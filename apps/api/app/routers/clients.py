import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Client, User
from ..schemas import ClientCreate, ClientOut, ClientPortalUpdate, ClientUpdate
from ..security import hash_password
from ..slugs import slugify, unique_slug


router = APIRouter(prefix="/clients", tags=["Clients"])


def _client(db: Session, user: User, client_id: uuid.UUID) -> Client:
    client = db.scalar(
        select(Client)
        .options(selectinload(Client.agents))
        .where(Client.id == client_id, Client.agency_id == user.agency_id)
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(
        select(Client)
        .options(selectinload(Client.agents))
        .where(Client.agency_id == user.agency_id)
        .order_by(Client.created_at.desc())
    ).all()


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = Client(
        agency_id=user.agency_id,
        portal_slug=unique_slug(db, Client, "portal_slug", payload.name),
        **payload.model_dump(),
    )
    db.add(client)
    db.commit()
    return _client(db, user, client.id)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _client(db, user, client_id)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: uuid.UUID, payload: ClientUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = _client(db, user, client_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    db.commit()
    return _client(db, user, client_id)


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
    return _client(db, user, client_id)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = _client(db, user, client_id)
    db.delete(client)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
