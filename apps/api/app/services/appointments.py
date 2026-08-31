"""Booking an appointment from a conversation, and telling both sides about it.

The agent calls this through its built-in schedule_appointment tool (see
services/tools/builtin.py). Two people need to hear about the result and they
need different things:

- The **contact** gets a confirmation they can act on: when, where, and a button
  that drops the event into whatever calendar they use.
- The **business owner** gets the contact's details, so the appointment lands in
  their calendar and they know who is coming without opening the app.

Copy is in Spanish on purpose: it is end-user facing, like the UI and the
agent's system prompt.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Agency, Agent, Appointment, Client, Conversation, now_utc
from . import calendar_invite
from .email_render import render_html, render_text
from .mailer import Attachment, send_email
from .summary import usable_summary


logger = logging.getLogger("nexacore.appointments")

MIN_DURATION_MINUTES = 5
MAX_DURATION_MINUTES = 12 * 60
# How far ahead a booking may be made. Anything past this is a typo in the year
# far more often than a real appointment.
MAX_HORIZON_DAYS = 730

DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


class BookingError(Exception):
    """A booking the agent must not retry as-is: the message is written for it."""


@dataclass
class BookingResult:
    appointment: Appointment
    contact_notified: bool
    owner_notified: bool


def zone_for(agent: Agent) -> ZoneInfo:
    name = (agent.timezone or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def parse_local(value: str, zone: ZoneInfo) -> datetime:
    """Read the start time the model produced, in the agent's timezone.

    Accepts "2026-09-03 16:00", the ISO "2026-09-03T16:00" form, and a value
    that already carries an offset — models emit all three.
    """
    text = (value or "").strip().replace("/", "-")
    if not text:
        raise BookingError("Falta la fecha y hora de la cita.")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text.replace(" ", "T"))
    except ValueError as exc:
        raise BookingError(
            "No pude interpretar la fecha. Usa el formato AAAA-MM-DD HH:MM en 24 horas."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


def format_local(moment: datetime, zone: ZoneInfo) -> str:
    local = moment.astimezone(zone)
    return (
        f"{DAYS[local.weekday()]} {local.day} de {MONTHS[local.month - 1]} "
        f"de {local.year}, {local:%H:%M} h"
    )


def _conflict(db: Session, client_id, starts_at: datetime, ends_at: datetime) -> Appointment | None:
    """An overlapping booking for the same business, if any.

    Two people being told the same slot is theirs is worse than the agent having
    to offer another time, so this is checked before anything is stored.
    """
    return db.scalar(
        select(Appointment).where(
            Appointment.client_id == client_id,
            Appointment.status == "confirmed",
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        )
    )


def book(
    db: Session,
    agent: Agent,
    conversation: Conversation | None,
    *,
    starts_at: str,
    contact_name: str = "",
    contact_email: str = "",
    contact_phone: str = "",
    reason: str = "",
    notes: str = "",
    summary: str = "",
    duration_minutes: int | None = None,
) -> Appointment:
    """Validate and store the booking. Raises BookingError with agent-facing copy."""
    zone = zone_for(agent)
    start = parse_local(starts_at, zone)
    duration = int(duration_minutes or agent.scheduling_duration_minutes or 60)
    if duration < MIN_DURATION_MINUTES or duration > MAX_DURATION_MINUTES:
        raise BookingError(
            f"La duración debe estar entre {MIN_DURATION_MINUTES} y {MAX_DURATION_MINUTES} minutos."
        )
    now = now_utc()
    if start <= now:
        raise BookingError(
            "Esa fecha ya pasó. Confirma con la persona una fecha futura y vuelve a intentarlo."
        )
    if start > now + timedelta(days=MAX_HORIZON_DAYS):
        raise BookingError("Esa fecha está demasiado lejos. Confirma el año con la persona.")

    email = (contact_email or "").strip()
    if agent.scheduling_require_email and not email:
        raise BookingError(
            "Falta el correo de la persona. Pídeselo antes de agendar para poder enviarle la confirmación."
        )
    if email and ("@" not in email or " " in email):
        # Not full validation, just enough to catch the model passing something
        # that is plainly not an address ("no tiene", a phone number).
        raise BookingError(
            "El correo no parece válido. Confírmalo con la persona, letra por letra si hace falta."
        )

    end = start + timedelta(minutes=duration)
    clash = _conflict(db, agent.client_id, start, end)
    if clash:
        raise BookingError(
            f"Ese horario ya está ocupado (hay una cita de {format_local(clash.starts_at, zone)} "
            f"a {clash.ends_at.astimezone(zone):%H:%M}). Ofrece otro horario."
        )

    appointment = Appointment(
        agency_id=agent.agency_id,
        client_id=agent.client_id,
        agent_id=agent.id,
        conversation_id=conversation.id if conversation else None,
        contact_name=(contact_name or "").strip()[:180],
        contact_email=email[:320] or None,
        contact_phone=(contact_phone or "").strip()[:60],
        title=(reason or "").strip()[:240] or f"Cita en {agent.client.name}",
        notes=(notes or "").strip(),
        # The agent's own recap of the conversation. When it writes none, the
        # contact card kept by services/summary.py is the next best thing —
        # better a machine summary than sending the business nothing at all.
        summary=(summary or "").strip() or (usable_summary(conversation) if conversation else ""),
        location=agent.scheduling_location or "",
        starts_at=start,
        ends_at=end,
        timezone=str(zone),
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def owner_recipients(agent: Agent, client: Client) -> list[str]:
    """Who at the business hears about a new appointment."""
    explicit = (agent.scheduling_owner_email or "").strip()
    return [address for address in [explicit or client.alert_email] if address]


def _calendar_buttons(appointment: Appointment) -> list[tuple[str, str]]:
    return [
        ("Google Calendar", calendar_invite.google_url(appointment)),
        ("Outlook", calendar_invite.outlook_url(appointment)),
        ("iPhone, Android u otro", calendar_invite.ics_url(appointment)),
    ]


def notify(db: Session, appointment: Appointment) -> BookingResult:
    """Send both confirmations. Never raises: a mail failure must not undo a booking."""
    client = db.get(Client, appointment.client_id)
    agent = db.get(Agent, appointment.agent_id)
    agency = db.get(Agency, appointment.agency_id)
    zone = zone_for(agent)
    when = format_local(appointment.starts_at, zone)
    until = appointment.ends_at.astimezone(zone).strftime("%H:%M")
    brand_color = agency.brand_color if agency else ""
    duration = int((appointment.ends_at - appointment.starts_at).total_seconds() // 60)
    ics = Attachment(
        filename="cita.ics",
        content=calendar_invite.build_ics(appointment, organizer_name=client.name),
        subtype="calendar",
        params={"method": "PUBLISH", "name": "cita.ics"},
    )
    buttons = _calendar_buttons(appointment)
    owners = owner_recipients(agent, client)

    contact_sent = False
    if appointment.contact_email:
        rows = [
            ("Fecha y hora", f"{when} a {until}"),
            ("Duración", f"{duration} minutos"),
            ("Lugar", appointment.location),
            ("Motivo", appointment.title),
            ("Atiende", client.name),
        ]
        greeting = f"Hola{' ' + appointment.contact_name.split()[0] if appointment.contact_name else ''},"
        contact_sent = send_email(
            db,
            appointment.agency_id,
            client=client,
            sender_name=client.name,
            to=[appointment.contact_email],
            reply_to=owners[0] if owners else None,
            subject=f"Cita confirmada en {client.name} — {when}",
            body_html=render_html(
                brand_name=client.name,
                brand_color=brand_color,
                title="Tu cita quedó confirmada",
                intro=f"{greeting} tu cita en {client.name} quedó agendada. Aquí están los detalles.",
                rows=rows,
                buttons=buttons,
                buttons_caption="Agrégala a tu calendario para que no se te pase:",
                note="Si necesitas cambiarla o cancelarla, responde este correo o escríbenos por el mismo medio por el que agendaste.",
                footer=f"{client.name} · Confirmación enviada automáticamente.",
            ),
            body_text=render_text(
                title="Tu cita quedó confirmada",
                intro=f"{greeting} tu cita en {client.name} quedó agendada.",
                rows=rows,
                buttons=buttons,
                note="Si necesitas cambiarla o cancelarla, responde este correo.",
                footer=client.name,
            ),
            attachments=[ics],
        )

    owner_sent = False
    if owners:
        rows = [
            ("Fecha y hora", f"{when} a {until}"),
            ("Duración", f"{duration} minutos"),
            ("Lugar", appointment.location),
            ("Motivo", appointment.title),
            ("Contacto", appointment.contact_name),
            ("Teléfono", appointment.contact_phone),
            ("Correo", appointment.contact_email or ""),
            ("Agendó", agent.name),
        ]
        owner_buttons = [*buttons]
        panel = f"{get_settings().frontend_url.rstrip('/')}/clients/{client.id}"
        owner_buttons.append(("Ver en el panel", panel))
        notes = (appointment.notes or "").strip()
        sections = [
            ("Resumen de la conversación", (appointment.summary or "").strip()),
            ("Notas", notes),
        ]
        owner_sent = send_email(
            db,
            appointment.agency_id,
            client=client,
            sender_name=client.name,
            to=owners,
            reply_to=appointment.contact_email,
            subject=f"Nueva cita: {appointment.contact_name or 'contacto'} — {when}",
            body_html=render_html(
                brand_name=client.name,
                brand_color=brand_color,
                title="Tienes una cita nueva",
                intro=f"{agent.name} agendó una cita durante una conversación. Estos son los datos.",
                rows=rows,
                sections=sections,
                buttons=owner_buttons,
                buttons_caption="Agrégala a tu calendario:",
                note="",
                footer="NexaCore Agent Manager · Aviso automático.",
            ),
            body_text=render_text(
                title="Tienes una cita nueva",
                intro=f"{agent.name} agendó una cita durante una conversación.",
                rows=rows,
                sections=sections,
                buttons=owner_buttons,
                note="",
                footer="NexaCore Agent Manager",
            ),
            attachments=[ics],
        )

    appointment.contact_notified = contact_sent
    appointment.owner_notified = owner_sent
    db.commit()
    if not contact_sent and not owner_sent:
        logger.info("Appointment %s stored but no confirmation could be sent", appointment.id)
    return BookingResult(appointment=appointment, contact_notified=contact_sent, owner_notified=owner_sent)
