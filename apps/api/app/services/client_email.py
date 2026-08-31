"""Reading and writing one client's email configuration.

Shared by the agency panel (routers/clients.py) and the client's own portal
(routers/portal.py) so both edit the same thing under the same rules — most
importantly that changing a credential drops the verified flag, and that only a
verified server is ever used to deliver.
"""

from sqlalchemy.orm import Session

from ..models import Client, now_utc
from ..security import encrypt_secret
from .mailer import agency_config, client_config, send_client_test_email, send_email


# Touching any of these means the stored credentials are no longer known to
# work, so the client has to pass a test send again before we rely on them.
CREDENTIAL_FIELDS = ("smtp_host", "smtp_port", "smtp_user", "smtp_use_tls", "smtp_from_email")
# Columns that are NOT NULL with an empty default: a cleared form field arrives
# as null and has to land as "", not as a constraint violation.
NON_NULLABLE = ("smtp_host", "smtp_user", "smtp_from_email", "smtp_from_name")


def apply_settings(client: Client, values: dict) -> None:
    """Apply a partial update. `smtp_password` is encrypted; blank keeps the stored one."""
    password = values.pop("smtp_password", None)
    if password:
        client.encrypted_smtp_password = encrypt_secret(password)
        client.smtp_verified_at = None
    for key, value in values.items():
        if value is None and key in NON_NULLABLE:
            value = ""
        if key in ("notification_email", "smtp_from_email") and value:
            value = str(value).lower()
        if key in CREDENTIAL_FIELDS and getattr(client, key) != value:
            client.smtp_verified_at = None
        setattr(client, key, value)
    client.updated_at = now_utc()


def settings_out(db: Session, client: Client) -> dict:
    own = client_config(client)
    return {
        "notification_email": client.notification_email,
        "smtp_enabled": client.smtp_enabled,
        "smtp_host": client.smtp_host,
        "smtp_port": client.smtp_port,
        "smtp_user": client.smtp_user,
        # The password is never returned; only whether one is stored.
        "has_smtp_password": client.smtp_password_configured,
        "smtp_use_tls": client.smtp_use_tls,
        "smtp_from_email": client.smtp_from_email,
        "smtp_from_name": client.smtp_from_name,
        "smtp_verified_at": client.smtp_verified_at,
        "using_own_smtp": own is not None,
        # Whether anything can go out at all: the client's server, or ours.
        "delivery_ready": own is not None or agency_config(db, client.agency_id) is not None,
        "alert_email": client.alert_email,
    }


def send_test(db: Session, client: Client, to: str) -> tuple[bool, str]:
    """Send a test message and report which server carried it.

    A success on the client's own credentials is what marks them verified —
    there is no other moment where we learn they actually work.
    """
    if client.smtp_enabled and client.smtp_host and client.smtp_from_email:
        if send_client_test_email(client, to):
            client.smtp_verified_at = now_utc()
            db.commit()
            return True, "own"
        return False, "own"

    sent = send_email(
        db,
        client.agency_id,
        to=[to],
        sender_name=client.name,
        subject=f"Prueba de configuración de correo — {client.name}",
        body_text=(
            f"Este es un correo de prueba para {client.name}.\n\n"
            "Salió desde el servidor de correo de la plataforma. Si quieres que tus "
            "notificaciones salgan desde tu propia dirección, configura tu servidor SMTP."
        ),
    )
    return sent, "agency"
