"""The public calendar file for a booked appointment.

Unauthenticated by design: the "add to calendar" button is pressed from a mail
client with no session, on a phone that has never seen the app. The unguessable
token on the appointment row is the credential, and the response carries nothing
beyond what the recipient was already emailed.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Appointment, Client
from ..ratelimit import calendar_rate_limit
from ..services import calendar_invite


public_router = APIRouter(prefix="/public", tags=["Public"])


@public_router.get("/appointments/{token}.ics", dependencies=[Depends(calendar_rate_limit)])
def appointment_ics(token: str, db: Session = Depends(get_db)):
    appointment = db.scalar(select(Appointment).where(Appointment.public_token == token))
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    client = db.get(Client, appointment.client_id)
    body = calendar_invite.build_ics(appointment, organizer_name=client.name if client else "")
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            # attachment, so mobile mail clients hand the file to the calendar
            # app instead of rendering it as text.
            "Content-Disposition": 'attachment; filename="cita.ics"',
            "Cache-Control": "no-store",
        },
    )
