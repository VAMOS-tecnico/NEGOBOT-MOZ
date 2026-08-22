"""Consumidor persistente da fila de mensagens WhatsApp."""
from __future__ import annotations

import json
import logging
import os
import time

import extensions

try:
    import redis
except ImportError:  # instalado no container pelo requirements.txt
    redis = None

from routes.webhook_routes import processar_webhook_background
from services.group_automation_service import purge_archived_groups
from services.incoming_queue import OMNICHANNEL_QUEUE_NAME, QUEUE_NAME
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-incoming-worker")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def _ensure_firestore() -> None:
    """Inicializa o Firestore no processo persistente antes de tratar mensagens."""
    if extensions.db is None:
        initialized_db = extensions.init_extensions()
        if extensions.db is None and initialized_db is not None:
            extensions.db = initialized_db
    if extensions.db is None:
        raise RuntimeError("Firestore não foi inicializado no worker")


def process_queue_item(item) -> bool:
    """Processa um item BLPOP e devolve se foi aceite pelo consumer."""
    try:
        envelope = json.loads(item[1])
        payload = envelope.get("payload") if isinstance(envelope, dict) else None
        if not isinstance(payload, dict):
            logger.warning("Envelope inválido descartado")
            return False
        enqueued_at = float(envelope.get("enqueued_at") or time.time())
        payload["_negobot_queue_enqueued_at"] = enqueued_at
        logger.info("Mensagem retirada da fila event_id=%s wait_ms=%d", envelope.get("event_id"), int((time.time() - enqueued_at) * 1000))
        processar_webhook_background(payload)
        return True
    except Exception:
        logger.exception("Falha ao processar item da fila WhatsApp")
        return False


def process_omnichannel_queue_item(item) -> bool:
    """Persiste o evento normalizado sem afirmar que houve resposta externa."""
    try:
        envelope = json.loads(item[1])
        payload = envelope.get("payload") if isinstance(envelope, dict) else None
        if not isinstance(payload, dict):
            logger.warning("Envelope omnichannel inválido descartado")
            return False
        _ensure_firestore()
        event_id = str(payload.get("event_id") or envelope.get("event_id") or "")
        tenant_id = str(payload.get("tenant_id") or "")
        channel = str(payload.get("channel") or "")
        if not event_id or not tenant_id or not channel:
            logger.warning("Evento omnichannel sem identidade descartado")
            return False
        now = time.time()
        event_ref = extensions.db.collection("omnichannel_events").document(event_id)
        event_ref.set({
            "tenant_id": tenant_id,
            "channel": channel,
            "status": "manual_review",
            "processing_status": "outbound_adapter_not_configured",
            "processed_at": now,
        }, merge=True)
        extensions.db.collection("omnichannel_messages").document(event_id).set({
            "tenant_id": tenant_id,
            "channel": channel,
            "conversation_id": payload.get("conversation_id"),
            "contact_external_id": payload.get("contact_external_id"),
            "message_id": payload.get("message_id"),
            "text": payload.get("text", ""),
            "direction": "inbound",
            "status": "manual_review",
            "received_at": payload.get("received_at"),
            "created_at": now,
        }, merge=True)
        logger.info("Evento omnichannel persistido event_id=%s channel=%s status=manual_review", event_id, channel)
        return True
    except Exception:
        logger.exception("Falha ao processar item da fila omnichannel")
        return False


def main() -> None:
    if redis is None:
        raise RuntimeError("Biblioteca redis não instalada")
    enforce_profile("whatsapp_ingress")
    _ensure_firestore()
    client = redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    logger.info("Consumidor online queues=%s,%s", QUEUE_NAME, OMNICHANNEL_QUEUE_NAME)
    last_group_cleanup = 0.0
    while True:
        now = time.time()
        if now - last_group_cleanup >= 300:
            try:
                removed = purge_archived_groups()
                if removed:
                    logger.info("Limpeza de grupos arquivados: %d documento(s) removido(s)", removed)
            except Exception:
                logger.exception("Falha na limpeza de grupos arquivados; o consumo continua")
            last_group_cleanup = now
        item = client.blpop([QUEUE_NAME, OMNICHANNEL_QUEUE_NAME], timeout=30)
        if item:
            if item[0] == OMNICHANNEL_QUEUE_NAME:
                process_omnichannel_queue_item(item)
            else:
                process_queue_item(item)


if __name__ == "__main__":
    main()
