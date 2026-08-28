"""Outbound email.

SMTP credentials are per agency and superadmin-managed (see AgencySettings).
When email is not configured the mailer is a no-op that logs and returns False,
so local runs and tests never send anything and a missing SMTP host can never
break message delivery.
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AgencySettings
from ..security import decrypt_secret


logger = logging.getLogger("nexacore.mailer")

SMTP_TIMEOUT = 20


@dataclass(frozen=True)
class MailerConfig:
    host: str
    port: int
    user: str
    password: str
    use_tls: bool
    from_email: str
    from_name: str


def get_settings_row(db: Session, agency_id) -> AgencySettings | None:
    return db.scalar(select(AgencySettings).where(AgencySettings.agency_id == agency_id))


def _config(db: Session, agency_id) -> MailerConfig | None:
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
    )


def send_email(
    db: Session,
    agency_id,
    *,
    to: list[str],
    subject: str,
    body_text: str,
    body_html: str | None = None,
    reply_to: str | None = None,
) -> bool:
    """Send one message. Returns False when email is off or the send failed.

    Never raises: a notification must not be able to break the flow that
    triggered it.
    """
    recipients = [address for address in to if address and address.strip()]
    if not recipients:
        return False
    config = _config(db, agency_id)
    if not config:
        logger.info("Email disabled or unconfigured; skipping '%s'", subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{config.from_name} <{config.from_email}>" if config.from_name else config.from_email
    message["To"] = ", ".join(recipients)
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")

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
        logger.warning("Could not send '%s': %s", subject, exc)
        return False
    return True


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
