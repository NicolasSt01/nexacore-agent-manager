"""Outbound email.

Two levels of credentials, resolved in order:

1. The **client's own SMTP**, when they configured it and a test send verified
   it. Their mail then leaves from their own address.
2. The **agency's SMTP**, superadmin-managed (see AgencySettings). This is the
   default every client falls back to, so a client that never configures
   anything still gets their notifications delivered.

When neither is available the mailer is a no-op that logs and returns False, so
local runs and tests never send anything and a missing SMTP host can never break
message delivery.

Sending on behalf of a client through the agency's server never puts the
client's address in `From:` — the agency's domain signs the message, and a
mismatched From is what gets mail rejected or filed as spam. The client's name
goes in the display name and their address in `Reply-To` instead.
"""

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AgencySettings, Client
from ..security import decrypt_secret


logger = logging.getLogger("nexacore.mailer")

SMTP_TIMEOUT = 20


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: str
    subtype: str = "plain"
    params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MailerConfig:
    host: str
    port: int
    user: str
    password: str
    use_tls: bool
    from_email: str
    from_name: str
    # "client" when the client's own server is being used, "agency" otherwise.
    source: str = "agency"


def get_settings_row(db: Session, agency_id) -> AgencySettings | None:
    return db.scalar(select(AgencySettings).where(AgencySettings.agency_id == agency_id))


def agency_config(db: Session, agency_id) -> MailerConfig | None:
    row = get_settings_row(db, agency_id)
    if not row or not row.emails_enabled:
        return None
    if not row.smtp_host or not row.smtp_from_email:
        return None
    return MailerConfig(
        host=row.smtp_host,
        port=row.smtp_port,
        user=row.smtp_user,
        password=decrypt_secret(row.encrypted_smtp_password) if row.encrypted_smtp_password else "",
        use_tls=row.smtp_use_tls,
        from_email=row.smtp_from_email,
        from_name=row.smtp_from_name,
        source="agency",
    )


def client_config(client: Client | None, *, require_verified: bool = True) -> MailerConfig | None:
    """The client's own SMTP, or None to fall back to the agency's.

    `require_verified` is lifted only by the test-send endpoint: that is the
    call that decides whether the credentials work at all.
    """
    if client is None or not client.smtp_enabled:
        return None
    if not client.smtp_host or not client.smtp_from_email:
        return None
    if require_verified and not client.smtp_verified_at:
        return None
    return MailerConfig(
        host=client.smtp_host,
        port=client.smtp_port,
        user=client.smtp_user,
        password=decrypt_secret(client.encrypted_smtp_password) if client.encrypted_smtp_password else "",
        use_tls=client.smtp_use_tls,
        from_email=client.smtp_from_email,
        from_name=client.smtp_from_name or client.name,
        source="client",
    )


def resolve_config(db: Session, agency_id, client: Client | None = None) -> MailerConfig | None:
    return client_config(client) or agency_config(db, agency_id)


def _from_header(config: MailerConfig, sender_name: str | None) -> str:
    """`From:` for this message, keeping the envelope domain honest.

    On the agency's server the address stays the agency's; the client's name is
    appended to the display name so the recipient still sees who is writing.
    """
    display = (sender_name or "").strip() or config.from_name
    if config.source == "agency" and sender_name and config.from_name and sender_name.strip() != config.from_name:
        display = f"{sender_name.strip()} vía {config.from_name}"
    return f"{display} <{config.from_email}>" if display else config.from_email


def send_with_config(
    config: MailerConfig,
    *,
    to: list[str],
    subject: str,
    body_text: str,
    body_html: str | None = None,
    reply_to: str | None = None,
    sender_name: str | None = None,
    attachments: list[Attachment] | None = None,
) -> bool:
    """Send through an already-resolved server. Never raises."""
    recipients = [address for address in to if address and address.strip()]
    if not recipients:
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _from_header(config, sender_name)
    message["To"] = ", ".join(recipients)
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")
    for attachment in attachments or []:
        message.add_attachment(
            attachment.content,
            subtype=attachment.subtype,
            filename=attachment.filename,
            params=attachment.params or None,
        )

    try:
        if config.port == 465:
            server = smtplib.SMTP_SSL(config.host, config.port, timeout=SMTP_TIMEOUT)
        else:
            server = smtplib.SMTP(config.host, config.port, timeout=SMTP_TIMEOUT)
        with server:
            if config.use_tls and config.port != 465:
                server.starttls()
            if config.user:
                server.login(config.user, config.password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Could not send '%s' via %s: %s", subject, config.host, exc)
        return False
    return True


def send_email(
    db: Session,
    agency_id,
    *,
    to: list[str],
    subject: str,
    body_text: str,
    body_html: str | None = None,
    reply_to: str | None = None,
    client: Client | None = None,
    sender_name: str | None = None,
    attachments: list[Attachment] | None = None,
) -> bool:
    """Send one message. Returns False when email is off or the send failed.

    Never raises: a notification must not be able to break the flow that
    triggered it.
    """
    config = resolve_config(db, agency_id, client)
    if not config:
        logger.info("Email disabled or unconfigured; skipping '%s'", subject)
        return False
    return send_with_config(
        config,
        to=to,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        reply_to=reply_to,
        sender_name=sender_name,
        attachments=attachments,
    )


def send_test_email(db: Session, agency_id, to: str) -> bool:
    return send_email(
        db,
        agency_id,
        to=[to],
        subject="Prueba de configuración de correo — NexaCore",
        body_text=(
            "Este es un correo de prueba de NexaCore Agent Manager.\n\n"
            "Si lo estás leyendo, la configuración SMTP quedó correcta."
        ),
    )


def send_client_test_email(client: Client, to: str) -> bool:
    """Verify a client's own SMTP. Uses the credentials as entered, verified or
    not — this send is what decides whether they work."""
    config = client_config(client, require_verified=False)
    if not config:
        return False
    return send_with_config(
        config,
        to=[to],
        subject=f"Prueba de configuración de correo — {client.name}",
        body_text=(
            f"Este es un correo de prueba enviado desde el servidor de correo de {client.name}.\n\n"
            "Si lo estás leyendo, las credenciales SMTP quedaron correctas y las "
            "notificaciones saldrán desde esta dirección."
        ),
    )
