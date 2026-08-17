"""Consumidor persistente da fila de mensagens WhatsApp."""
from __future__ import annotations

import json
import logging
import os
import time

try:
    import redis
except ImportError:  # instalado no container pelo requirements.txt
    redis = None

from routes.webhook_routes import processar_webhook_background

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-incoming-worker")
QUEUE_NAME = os.getenv("WHATSAPP_INCOMING_QUEUE", "whatsapp_incoming_queue")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


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


def main() -> None:
    if redis is None:
        raise RuntimeError("Biblioteca redis não instalada")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    logger.info("Consumidor online queue=%s", QUEUE_NAME)
    while True:
        item = client.blpop(QUEUE_NAME, timeout=30)
        if item:
            process_queue_item(item)


if __name__ == "__main__":
    main()
