"""Calendar artefacts for an appointment: an .ics file and add-to-calendar links.

No third-party integration and no OAuth. Between an iCalendar file and two
deeplinks every mainstream client is covered:

- Google Calendar and Outlook/Microsoft 365 take a pre-filled URL.
- Apple Calendar, iOS Mail, Android and Outlook desktop open the .ics, which
  also rides along as an attachment so the mail app can offer "add to calendar"
  without a round trip.
"""

from datetime import datetime, timezone
from urllib.parse import quote

from ..config import get_settings
from ..models import Appointment


GOOGLE_BASE = "https://calendar.google.com/calendar/render"
OUTLOOK_BASE = "https://outlook.live.com/calendar/0/deeplink/compose"
OFFICE_BASE = "https://outlook.office.com/calendar/0/deeplink/compose"

# RFC 5545 caps a content line at 75 octets; longer lines must be folded with a
# CRLF and a leading space or the file is rejected by strict parsers.
MAX_LINE_OCTETS = 74


def _utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _stamp(moment: datetime) -> str:
    return _utc(moment).strftime("%Y%m%dT%H%M%SZ")


def _escape(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold one content line onto continuation lines, counting octets."""
    encoded = line.encode("utf-8")
    if len(encoded) <= MAX_LINE_OCTETS:
        return line
    chunks: list[str] = []
    current = b""
    for char in line:
        char_bytes = char.encode("utf-8")
        limit = MAX_LINE_OCTETS if not chunks else MAX_LINE_OCTETS - 1
        if len(current) + len(char_bytes) > limit:
            chunks.append(current.decode("utf-8"))
            current = b""
        current += char_bytes
    if current:
        chunks.append(current.decode("utf-8"))
    return "\r\n ".join(chunks)


def description_for(appointment: Appointment) -> str:
    parts = [appointment.notes.strip()]
    if appointment.contact_name:
        parts.append(f"Contacto: {appointment.contact_name}")
    if appointment.contact_phone:
        parts.append(f"Teléfono: {appointment.contact_phone}")
    if appointment.contact_email:
        parts.append(f"Correo: {appointment.contact_email}")
    return "\n".join(part for part in parts if part)


def build_ics(appointment: Appointment, *, organizer_name: str) -> str:
    """The iCalendar file for this appointment.

    METHOD:PUBLISH rather than REQUEST: this is a copy of a confirmed booking
    for the recipient's own calendar, not an invitation awaiting an RSVP that
    nothing on our side would ever process.
    """
    event = [
        "BEGIN:VEVENT",
        f"UID:{appointment.public_token}@nexacore",
        f"DTSTAMP:{_stamp(appointment.created_at or datetime.now(timezone.utc))}",
        f"DTSTART:{_stamp(appointment.starts_at)}",
        f"DTEND:{_stamp(appointment.ends_at)}",
        f"SUMMARY:{_escape(appointment.title)}",
        f"DESCRIPTION:{_escape(description_for(appointment))}",
        f"ORGANIZER;CN={_escape(organizer_name)}:MAILTO:noreply@invalid",
        "STATUS:CONFIRMED" if appointment.status == "confirmed" else "STATUS:CANCELLED",
        "SEQUENCE:0",
    ]
    if appointment.location:
        event.append(f"LOCATION:{_escape(appointment.location)}")
    # A one-hour reminder, so the event is useful the moment it is imported.
    event += [
        "BEGIN:VALARM",
        "TRIGGER:-PT60M",
        "ACTION:DISPLAY",
        "DESCRIPTION:Recordatorio",
        "END:VALARM",
        "END:VEVENT",
    ]
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NexaCore//Agent Manager//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *event,
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def ics_url(appointment: Appointment) -> str:
    """Public URL of the .ics, used by the button in the email.

    Built on the frontend origin because that is the address the gateway serves
    publicly; it proxies /api/* through to this backend.
    """
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}/api/public/appointments/{appointment.public_token}.ics"


def google_url(appointment: Appointment) -> str:
    params = {
        "action": "TEMPLATE",
        "text": appointment.title,
        "dates": f"{_stamp(appointment.starts_at)}/{_stamp(appointment.ends_at)}",
        "details": description_for(appointment),
        "location": appointment.location,
    }
    query = "&".join(f"{key}={quote(value or '', safe='')}" for key, value in params.items())
    return f"{GOOGLE_BASE}?{query}"


def _outlook_url(base: str, appointment: Appointment) -> str:
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": appointment.title,
        "startdt": _utc(appointment.starts_at).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "enddt": _utc(appointment.ends_at).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "body": description_for(appointment),
        "location": appointment.location,
    }
    query = "&".join(f"{key}={quote(value or '', safe='')}" for key, value in params.items())
    return f"{base}?{query}"


def outlook_url(appointment: Appointment) -> str:
    return _outlook_url(OUTLOOK_BASE, appointment)


def office_url(appointment: Appointment) -> str:
    return _outlook_url(OFFICE_BASE, appointment)
