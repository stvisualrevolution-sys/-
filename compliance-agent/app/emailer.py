from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


class EmailConfigError(Exception):
    pass


def send_email(subject: str, body: str, to_email: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not host or not from_email:
        raise EmailConfigError("SMTP_HOST and SMTP_FROM are required")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=15) as server:
        if use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(msg)
