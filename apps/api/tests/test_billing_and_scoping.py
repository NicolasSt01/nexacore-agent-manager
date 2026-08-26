"""Portfolio isolation between sellers, and per-client token accounting.

These cover the two places where a mistake is expensive rather than annoying:
one seller seeing another's book, and one client's consumption being charged
against everybody else's quota.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.models import Client as ClientModel
from app.models import UsageRecord
from app.services.billing import get_cycle_window


SELLER_PASSWORD = "contrasena-segura"


def _login(client: TestClient, email: str, password: str = SELLER_PASSWORD) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


def _create_seller(client: TestClient, name: str, email: str) -> dict:
    response = client.post(
        "/api/agency/users",
        json={"name": name, "email": email, "password": SELLER_PASSWORD, "role": "seller"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_client(client: TestClient, name: str, fee: str = "200.00", limit: int = 500_000) -> dict:
    response = client.post(
        "/api/clients",
        json={"name": name, "billing_mode": "plan", "monthly_fee_mxn": fee, "monthly_token_limit": limit},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def agency_with_sellers(authenticated_client: TestClient):
    """Ana (agency owner) plus two sellers in the same agency, each with a client."""
    admin = authenticated_client
    edgar = _create_seller(admin, "Edgar", "edgar@prisma.com")
    enedina = _create_seller(admin, "Enedina", "enedina@prisma.com")

    _login(admin, "edgar@prisma.com")
    edgar_client = _create_client(admin, "Consultorio Dental")

    _login(admin, "enedina@prisma.com")
    enedina_client = _create_client(admin, "Despacho Juridico", fee="500.00", limit=1_000_000)

    return {
        "client": admin,
        "edgar": edgar,
        "enedina": enedina,
        "edgar_client": edgar_client,
        "enedina_client": enedina_client,
    }


# --- Seller scoping -------------------------------------------------------


def test_seller_only_lists_own_clients(agency_with_sellers):
    ctx = agency_with_sellers
    api = ctx["client"]

    _login(api, "edgar@prisma.com")
    ids = {row["id"] for row in api.get("/api/clients").json()}
    assert ctx["edgar_client"]["id"] in ids
    assert ctx["enedina_client"]["id"] not in ids

    _login(api, "enedina@prisma.com")
    ids = {row["id"] for row in api.get("/api/clients").json()}
    assert ctx["enedina_client"]["id"] in ids
    assert ctx["edgar_client"]["id"] not in ids


def test_reaching_another_sellers_client_is_404_not_403(agency_with_sellers):
    ctx = agency_with_sellers
    api = ctx["client"]
    _login(api, "enedina@prisma.com")
    # 403 would confirm the client exists and leak the shape of the portfolio.
    assert api.get(f"/api/clients/{ctx['edgar_client']['id']}").status_code == 404
    assert api.patch(f"/api/clients/{ctx['edgar_client']['id']}", json={"name": "Robado"}).status_code == 404


def test_client_ownership_comes_from_the_session_not_the_payload(agency_with_sellers):
    ctx = agency_with_sellers
    api = ctx["client"]
    _login(api, "enedina@prisma.com")
    created = api.post(
        "/api/clients",
        json={"name": "Suplantacion", "billing_mode": "plan", "created_by_user_id": ctx["edgar"]["id"]},
    )
    assert created.status_code == 201
    assert created.json()["created_by_user_id"] == ctx["enedina"]["id"]


def test_superadmin_sees_every_client(agency_with_sellers):
    ctx = agency_with_sellers
    api = ctx["client"]
    _login(api, "ana@prisma.com")
    ids = {row["id"] for row in api.get("/api/clients").json()}
    assert {ctx["edgar_client"]["id"], ctx["enedina_client"]["id"]} <= ids


def test_finance_dashboard_is_superadmin_only(agency_with_sellers):
    ctx = agency_with_sellers
    api = ctx["client"]

    _login(api, "edgar@prisma.com")
    assert api.get("/api/dashboard/finance").status_code == 403
    assert api.post(
        "/api/agency/users",
        json={"name": "Colado", "email": "colado@prisma.com", "password": SELLER_PASSWORD, "role": "seller"},
    ).status_code == 403

    _login(api, "ana@prisma.com")
    finance = api.get("/api/dashboard/finance")
    assert finance.status_code == 200
    body = finance.json()
    assert body["total_monthly_revenue_mxn"] == 700.0
    per_seller = {row["worker_id"]: row for row in body["workers_metrics"]}
    assert per_seller[ctx["edgar"]["id"]]["monthly_revenue_mxn"] == 200.0
    assert per_seller[ctx["enedina"]["id"]]["monthly_revenue_mxn"] == 500.0


def test_only_superadmin_can_reassign_a_client(agency_with_sellers):
    ctx = agency_with_sellers
    api = ctx["client"]

    _login(api, "enedina@prisma.com")
    stolen = api.patch(
        f"/api/clients/{ctx['edgar_client']['id']}/owner",
        json={"owner_user_id": ctx["enedina"]["id"]},
    )
    assert stolen.status_code == 403

    _login(api, "ana@prisma.com")
    moved = api.patch(
        f"/api/clients/{ctx['edgar_client']['id']}/owner",
        json={"owner_user_id": ctx["enedina"]["id"]},
    )
    assert moved.status_code == 200
    assert moved.json()["created_by_user_id"] == ctx["enedina"]["id"]


# --- Token accounting -----------------------------------------------------


def _add_usage(db, client_id, agency_id, tokens: int, *, source: str = "whatsapp", when: datetime | None = None) -> None:
    record = UsageRecord(
        agency_id=agency_id,
        client_id=client_id,
        agent_id=None,
        provider="openai",
        model="gpt-5.6-luna",
        input_tokens=tokens,
        output_tokens=0,
        source=source,
    )
    if when is not None:
        record.created_at = when
    db.add(record)
    db.commit()


def test_usage_is_counted_per_client_not_per_agency(agency_with_sellers, db_session):
    """Regression: consumption was summed by agency, so one client burning
    through their package blocked every other client in NexaCore."""
    ctx = agency_with_sellers
    api = ctx["client"]

    agency_id = db_session.get(ClientModel, uuid.UUID(ctx["edgar_client"]["id"])).agency_id
    _add_usage(db_session, uuid.UUID(ctx["edgar_client"]["id"]), agency_id, 100_000)

    _login(api, "edgar@prisma.com")
    edgar_view = api.get(f"/api/clients/{ctx['edgar_client']['id']}").json()
    assert edgar_view["used_tokens_current_cycle"] == 100_000

    _login(api, "enedina@prisma.com")
    enedina_view = api.get(f"/api/clients/{ctx['enedina_client']['id']}").json()
    assert enedina_view["used_tokens_current_cycle"] == 0
    assert enedina_view["is_blocked"] is False


def test_playground_usage_does_not_consume_client_quota(agency_with_sellers, db_session):
    ctx = agency_with_sellers
    api = ctx["client"]

    agency_id = db_session.get(ClientModel, uuid.UUID(ctx["edgar_client"]["id"])).agency_id
    _add_usage(db_session, uuid.UUID(ctx["edgar_client"]["id"]), agency_id, 50_000, source="playground")

    _login(api, "edgar@prisma.com")
    view = api.get(f"/api/clients/{ctx['edgar_client']['id']}").json()
    assert view["used_tokens_current_cycle"] == 0


def test_usage_outside_the_cycle_window_is_excluded(agency_with_sellers, db_session):
    ctx = agency_with_sellers
    api = ctx["client"]

    model = db_session.get(ClientModel, uuid.UUID(ctx["edgar_client"]["id"]))
    agency_id = model.agency_id
    cycle_start, _ = get_cycle_window(model)

    _add_usage(db_session, uuid.UUID(ctx["edgar_client"]["id"]), agency_id, 70_000, when=cycle_start - timedelta(days=1))
    _add_usage(db_session, uuid.UUID(ctx["edgar_client"]["id"]), agency_id, 20_000, when=cycle_start + timedelta(hours=1))

    _login(api, "edgar@prisma.com")
    view = api.get(f"/api/clients/{ctx['edgar_client']['id']}").json()
    assert view["used_tokens_current_cycle"] == 20_000


def test_client_is_blocked_once_the_limit_is_reached(agency_with_sellers, db_session):
    ctx = agency_with_sellers
    api = ctx["client"]

    agency_id = db_session.get(ClientModel, uuid.UUID(ctx["edgar_client"]["id"])).agency_id
    _add_usage(db_session, uuid.UUID(ctx["edgar_client"]["id"]), agency_id, 500_000)

    _login(api, "edgar@prisma.com")
    view = api.get(f"/api/clients/{ctx['edgar_client']['id']}").json()
    assert view["is_blocked"] is True
    assert view["percentage_tokens_used"] == 100.0


def test_byok_and_unlimited_clients_are_never_blocked(agency_with_sellers, db_session):
    ctx = agency_with_sellers
    api = ctx["client"]

    agency_id = db_session.get(ClientModel, uuid.UUID(ctx["edgar_client"]["id"])).agency_id
    _add_usage(db_session, uuid.UUID(ctx["edgar_client"]["id"]), agency_id, 900_000)

    _login(api, "edgar@prisma.com")
    byok = api.patch(f"/api/clients/{ctx['edgar_client']['id']}", json={"billing_mode": "byok"})
    assert byok.status_code == 200
    assert byok.json()["is_blocked"] is False

    unlimited = api.patch(
        f"/api/clients/{ctx['edgar_client']['id']}",
        json={"billing_mode": "plan", "monthly_token_limit": 0},
    )
    assert unlimited.json()["is_blocked"] is False


# --- Billing cycle windows ------------------------------------------------


class _FakeClient:
    """Just enough of a Client for the pure cycle-window calculation."""

    def __init__(self, anchor: int):
        self.billing_anchor_day = anchor


@pytest.mark.parametrize(
    ("anchor", "now", "expected_start", "expected_end"),
    [
        # Mid-cycle: signed up on the 12th, asked on the 20th.
        (12, datetime(2026, 3, 20, tzinfo=timezone.utc), datetime(2026, 3, 12, tzinfo=timezone.utc), datetime(2026, 4, 12, tzinfo=timezone.utc)),
        # Before this month's anchor: the cycle still belongs to last month.
        (12, datetime(2026, 3, 5, tzinfo=timezone.utc), datetime(2026, 2, 12, tzinfo=timezone.utc), datetime(2026, 3, 12, tzinfo=timezone.utc)),
        # Exactly on the anchor: a new cycle starts today.
        (12, datetime(2026, 3, 12, tzinfo=timezone.utc), datetime(2026, 3, 12, tzinfo=timezone.utc), datetime(2026, 4, 12, tzinfo=timezone.utc)),
        # Anchor past the end of a short month is clamped, never skipped.
        (31, datetime(2026, 2, 15, tzinfo=timezone.utc), datetime(2026, 1, 31, tzinfo=timezone.utc), datetime(2026, 2, 28, tzinfo=timezone.utc)),
        # Year boundary.
        (12, datetime(2026, 1, 5, tzinfo=timezone.utc), datetime(2025, 12, 12, tzinfo=timezone.utc), datetime(2026, 1, 12, tzinfo=timezone.utc)),
        (12, datetime(2026, 12, 20, tzinfo=timezone.utc), datetime(2026, 12, 12, tzinfo=timezone.utc), datetime(2027, 1, 12, tzinfo=timezone.utc)),
    ],
)
def test_cycle_window_is_anchored_to_the_signup_day(anchor, now, expected_start, expected_end):
    start, end = get_cycle_window(_FakeClient(anchor), now)
    assert (start, end) == (expected_start, expected_end)


def test_cycle_windows_are_contiguous_across_a_full_year():
    """Walking day by day, the window must never gap or overlap."""
    client = _FakeClient(31)
    day = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seen = []
    while day < datetime(2027, 1, 1, tzinfo=timezone.utc):
        start, end = get_cycle_window(client, day)
        assert start <= day < end
        if not seen or seen[-1] != (start, end):
            seen.append((start, end))
        day += timedelta(days=1)
    for (_, previous_end), (next_start, _) in zip(seen, seen[1:]):
        assert previous_end == next_start
