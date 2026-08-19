"""Contrato seguro para publicações agendadas em WhatsApp Channels.

A Evolution API actual não tem adaptador documentado para Channels nativos.
Este módulo prepara drafts/agenda e falha fechado antes de qualquer chamada a
sendText ou a um endpoint não suportado.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

try:
    import redis
except ImportError:  # disponível no container de produção
    redis = None

import extensions

logger = logging.getLogger("negobot-channel-publications")
PUBLICATION_QUEUE = os.getenv("CHANNEL_PUBLICATIONS_QUEUE", "negobot:channel-publications")
SCHEDULED_QUEUE = os.getenv("CHANNEL_PUBLICATIONS_SCHEDULED_QUEUE", "negobot:channel-publications:scheduled")
CONTROL_PREFIX = "negobot:channel-publication:"
NEWSLETTER_SUFFIX = "@newsletter"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def validate_cta_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) > 500:
        raise ValueError("O link CTA não pode exceder 500 caracteres.")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("O CTA deve ser um URL absoluto http:// ou https://.")
    return raw


def normalize_channel_jid(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not raw.endswith(NEWSLETTER_SUFFIX) or len(raw) < len(NEWSLETTER_SUFFIX) + 4:
        raise ValueError("O identificador do canal deve terminar em @newsletter.")
    return raw


def channel_capability() -> dict[str, Any]:
    return {
        "key": "whatsapp_newsletter",
        "label": "WhatsApp Channels",
        "status": "pending_authorization",
        "provider": "Evolution API",
        "adapter_configured": False,
        "administrator_verification": False,
        "can_publish": False,
        "reason": "A Evolution API v2.3.7 não expõe um adaptador documentado para listar e publicar em Channels nativos.",
    }


def _redis_client():
    if redis is None:
        raise RuntimeError("Biblioteca redis não instalada")
    return redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/1"), decode_responses=True)


def enqueue_publication(publication_id: str, scheduled_at: datetime | None = None, queue: Any | None = None) -> dict[str, Any]:
    queue = queue or _redis_client()
    if scheduled_at and scheduled_at > now_utc():
        position = queue.zadd(SCHEDULED_QUEUE, {publication_id: scheduled_at.timestamp()})
        return {"queued": True, "scheduled": True, "queue": SCHEDULED_QUEUE, "position": position}
    position = queue.rpush(PUBLICATION_QUEUE, publication_id)
    return {"queued": True, "scheduled": False, "queue": PUBLICATION_QUEUE, "position": position}


def promote_scheduled(queue: Any, moment: datetime | None = None) -> int:
    moment = moment or now_utc()
    due = queue.zrangebyscore(SCHEDULED_QUEUE, 0, moment.timestamp(), start=0, num=50)
    promoted = 0
    for publication_id in due:
        if queue.zrem(SCHEDULED_QUEUE, publication_id):
            queue.rpush(PUBLICATION_QUEUE, publication_id)
            promoted += 1
    return promoted


def control_value(queue: Any, publication_id: str) -> str:
    return str(queue.get(f"{CONTROL_PREFIX}{publication_id}:control") or "").strip().lower()


def add_cta(body: str, cta_label: str | None, cta_url: str | None) -> str:
    if not cta_url:
        return body
    label = str(cta_label or "Saber mais").strip()[:80]
    return f"{body}\n\n{label}: {cta_url}"


def _publication_ref(publication_id: str):
    if extensions.db is None:
        extensions.init_extensions()
    if extensions.db is None:
        raise RuntimeError("Firestore indisponível")
    reference = extensions.db.collection("channel_publications").document(publication_id)
    document = reference.get()
    if not document.exists:
        return None
    return reference, document.to_dict() or {}


def process_publication(publication_id: str, queue: Any) -> None:
    resolved = _publication_ref(publication_id)
    if not resolved:
        logger.warning("Publicação de canal inexistente: %s", publication_id)
        return
    reference, publication = resolved
    status = str(publication.get("status") or "draft").lower()
    if status in {"published", "cancelled", "blocked"}:
        return
    control = control_value(queue, publication_id)
    if control == "cancel":
        reference.set({"status": "cancelled", "updated_at": now_utc()}, merge=True)
        return
    scheduled = parse_datetime(publication.get("scheduled_at"))
    if scheduled and scheduled > now_utc():
        reference.set({"status": "scheduled", "updated_at": now_utc()}, merge=True)
        enqueue_publication(publication_id, scheduled, queue=queue)
        return

    # Fail closed: never call Evolution sendText for @newsletter without adapter.
    capability = channel_capability()
    reference.set({
        "status": "blocked",
        "delivery_status": "outbound_adapter_not_configured",
        "adapter_status": capability["status"],
        "authorization_status": "pending_authorization",
        "administrator_verified": False,
        "last_error": capability["reason"],
        "updated_at": now_utc(),
    }, merge=True)
    logger.warning("Publicação %s bloqueada: adapter de Channels não configurado", publication_id)


def create_publication_data(payload: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or payload.get("message") or "").strip()
    if not 2 <= len(title) <= 160:
        raise ValueError("O título deve ter entre 2 e 160 caracteres.")
    if not 1 <= len(body) <= 4000:
        raise ValueError("O conteúdo deve ter entre 1 e 4000 caracteres.")
    cta_url = validate_cta_url(payload.get("cta_url"))
    cta_label = str(payload.get("cta_label") or "Saber mais").strip()[:80] if cta_url else None
    channel_jid = normalize_channel_jid(payload.get("channel_jid"))
    scheduled_at = parse_datetime(payload.get("scheduled_at"))
    status = "scheduled" if scheduled_at and scheduled_at > now_utc() else "draft"
    return {
        "tenant_id": tenant_id,
        "channel_type": "whatsapp_newsletter",
        "channel_jid": channel_jid,
        "channel_name": str(payload.get("channel_name") or "").strip()[:160] or None,
        "title": title,
        "body": body,
        "rendered_body": add_cta(body, cta_label, cta_url),
        "cta_url": cta_url,
        "cta_label": cta_label,
        "scheduled_at": scheduled_at,
        "timezone": str(payload.get("timezone") or "Africa/Maputo").strip()[:80],
        "status": status,
        "delivery_status": "not_queued" if status == "draft" else "queued",
        "adapter_status": "pending_authorization",
        "authorization_status": "pending_authorization",
        "administrator_verified": False,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
