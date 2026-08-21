"""Integração segura entre o worker NEGOBOT e webhooks n8n.

O n8n deve usar um Webhook node em modo de produção com Header Auth. O valor
configurado no header `X-NEGOBOT-Signature` é o segredo partilhado, guardado
apenas no n8n e no Campaign Worker.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

import requests

logger = logging.getLogger("negobot-n8n")


def configured() -> bool:
    return bool(os.getenv("N8N_CAMPAIGN_WEBHOOK_URL", "").strip() and os.getenv("N8N_WEBHOOK_SECRET", "").strip())


def dispatch_campaign_event(event: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    """Envia um evento de campanha ao n8n com retries seguros.

    O corpo inclui `request_id` para correlação e o header secreto impede que
    uma chamada externa injete tarefas na automação sem conhecer o segredo.
    """
    url = os.getenv("N8N_CAMPAIGN_WEBHOOK_URL", "").strip()
    secret = os.getenv("N8N_WEBHOOK_SECRET", "").strip()
    if not url or not secret:
        return {"sent": False, "configured": False, "reason": "n8n_not_configured"}
    correlation_id = request_id or uuid.uuid4().hex
    body = {"event": event, "request_id": correlation_id, "sent_at": time.time(), **payload}
    raw_body = json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-NEGOBOT-Event": event,
        "X-NEGOBOT-Request-ID": correlation_id,
        "X-NEGOBOT-Signature": secret,
    }
    retries = max(1, min(4, int(os.getenv("N8N_WEBHOOK_RETRIES", "3"))))
    timeout = max(3, min(30, int(os.getenv("N8N_WEBHOOK_TIMEOUT", "12"))))
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, data=raw_body, headers=headers, timeout=timeout)
            if 200 <= response.status_code < 300:
                return {"sent": True, "configured": True, "request_id": correlation_id, "status_code": response.status_code, "attempt": attempt}
            last_error = f"HTTP {response.status_code}"
            if response.status_code < 500:
                break
        except requests.RequestException as exc:
            last_error = str(exc)
        if attempt < retries:
            time.sleep(min(2 ** (attempt - 1), 4))
    logger.warning("Falha ao enviar evento %s ao n8n request_id=%s: %s", event, correlation_id, last_error)
    return {"sent": False, "configured": True, "request_id": correlation_id, "error": last_error, "attempts": retries}
