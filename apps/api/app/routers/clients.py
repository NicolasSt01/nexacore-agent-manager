import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user, is_superadmin, require_superadmin
from ..models import Client, User, new_domain_token, now_utc
from ..schemas import (
    ClientCreate,
    ClientDomainOut,
    ClientDomainSet,
    ClientOut,
    ClientOwnerUpdate,
    ClientPortalUpdate,
    ClientUpdate,
)
from ..security import hash_password
from ..services import billing as billing_service
from ..services.scoping import not_found, scope_clients
from ..services import dns as dns_service
from ..slugs import slugify, unique_slug


router = APIRouter(prefix="/clients", tags=["Clients"])


def _domain_out(client: Client) -> ClientDomainOut:
    if not client.portal_domain:
        return ClientDomainOut(domain=None, verified=False, txt_host=None, txt_value=None)
    return ClientDomainOut(
        domain=client.portal_domain,
        verified=client.portal_domain_verified,
        txt_host=dns_service.challenge_host(client.portal_domain),
        txt_value=client.portal_domain_token,
    )


def _enrich_client_out(db: Session, client: Client) -> ClientOut:
    """Attach the live quota status, which is derived per request rather than
    stored on the client row."""
    quota = billing_service.get_quota_status(db, client)
    out = ClientOut.model_validate(client)
    out.used_tokens_current_cycle = quota["used_tokens"]
    out.percentage_tokens_used = quota["percentage_used"]
    out.is_blocked = quota["is_blocked"]
    out.cycle_start = quota["cycle_start"]
    out.cycle_end = quota["cycle_end"]
    return out


def _client(db: Session, user: User, client_id: uuid.UUID) -> Client:
    stmt = scope_clients(select(Client).options(selectinload(Client.agents)).where(Client.id == client_id), user)
    client = db.scalar(stmt)
    if not client:
        # 404 rather than 403 on another seller's client: a 403 would confirm
        # the client exists and leak the size and shape of their portfolio.
        raise not_found("Client not found")
    return client


@router.get("", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = scope_clients(select(Client).options(selectinload(Client.agents)), user)
    clients = db.scalars(stmt.order_by(Client.created_at.desc())).all()
    return [_enrich_client_out(db, client) for client in clients]


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = now_utc()
    client = Client(
        agency_id=user.agency_id,
        # Ownership always comes from the session, never from the payload.
        created_by_user_id=user.id,
        portal_slug=unique_slug(db, Client, "portal_slug", payload.name),
        # The billing cycle cuts on the signup day: registered on the 12th,
        # cuts on the 12th of every month.
        billing_anchor_day=now.day,
        **payload.model_dump(),
    )
    db.add(client)
    db.commit()
    return _enrich_client_out(db, _client(db, user, client.id))


@router.patch("/{client_id}/owner", response_model=ClientOut)
def reassign_client(
    client_id: uuid.UUID,
    payload: ClientOwnerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_superadmin),
):
    """Move a client to another seller. Superadmin only — a seller must not be
    able to hand a client over to, or take one from, a colleague."""
    client = _client(db, user, client_id)
    owner = db.scalar(
        select(User).where(User.id == payload.owner_user_id, User.agency_id == user.agency_id)
    )
    if not owner:
        raise HTTPException(status_code=404, detail="User not found in this agency")
    client.created_by_user_id = owner.id
    db.commit()
    return _enrich_client_out(db, _client(db, user, client_id))


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _enrich_client_out(db, _client(db, user, client_id))


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: uuid.UUID, payload: ClientUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = _client(db, user, client_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    db.commit()
    return _enrich_client_out(db, _client(db, user, client_id))


@router.patch("/{client_id}/portal", response_model=ClientOut)
def update_client_portal(
    client_id: uuid.UUID,
    payload: ClientPortalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    client = _client(db, user, client_id)
    values = payload.model_dump(exclude_unset=True)
    password = values.pop("portal_password", None)
    if password:
        client.portal_password_hash = hash_password(password)
    if "portal_email" in values and values["portal_email"]:
        values["portal_email"] = str(values["portal_email"]).lower()
    if "portal_slug" in values and values["portal_slug"]:
        candidate = slugify(values["portal_slug"])
        existing = db.scalar(select(Client).where(Client.portal_slug == candidate, Client.id != client.id))
        if existing:
            raise HTTPException(status_code=409, detail="That portal URL is already in use")
        values["portal_slug"] = candidate
    for key, value in values.items():
        setattr(client, key, value)
    if client.portal_enabled and (not client.portal_email or not client.portal_password_hash):
        raise HTTPException(status_code=400, detail="Set an email and a password before enabling the portal")
    db.commit()
    return _enrich_client_out(db, _client(db, user, client_id))


@router.get("/{client_id}/domain", response_model=ClientDomainOut)
def get_client_domain(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _domain_out(_client(db, user, client_id))


@router.put("/{client_id}/domain", response_model=ClientDomainOut)
def set_client_domain(
    client_id: uuid.UUID,
    payload: ClientDomainSet,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    client = _client(db, user, client_id)
    domain = payload.domain.strip().lower()
    taken = db.scalar(select(Client).where(Client.portal_domain == domain, Client.id != client.id))
    if taken:
        raise HTTPException(status_code=409, detail="That domain is already in use")
    # Re-assigning resets verification and issues a fresh challenge token.
    if client.portal_domain != domain or not client.portal_domain_token:
        client.portal_domain_token = new_domain_token()
    client.portal_domain = domain
    client.portal_domain_verified = False
    db.commit()
    return _domain_out(_client(db, user, client_id))


@router.post("/{client_id}/domain/verify", response_model=ClientDomainOut)
def verify_client_domain(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = _client(db, user, client_id)
    if not client.portal_domain:
        raise HTTPException(status_code=400, detail="Add a domain before verifying it")
    if not dns_service.txt_contains(client.portal_domain, client.portal_domain_token):
        raise HTTPException(status_code=400, detail="The verification TXT record was not found yet. DNS can take a while to propagate.")
    client.portal_domain_verified = True
    db.commit()
    return _domain_out(_client(db, user, client_id))


@router.delete("/{client_id}/domain", response_model=ClientDomainOut)
def delete_client_domain(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = _client(db, user, client_id)
    client.portal_domain = None
    client.portal_domain_verified = False
    client.portal_domain_token = ""
    db.commit()
    return _domain_out(_client(db, user, client_id))


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = _client(db, user, client_id)
    db.delete(client)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
