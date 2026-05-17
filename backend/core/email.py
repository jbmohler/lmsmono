"""Email sending via SMTP."""

import smtplib
from email.message import EmailMessage

from core.config import SmtpConfig


def send_password_reset_email(
    smtp: SmtpConfig,
    to_address: str,
    username: str,
    reset_url: str,
) -> None:
    """Send a password reset email to the given address."""
    msg = EmailMessage()
    msg["Subject"] = "LMS Password Reset"
    msg["From"] = smtp.from_address
    msg["To"] = to_address
    msg.set_content(
        f"Hi {username},\n\n"
        f"A password reset was requested for your account.\n\n"
        f"Click the link below to set a new password (valid for 2 hours):\n\n"
        f"  {reset_url}\n\n"
        f"If you did not request this, you can ignore this email.\n"
    )

    with smtplib.SMTP(smtp.host, smtp.port) as server:
        if smtp.use_tls:
            server.starttls()
        if smtp.username:
            server.login(smtp.username, smtp.password)
        server.send_message(msg)
