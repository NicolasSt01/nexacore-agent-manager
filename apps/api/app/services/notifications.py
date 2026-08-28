"""Quota notification emails.

Two audiences, two messages, because they need different things:

- The **seller** gets an alert with the client's contact details attached, so
  they can pick up the phone immediately and sell more package. This is a sales
  trigger, not a system log.
- The **client** gets a heads-up in their own language about their consumption,
  so the block is never a surprise.

Copy is in Spanish on purpose: it is end-user facing, like the UI and the
agent's system prompt.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Client, User
from .billing import get_quota_status
from .mailer import get_settings_row, send_email


logger = logging.getLogger("nexacore.notifications")


def _fmt(number: int) -> str:
    return f"{number:,}".replace(",", ",")


def _client_link(client: Client) -> str:
    return f"{get_settings().frontend_url.rstrip('/')}/clients/{client.id}"


def _seller(db: Session, client: Client) -> User | None:
    if not client.created_by_user_id:
        return None
    return db.scalar(select(User).where(User.id == client.created_by_user_id))


def _client_facts(db: Session, client: Client) -> str:
    """The block a seller needs to act without opening the app."""
    status = get_quota_status(db, client)
    return "\n".join(
        [
            f"  Cliente:        {client.name}",
            f"  Giro:           {client.industry or 'sin especificar'}",
            f"  Correo portal:  {client.portal_email or 'sin configurar'}",
            f"  Plan:           {client.billing_mode} — ${client.monthly_fee_mxn} MXN/mes",
            f"  Límite:         {_fmt(status['limit_tokens'])} tokens por ciclo",
            f"  Consumido:      {_fmt(status['used_tokens'])} tokens ({status['percentage_used']}%)",
            f"  Ciclo:          {status['cycle_start']:%d/%m/%Y} al {status['cycle_end']:%d/%m/%Y}",
            f"  Ficha:          {_client_link(client)}",
        ]
    )


def notify_quota_warning(db: Session, client: Client) -> None:
    """80% of the package consumed: time to sell more, before service stops."""
    settings_row = get_settings_row(db, client.agency_id)
    status = get_quota_status(db, client)
    seller = _seller(db, client)

    if not settings_row or settings_row.notify_seller_on_quota:
        recipients = [address for address in [seller.email if seller else None] if address]
        if settings_row and settings_row.owner_alert_email:
            recipients.append(settings_row.owner_alert_email)
        send_email(
            db,
            client.agency_id,
            to=recipients,
            subject=f"[Acción] {client.name} va en {status['percentage_used']}% de su paquete",
            body_text=(
                f"Hola{' ' + seller.name.split()[0] if seller else ''},\n\n"
                f"Tu cliente {client.name} ya consumió el {status['percentage_used']}% de su paquete "
                f"de tokens del ciclo actual.\n\n"
                "Cuando se agote, su agente dejará de responder automáticamente y las conversaciones "
                "pasarán a atención manual. Es buen momento para contactarlo y ofrecerle subir de plan.\n\n"
                "Datos para el contacto:\n"
                f"{_client_facts(db, client)}\n\n"
                "— NexaCore Agent Manager"
            ),
            reply_to=client.portal_email,
        )

    if (not settings_row or settings_row.notify_client_on_quota) and client.portal_email:
        send_email(
            db,
            client.agency_id,
            to=[client.portal_email],
            subject="Su paquete de mensajes está por agotarse",
            body_text=(
                f"Hola,\n\n"
                f"Le escribimos para avisarle que {client.name} ya utilizó el "
                f"{status['percentage_used']}% de su paquete de mensajes del ciclo actual, que termina "
                f"el {status['cycle_end']:%d/%m/%Y}.\n\n"
                "Si se agota antes de esa fecha, su asistente dejará de responder automáticamente y los "
                "mensajes deberán atenderse de forma manual desde su portal.\n\n"
                "Si desea ampliar su paquete, responda este correo o contacte a su asesor"
                f"{' (' + seller.name + ', ' + seller.email + ')' if seller else ''}.\n\n"
                "— NexaCore"
            ),
            reply_to=seller.email if seller else None,
        )


def notify_quota_blocked(db: Session, client: Client) -> None:
    """The package is spent and automatic replies have stopped."""
    settings_row = get_settings_row(db, client.agency_id)
    status = get_quota_status(db, client)
    seller = _seller(db, client)

    if not settings_row or settings_row.notify_seller_on_quota:
        recipients = [address for address in [seller.email if seller else None] if address]
        if settings_row and settings_row.owner_alert_email:
            recipients.append(settings_row.owner_alert_email)
        send_email(
            db,
            client.agency_id,
            to=recipients,
            subject=f"[Urgente] {client.name} agotó su paquete — el agente dejó de responder",
            body_text=(
                f"Hola{' ' + seller.name.split()[0] if seller else ''},\n\n"
                f"Tu cliente {client.name} agotó su paquete de tokens. Su agente ya NO está respondiendo "
                "automáticamente y las conversaciones nuevas pasan a atención manual.\n\n"
                "Contáctalo hoy: cada hora que pase son prospectos suyos sin respuesta.\n\n"
                "Datos para el contacto:\n"
                f"{_client_facts(db, client)}\n\n"
                "— NexaCore Agent Manager"
            ),
            reply_to=client.portal_email,
        )

    if (not settings_row or settings_row.notify_client_on_quota) and client.portal_email:
        send_email(
            db,
            client.agency_id,
            to=[client.portal_email],
            subject="Su paquete de mensajes se agotó",
            body_text=(
                "Hola,\n\n"
                f"El paquete de mensajes de {client.name} se agotó "
                f"({_fmt(status['used_tokens'])} de {_fmt(status['limit_tokens'])} tokens del ciclo).\n\n"
                "A partir de este momento su asistente dejó de responder automáticamente. Los mensajes "
                "que lleguen se siguen registrando y puede contestarlos usted mismo desde su portal, "
                "pero no recibirán respuesta inmediata.\n\n"
                "Para reactivar el servicio, responda este correo o contacte a su asesor"
                f"{' (' + seller.name + ', ' + seller.email + ')' if seller else ''}.\n\n"
                "— NexaCore"
            ),
            reply_to=seller.email if seller else None,
        )


def notify_pool_pressure(db: Session, agency_id, provider: str, percent: float, windows: dict) -> None:
    """Alert the owner that the shared subscription pool is filling up.

    This is the one alert that is not about a single client: when this pool
    runs out, every client on the key stops at the same time.
    """
    settings_row = get_settings_row(db, agency_id)
    recipient = (settings_row.owner_alert_email if settings_row else "") or ""
    if not recipient:
        return

    detail = []
    for name, window in (windows or {}).items():
        if isinstance(window, dict):
            detail.append(
                f"  · {name:<9} {window.get('percent', 0):>5.1f}%  (resetea {window.get('resetsAt', '?')})"
            )

    send_email(
        db,
        agency_id,
        to=[recipient],
        subject=f"[Suscripción] {provider} va en {percent:.0f}% de su bolsa",
        body_text=(
            f"La bolsa compartida de {provider} va en {percent:.0f}%.\n\n"
            "Recuerda que esta bolsa la comparten TODOS los clientes que usan esa llave: "
            "si se agota, sus agentes dejan de responder al mismo tiempo, aunque ninguno "
            "haya excedido su propio plan.\n\n"
            "Detalle por ventana:\n" + ("\n".join(detail) or "  (sin detalle)") + "\n\n"
            "Opciones:\n"
            "  1. Contratar otra suscripción y repartir clientes entre las dos.\n"
            "  2. Mover clientes de alto volumen a un modelo que rinda más.\n"
            "  3. Esperar al reseteo de la ventana más apretada.\n\n"
            "El sistema degradará solo al llegar al umbral configurado.\n\n"
            "— NexaCore Agent Manager"
        ),
    )
