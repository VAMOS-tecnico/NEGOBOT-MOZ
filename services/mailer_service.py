"""Envio SMTP mínimo e server-side para o Mailer Worker."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any


def send_email(to: str, subject: str, body: str, *, html: str | None = None) -> dict[str, Any]:
    recipient = str(to or "").strip()
    if not recipient:
        raise ValueError("recipient_obrigatorio")
    host = str(os.getenv("SMTP_HOST") or "").strip()
    sender = str(os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "").strip()
    password = str(os.getenv("SMTP_PASSWORD") or "")
    if not host or not sender:
        raise RuntimeError("smtp_not_configured")
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        timeout = max(5, min(int(os.getenv("SMTP_TIMEOUT_SECONDS", "20")), 60))
    except ValueError as exc:
        raise RuntimeError("smtp_configuration_invalid") from exc
    use_tls = str(os.getenv("SMTP_USE_TLS", "true")).strip().lower() not in {"0", "false", "no"}
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = str(subject or "NEGOBOT MOZ")[:200]
    message.set_content(str(body or ""))
    if html:
        message.add_alternative(str(html), subtype="html")
    with smtplib.SMTP(host, port, timeout=timeout) as server:
        if use_tls:
            server.starttls()
        if os.getenv("SMTP_USER") and password:
            server.login(str(os.getenv("SMTP_USER")), password)
        server.send_message(message)
    return {"sent": True, "recipient": recipient}
