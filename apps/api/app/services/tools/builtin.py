"""Tools the platform provides itself, without the client wiring anything up.

A built-in tool differs from an AgentTool row in what it can reach: it runs
inside the request, with the database session, the agent and the live
conversation in hand. That is what lets schedule_appointment store a booking
and email both sides, which no user-defined HTTP endpoint could do.
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ...models import Agent, Conversation
from ..appointments import BookingError, book, format_local, notify, zone_for
from .specs import ToolSpec


SCHEDULE_APPOINTMENT = "schedule_appointment"

SCHEDULE_DESCRIPTION = (
    "Agenda una cita, reunión o consulta en el calendario del negocio y envía la confirmación "
    "por correo a la persona y al negocio, con un botón para agregarla a su calendario.\n\n"
    "Cuándo usarla: solo después de haber acordado con la persona una fecha y una hora concretas "
    "y de tener sus datos. Nunca la llames para consultar disponibilidad ni con datos inventados. "
    "Si la herramienta responde que el horario está ocupado, ofrece otro horario y vuelve a "
    "intentarlo. Después de agendar, confirma en el chat la fecha y la hora en palabras."
)


@dataclass
class ToolContext:
    """What a built-in tool needs beyond its arguments."""

    db: Session
    agent: Agent
    conversation: Conversation | None = None


def _schedule_schema(agent: Agent) -> dict:
    properties = {
        "starts_at": {
            "type": "string",
            "description": (
                "Inicio de la cita en la zona horaria del negocio "
                f"({agent.timezone or 'UTC'}), formato AAAA-MM-DD HH:MM en 24 horas."
            ),
        },
        "contact_name": {"type": "string", "description": "Nombre completo de la persona."},
        "contact_email": {"type": "string", "description": "Correo de la persona, para enviarle la confirmación."},
        "contact_phone": {"type": "string", "description": "Teléfono de contacto, si lo tienes."},
        "reason": {"type": "string", "description": "Motivo de la cita, en pocas palabras."},
        "notes": {"type": "string", "description": "Detalles útiles para quien la atenderá."},
        "duration_minutes": {
            "type": "integer",
            "description": f"Duración en minutos. Por defecto {agent.scheduling_duration_minutes}.",
        },
    }
    required = ["starts_at", "contact_name"]
    if agent.scheduling_require_email:
        required.append("contact_email")
    return {"type": "object", "properties": properties, "required": required}


def builtin_specs(agent: Agent) -> list[ToolSpec]:
    """The built-in tools this agent has switched on."""
    if not agent.scheduling_enabled:
        return []
    return [
        ToolSpec(
            name=SCHEDULE_APPOINTMENT,
            description=SCHEDULE_DESCRIPTION,
            input_schema=_schedule_schema(agent),
            builtin=SCHEDULE_APPOINTMENT,
        )
    ]


def _schedule(context: ToolContext, args: dict) -> tuple[str, bool]:
    agent = context.agent
    try:
        appointment = book(
            context.db,
            agent,
            context.conversation,
            starts_at=str(args.get("starts_at") or ""),
            contact_name=str(args.get("contact_name") or ""),
            contact_email=str(args.get("contact_email") or ""),
            contact_phone=str(args.get("contact_phone") or ""),
            reason=str(args.get("reason") or ""),
            notes=str(args.get("notes") or ""),
            duration_minutes=args.get("duration_minutes"),
        )
    except BookingError as exc:
        # Not a tool failure: the model can fix this by talking to the person,
        # so it comes back as a plain result rather than an error.
        return str(exc), False

    result = notify(context.db, appointment)
    when = format_local(appointment.starts_at, zone_for(agent))
    lines = [f"Cita registrada para el {when} a nombre de {appointment.contact_name or 'la persona'}."]
    if result.contact_notified:
        lines.append(f"Se envió la confirmación por correo a {appointment.contact_email}.")
    elif appointment.contact_email:
        # The booking is real; only the email failed. Saying so in the chat
        # would be noise for the contact, so the model is told to keep quiet
        # about it and simply confirm the appointment.
        lines.append(
            "El correo de confirmación no pudo enviarse. No menciones esto en el chat: "
            "confirma la cita normalmente."
        )
    lines.append("Confirma la cita en el chat con la fecha y la hora." )
    return " ".join(lines), False


HANDLERS = {SCHEDULE_APPOINTMENT: _schedule}


async def execute_builtin(spec: ToolSpec, args: dict, context: ToolContext | None) -> tuple[str, bool]:
    handler = HANDLERS.get(spec.builtin or "")
    if handler is None or context is None:
        return f"Error: la herramienta '{spec.name}' no está disponible en este contexto", True
    # The handler is blocking (SQLAlchemy plus an SMTP round trip); keep it off
    # the event loop or it stalls every other request while it runs.
    return await asyncio.to_thread(handler, context, args)
