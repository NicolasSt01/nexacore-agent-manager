"""Portfolio visibility — the second isolation axis, on top of the agency.

NexaCore is a single agency whose sellers each own the clients they register.
`agency_id` is still the tenant boundary; this module adds the per-seller rule
and is the single place that decides who sees what.

Every resource that hangs off a client (agents, conversations, channels, tools)
must go through here. Filtering only by `agency_id` — the pre-existing rule —
leaks one seller's book to another.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import Select, select

from ..deps import is_superadmin
from ..models import Client, User


def owned_client_ids(user: User) -> Select:
    """Subquery of the client ids a seller owns. Kept as a subquery rather than
    a materialized list so it composes into the caller's query."""
    return select(Client.id).where(
        Client.agency_id == user.agency_id,
        Client.created_by_user_id == user.id,
    )


def scope_clients(stmt: Select, user: User) -> Select:
    """Restrict a select over Client itself. Client carries the ownership
    column directly, so it cannot go through `scope_to_agency`."""
    stmt = stmt.where(Client.agency_id == user.agency_id)
    if not is_superadmin(user):
        stmt = stmt.where(Client.created_by_user_id == user.id)
    return stmt


def scope_to_agency(stmt: Select, model, user: User) -> Select:
    """Restrict a select over a client-owned model to what the user may see:
    the whole agency for a superadmin, only their own portfolio for a seller.

    `model` must expose `agency_id` and `client_id`.
    """
    stmt = stmt.where(model.agency_id == user.agency_id)
    if not is_superadmin(user):
        stmt = stmt.where(model.client_id.in_(owned_client_ids(user)))
    return stmt


def not_found(detail: str) -> HTTPException:
    """404 rather than 403 for a resource owned by another seller: a 403 would
    confirm it exists and leak the shape of the other portfolio."""
    return HTTPException(status_code=404, detail=detail)


def visible_client_ids(db, user: User) -> list[uuid.UUID] | None:
    """Client ids the user may see, or None for 'every client in the agency'.

    Prefer `scope_to_agency`; use this only where the ids themselves are needed
    (aggregate queries that cannot be expressed as a filter on one model).
    """
    if is_superadmin(user):
        return None
    return list(db.scalars(owned_client_ids(user)))
