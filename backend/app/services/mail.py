"""Plain-text emails over SMTP (stdlib only). See the MAIL_* settings in config.py."""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app

SMTP_TIMEOUT_SECONDS = 15


def send(to, subject, body):
    """Send one email. Returns True if it was handed to the mail server, False otherwise.

    Never raises: a failed email must not undo the staff decision that triggered it.
    """
    config = current_app.config
    if config.get("MAIL_SUPPRESS"):
        current_app.extensions.setdefault("mail_outbox", []).append(
            {"to": to, "subject": subject, "body": body}
        )
        return True
    if not config.get("MAIL_USERNAME"):
        current_app.logger.warning("MAIL_USERNAME is not set: email to %s not sent.", to)
        return False

    message = EmailMessage()
    message["From"] = formataddr(
        ("Lab Absence Manager", config.get("MAIL_SENDER") or config["MAIL_USERNAME"])
    )
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(config["MAIL_SERVER"], config["MAIL_PORT"],
                          timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.starttls()
            smtp.login(config["MAIL_USERNAME"], config["MAIL_PASSWORD"] or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("Sending email to %s failed.", to)
        return False
    return True
