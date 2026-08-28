"""Bootstrap data applied on API startup.

Seeds are declarative JSON files under ``app/seeds/`` describing an agency, its
users, clients and agents. They are applied create-only: anything already
present (matched by its natural key — agency slug, user email, client portal
slug, agent name within a client) is left untouched, so restarting the API
never overwrites what was edited in the UI.

``SEED_DIR`` points the loader at a directory outside the repository (a mounted
volume, say) when the bootstrap data is private.

Secrets never live in a seed file. A user's password may be supplied through
the environment variable named by ``password_env`` (falling back to the bundled
hash), and a provider API key is only created when the variable named by
``api_key_env`` is set.
"""

import json
import os
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Base, SessionLocal, engine
from ..models import Agency, Agent, AgentQA, Client, ProviderCredential, User
from ..security import encrypt_secret, hash_password


SEEDS_DIR = Path(__file__).resolve().parents[1] / "seeds"


def seeds_dir() -> Path:
    """Where seed files are read from: ``SEED_DIR`` when set, else app/seeds/."""
    configured = get_settings().seed_dir
    return Path(configured) if configured else SEEDS_DIR


def run_seeds() -> None:
    """Create any missing tables, then apply every seed file."""
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    if not settings.seed_enabled:
        return
    for path in sorted(seeds_dir().glob("*.json")):
        db = SessionLocal()
        try:
            apply_seed(db, json.loads(path.read_text(encoding="utf-8")), settings.seed_reset_passwords)
            db.commit()
            print(f"✅ Seed '{path.stem}' applied.")
        except Exception as exc:  # a broken seed must never stop the API from booting
            db.rollback()
            print(f"⚠️ Error applying seed '{path.stem}': {exc}")
        finally:
            db.close()


def apply_seed(db: Session, data: dict, reset_passwords: bool = False) -> Agency:
    agency = _agency(db, data["agency"])
    owner = None
    for spec in data.get("users", []):
        user = _user(db, agency, spec, reset_passwords)
        if spec.get("owner") or owner is None:
            owner = user
    for spec in data.get("provider_credentials", []):
        _provider_credential(db, agency, spec)
    for spec in data.get("clients", []):
        _client(db, agency, owner, spec)
    return agency


def _agency(db: Session, spec: dict) -> Agency:
    agency = db.scalar(select(Agency).where(Agency.slug == spec["slug"]))
    if not agency:
        agency = db.scalar(select(Agency).where(Agency.name == spec["name"]))
    if agency:
        return agency
    agency = Agency(name=spec["name"], slug=spec["slug"], brand_color=spec.get("brand_color", "#075985"))
    db.add(agency)
    db.flush()
    return agency


def _password_hash(spec: dict) -> str:
    """The password from the environment when provided, else the bundled hash."""
    plaintext = os.getenv(spec["password_env"], "") if spec.get("password_env") else ""
    return hash_password(plaintext) if plaintext else spec["password_hash"]


def _user(db: Session, agency: Agency, spec: dict, reset_passwords: bool) -> User:
    user = db.scalar(select(User).where(User.email == spec["email"]))
    if user:
        if reset_passwords:
            user.role = spec.get("role", "admin")
            user.password_hash = _password_hash(spec)
        return user
    user = User(
        agency_id=agency.id,
        name=spec["name"],
        email=spec["email"],
        role=spec.get("role", "admin"),
        password_hash=_password_hash(spec),
    )
    db.add(user)
    db.flush()
    return user


def _provider_credential(db: Session, agency: Agency, spec: dict) -> None:
    api_key = os.getenv(spec["api_key_env"], "") if spec.get("api_key_env") else ""
    if not api_key:
        return
    exists = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.agency_id == agency.id,
            ProviderCredential.provider == spec["provider"],
        )
    )
    if exists:
        return
    db.add(
        ProviderCredential(
            agency_id=agency.id,
            provider=spec["provider"],
            encrypted_api_key=encrypt_secret(api_key),
            base_url=spec.get("base_url") or None,
        )
    )


def _client(db: Session, agency: Agency, owner: User | None, spec: dict) -> Client:
    fields = {key: value for key, value in spec.items() if key != "agents"}
    client = db.scalar(select(Client).where(Client.portal_slug == fields["portal_slug"]))
    if not client:
        if "monthly_fee_mxn" in fields:
            fields["monthly_fee_mxn"] = Decimal(str(fields["monthly_fee_mxn"]))
        client = Client(
            agency_id=agency.id,
            created_by_user_id=owner.id if owner else None,
            **fields,
        )
        db.add(client)
        db.flush()
    for agent_spec in spec.get("agents", []):
        _agent(db, agency, client, agent_spec)
    return client


def _agent(db: Session, agency: Agency, client: Client, spec: dict) -> Agent:
    fields = {key: value for key, value in spec.items() if key != "qa"}
    agent = db.scalar(
        select(Agent).where(Agent.client_id == client.id, Agent.name == fields["name"])
    )
    if agent:
        return agent
    agent = Agent(agency_id=agency.id, client_id=client.id, **fields)
    db.add(agent)
    db.flush()
    for position, qa in enumerate(spec.get("qa", [])):
        db.add(
            AgentQA(
                agent_id=agent.id,
                question=qa["question"],
                answer=qa["answer"],
                position=qa.get("position", position),
            )
        )
    return agent
