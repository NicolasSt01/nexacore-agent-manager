"""Daily model-catalog sync.

Providers retire models and change prices without warning, and either one hits
NexaCore's margin — or breaks a client's agent outright when the model it is
pinned to disappears. This job asks each configured provider what it currently
offers, compares it against the catalog and the agents in use, and emails the
owner only when something actually changed.

It deliberately reports rather than auto-applies: which model a client's agent
runs on is a commercial decision, not something a cron job should change.
"""

import logging
from dataclasses import dataclass, field
from datetime import date

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Agency, Agent, ModelPrice, now_utc
from .mailer import get_settings_row, send_email
from .model_catalog import list_models
from .providers import PROVIDERS, base_url_for
from .providers import resolve_provider_credentials


logger = logging.getLogger("nexacore.model_sync")

LIST_TIMEOUT = 25


@dataclass
class SyncReport:
    checked_providers: list[str] = field(default_factory=list)
    unreachable: list[tuple[str, str]] = field(default_factory=list)
    # Catalog models the provider no longer lists.
    retired: list[tuple[str, str]] = field(default_factory=list)
    # Models the provider lists that the catalog does not know about.
    new_models: list[tuple[str, str]] = field(default_factory=list)
    # Agents pinned to a model that is no longer available — the urgent one.
    agents_at_risk: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.retired or self.new_models or self.agents_at_risk or self.unreachable)


def _list_remote_models(provider: str, base_url: str, api_key: str) -> set[str] | None:
    """Model ids the provider currently offers, or None if unreachable."""
    url = f"{base_url.rstrip('/')}/models"
    headers = (
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        if provider == "anthropic"
        else {"Authorization": f"Bearer {api_key}"}
    )
    try:
        response = httpx.get(url, headers=headers, timeout=LIST_TIMEOUT)
        if response.status_code >= 400:
            return None
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return None
    ids = set()
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            ids.add(str(row["id"]))
        elif isinstance(row, str):
            ids.add(row)
    return ids or None


def run_sync(db: Session, agency_id) -> SyncReport:
    """Compare every configured provider against the catalog. Read-only."""
    report = SyncReport()
    catalog = list_models()
    by_provider: dict[str, set[str]] = {}
    for model in catalog:
        by_provider.setdefault(model.provider, set()).add(model.id)

    # Models actually in use, so a retirement can be reported by client impact.
    agents = db.scalars(select(Agent).where(Agent.agency_id == agency_id, Agent.is_active.is_(True))).all()

    for provider in PROVIDERS:
        credentials = resolve_provider_credentials(db, agency_id, provider)
        if not credentials:
            continue
        base_url, api_key = credentials
        report.checked_providers.append(provider)

        remote = _list_remote_models(provider, base_url, api_key)
        if remote is None:
            report.unreachable.append((provider, base_url or base_url_for(provider)))
            continue

        known = by_provider.get(provider, set())
        for model_id in sorted(known - remote):
            report.retired.append((provider, model_id))
        # Only surface genuinely new families, not every dated snapshot, or the
        # report becomes noise nobody reads.
        interesting = {m for m in remote if not any(ch.isdigit() for ch in m.split("-")[-1])}
        for model_id in sorted(interesting - known)[:15]:
            report.new_models.append((provider, model_id))

        for agent in agents:
            if agent.provider == provider and agent.model.strip() and agent.model.strip() not in remote:
                report.agents_at_risk.append((agent.client.name, agent.name, agent.model.strip()))

    return report


def _format_report(report: SyncReport, when: date) -> str:
    lines = [f"Revisión diaria del catálogo de modelos — {when:%d/%m/%Y}", ""]

    if report.agents_at_risk:
        lines += ["🔴 AGENTES EN RIESGO (el modelo ya no está disponible):", ""]
        for client_name, agent_name, model in report.agents_at_risk:
            lines.append(f"  · {client_name} — agente “{agent_name}” usa {model}")
        lines += ["", "  Estos agentes fallarán en cuanto llegue un mensaje. Cámbiales el modelo.", ""]

    if report.retired:
        lines += ["⚠️  Modelos del catálogo que el proveedor ya no lista:", ""]
        for provider, model in report.retired:
            lines.append(f"  · {provider}: {model}")
        lines.append("")

    if report.new_models:
        lines += ["🆕 Modelos nuevos disponibles que no están en el catálogo:", ""]
        for provider, model in report.new_models:
            lines.append(f"  · {provider}: {model}")
        lines.append("")

    if report.unreachable:
        lines += ["🔌 Proveedores que no se pudieron consultar:", ""]
        for provider, base_url in report.unreachable:
            lines.append(f"  · {provider} ({base_url})")
        lines += ["", "  Revisa la llave o el endpoint en Configuración.", ""]

    lines += [
        f"Proveedores revisados: {', '.join(report.checked_providers) or 'ninguno'}.",
        "",
        "Los precios no se modifican automáticamente: revisa y actualiza desde",
        "Configuración → Precios de modelos si algún proveedor cambió sus tarifas.",
        "",
        "— NexaCore Agent Manager",
    ]
    return "\n".join(lines)


def run_and_notify(db: Session, agency_id) -> SyncReport:
    """Run the sync and email the owner, but only when something changed."""
    report = run_sync(db, agency_id)
    if not report.has_changes:
        logger.info("Model sync: no changes for agency %s", agency_id)
        return report

    settings_row = get_settings_row(db, agency_id)
    recipient = (settings_row.owner_alert_email if settings_row else "") or ""
    if not recipient:
        logger.info("Model sync found changes but no owner_alert_email is configured")
        return report

    urgent = "🔴 " if report.agents_at_risk else ""
    send_email(
        db,
        agency_id,
        to=[recipient],
        subject=f"{urgent}Cambios en los modelos de IA — revisión del {now_utc():%d/%m/%Y}",
        body_text=_format_report(report, now_utc().date()),
    )
    return report


def sync_all_agencies(db: Session) -> None:
    """Entry point for the daily scheduler."""
    for agency_id in db.scalars(select(Agency.id)):
        try:
            run_and_notify(db, agency_id)
        except Exception as exc:  # noqa: BLE001 - one agency must not stop the rest
            logger.warning("Model sync failed for agency %s: %s", agency_id, exc)


def seed_prices_from_catalog(db: Session) -> int:
    """Insert a price row for every catalog model that has none.

    Idempotent: it only fills gaps, so it never overwrites a price a superadmin
    entered by hand.
    """
    existing = {
        (provider, model)
        for provider, model in db.execute(select(ModelPrice.provider, ModelPrice.model).distinct()).all()
    }
    added = 0
    for model in list_models():
        if (model.provider, model.id) in existing:
            continue
        db.add(
            ModelPrice(
                provider=model.provider,
                model=model.id,
                input_price_per_1k_usd=model.input_price_per_1k,
                output_price_per_1k_usd=model.output_price_per_1k,
                origin="catalog",
                note="Seeded from the built-in catalog",
            )
        )
        added += 1
    if added:
        db.commit()
    return added
