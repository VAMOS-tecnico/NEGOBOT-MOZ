"""Produtor tenant-scoped para o Mailer Worker."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None


MAIL_QUEUE = os.getenv("MAIL_QUEUE", "negobot:mail_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


class MailQueueError(RuntimeError):
    """Indica que o e-mail não pôde ser publicado na fila."""


def _client():
    if redis is None:
        raise MailQueueError("redis_indisponivel")
    return redis.from_url(REDIS_URL, decode_responses=True)


def enqueue_email(
    *,
    tenant_id: str,
    recipient: str,
    subject: str,
    body: str,
    html: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()[:160]
    to = str(recipient or "").strip()[:320]
    if not tenant:
        raise MailQueueError("tenant_id_obrigatorio")
    if not to:
        raise MailQueueError("recipient_obrigatorio")
    job_id = str(request_id or uuid.uuid4().hex).strip()[:160]
    envelope = {
        "job_id": job_id,
        "tenant_id": tenant,
        "kind": "email_delivery",
        "attempt": 1,
        "payload": {
            "to": to,
            "subject": str(subject or "NEGOBOT MOZ")[:300],
            "body": str(body or "")[:20000],
            "html": str(html)[:30000] if html else None,
        },
    }
    try:
        position = _client().rpush(MAIL_QUEUE, json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))
    except Exception as exc:
        raise MailQueueError("mail_queue_unavailable") from exc
    return {"queued": True, "job_id": job_id, "tenant_id": tenant, "position": position}
