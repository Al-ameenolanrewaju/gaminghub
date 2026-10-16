import os
import smtplib
from email.message import EmailMessage


class EmailConfigurationError(RuntimeError):
    """Raised when outbound mail is not configured."""


def _configuration():
    host = os.environ.get("MAIL_SERVER", "").strip()
    username = os.environ.get("MAIL_USERNAME", "").strip()
    password = os.environ.get("MAIL_PASSWORD", "")
    sender = os.environ.get("MAIL_DEFAULT_SENDER", username).strip()
    if not host or not sender:
        raise EmailConfigurationError(
            "Set MAIL_SERVER and MAIL_DEFAULT_SENDER (or MAIL_USERNAME) to enable email."
        )

    try:
        port = int(os.environ.get("MAIL_PORT", "587"))
    except ValueError as error:
        raise EmailConfigurationError("MAIL_PORT must be a valid TCP port.") from error
    if not 1 <= port <= 65535:
        raise EmailConfigurationError("MAIL_PORT must be between 1 and 65535.")
    use_ssl = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    default_tls = "false" if use_ssl else "true"
    use_tls = os.environ.get("MAIL_USE_TLS", default_tls).lower() == "true"
    if use_ssl and use_tls:
        raise EmailConfigurationError("Enable only one of MAIL_USE_SSL or MAIL_USE_TLS.")
    return host, port, username, password, sender, use_ssl, use_tls


def validate_email_configuration():
    _configuration()


def send_email(recipient, subject, body, *, reply_to=None):
    host, port, username, password, sender, use_ssl, use_tls = _configuration()

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=15) as server:
        if use_tls and not use_ssl:
            server.starttls()
        if username:
            server.login(username, password)
        server.send_message(message)
