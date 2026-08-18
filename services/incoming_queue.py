"""Produtor Redis para mensagens recebidas da Evolution API."""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

try:
    import redis
except ImportError:  # o backend de produção instala redis via requirements.txt
    redis = None

QUEUE_NAME = os.getenv("WHATSAPP_INCOMING_QUEUE", "whatsapp_incoming_queue")
OMNICHANNEL_QUEUE_NAME = os.getenv("OMNICHANNEL_INCOMING_QUEUE", "omnichannel_incoming_queue")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def _redis_client():
    if redis is None:
        raise RuntimeError("Biblioteca redis não instalada")
    return redis.from_url(REDIS_URL, decode_responses=True)


def validate_event(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    event = str(payload.get("event") or "").lower()
    if event not in {"messages.upsert", "messages_upsert"}:
        return True
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return False
    key = data.get("key")
    return isinstance(key, dict) or not data


def _enqueue(payload: dict[str, Any], queue_name: str) -> dict[str, Any]:
    event_id = str(payload.get("event_id") or uuid.uuid4().hex)
    envelope = {
        "event_id": event_id,
        "enqueued_at": time.time(),
        "payload": payload,
    }
    client = _redis_client()
    position = client.rpush(queue_name, json.dumps(envelope, ensure_ascii=False, default=str, separators=(",", ":")))
    return {"queued": True, "event_id": event_id, "queue": queue_name, "position": position}


def enqueue_incoming_event(payload: dict[str, Any]) -> dict[str, Any]:
    if not validate_event(payload):
        raise ValueError("Payload de webhook inválido")
    return _enqueue(payload, QUEUE_NAME)


def enqueue_omnichannel_event(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload.get("tenant_id") or not payload.get("channel"):
        raise ValueError("Evento omnichannel inválido")
    return _enqueue(payload, OMNICHANNEL_QUEUE_NAME)
