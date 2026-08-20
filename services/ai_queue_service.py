"""Cliente tenant-scoped para o AI Worker.

O Backend não conhece fornecedores nem chaves de IA. Publica um envelope comum
em Redis e aguarda apenas o resultado identificado pelo mesmo job_id e tenant_id.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

try:
    import redis
except ImportError:  # pragma: no cover - o runtime de produção instala redis
    redis = None


AI_QUEUE = os.getenv("AI_QUEUE", "negobot:ai_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
RESULT_TTL_SECONDS = 24 * 60 * 60


class AIQueueError(RuntimeError):
    """Indica que o job não pôde ser publicado ou concluído."""


def _client():
    if redis is None:
        raise AIQueueError("redis_indisponivel")
    return redis.from_url(REDIS_URL, decode_responses=True)


def _result_key(job_id: str) -> str:
    return f"negobot:ai:result:{job_id}"


def request_ai_text(
    *,
    tenant_id: str,
    messages: list[dict[str, Any]],
    system_prompt: str = "",
    request_id: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Enfileira uma geração e devolve o resultado do AI Worker.

    O método é síncrono para preservar o contrato actual dos fluxos WhatsApp e
    web, mas todo o processamento de fornecedor ocorre no worker dedicado.
    """
    tenant = str(tenant_id or "").strip()[:160]
    if not tenant:
        raise AIQueueError("tenant_id_obrigatorio")
    if not isinstance(messages, list) or not messages:
        raise AIQueueError("messages_obrigatorias")

    job_id = str(request_id or uuid.uuid4().hex).strip()[:160]
    try:
        timeout = float(timeout_seconds if timeout_seconds is not None else os.getenv("AI_RESPONSE_TIMEOUT_SECONDS", "30"))
    except (TypeError, ValueError):
        timeout = 30.0
    timeout = max(2.0, min(timeout, 60.0))

    client = _client()
    envelope = {
        "job_id": job_id,
        "tenant_id": tenant,
        "kind": "text_generation",
        "attempt": 1,
        "payload": {
            "messages": messages,
            "system_prompt": str(system_prompt or "")[:12000],
        },
    }
    try:
        client.rpush(AI_QUEUE, json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))
    except Exception as exc:
        raise AIQueueError("ai_queue_unavailable") from exc

    deadline = time.monotonic() + timeout
    key = _result_key(job_id)
    while time.monotonic() < deadline:
        raw = client.get(key)
        if raw:
            try:
                result = json.loads(raw)
            except (TypeError, json.JSONDecodeError) as exc:
                raise AIQueueError("ai_result_invalid") from exc
            if str(result.get("job_id") or "") != job_id or str(result.get("tenant_id") or "") != tenant:
                raise AIQueueError("ai_result_tenant_mismatch")
            return result
        time.sleep(0.2)
    raise AIQueueError("ai_timeout")
