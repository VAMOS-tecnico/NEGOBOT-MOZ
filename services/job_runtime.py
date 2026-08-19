"""Runtime comum para workers Redis do NEGOBOT MOZ.

O runtime não conhece regras de negócio. Valida apenas o envelope comum, mantém
estado idempotente por job e garante que cada handler recebe um tenant_id explícito.
Não escreve payloads ou segredos nos logs.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any


logger = logging.getLogger("negobot-job-runtime")


class JobContractError(ValueError):
    """Indica um job inválido ou incompleto."""


class JobManualReview(RuntimeError):
    """Indica que o adaptador ainda não pode executar o job automaticamente."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def validate_job(raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        job = dict(raw)
    else:
        try:
            job = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise JobContractError("job_json_invalido") from exc
    if not isinstance(job, dict):
        raise JobContractError("job_deve_ser_objecto")
    for field in ("job_id", "tenant_id", "kind"):
        if not str(job.get(field) or "").strip():
            raise JobContractError(f"campo_obrigatorio:{field}")
    job["job_id"] = str(job["job_id"]).strip()[:160]
    job["tenant_id"] = str(job["tenant_id"]).strip()[:160]
    job["kind"] = str(job["kind"]).strip()[:160]
    job["attempt"] = max(1, int(job.get("attempt") or 1))
    return job


def _state_key(profile: str, job_id: str) -> str:
    return f"negobot:job:{profile}:{job_id}"


def _save_state(client: Any, profile: str, job: dict[str, Any], status: str, **fields: Any) -> None:
    values = {
        "job_id": job["job_id"],
        "tenant_id": job["tenant_id"],
        "kind": job["kind"],
        "status": status,
        "updated_at": str(time.time()),
        **{str(key): str(value)[:4000] for key, value in fields.items()},
    }
    client.hset(_state_key(profile, job["job_id"]), mapping=values)
    client.expire(_state_key(profile, job["job_id"]), 7 * 24 * 60 * 60)


def process_once(client: Any, profile: str, raw: str | bytes | dict[str, Any], handler: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    job = validate_job(raw)
    key = _state_key(profile, job["job_id"])
    previous = client.hget(key, "status")
    if previous in {"completed", "manual_review"}:
        return {"status": "duplicate", "job_id": job["job_id"]}
    _save_state(client, profile, job, "processing", attempt=job["attempt"])
    try:
        result = handler(job) or {}
        status = str(result.get("status") or "completed")
        if status not in {"completed", "manual_review"}:
            status = "completed"
        _save_state(client, profile, job, status, result=json.dumps(result, ensure_ascii=False))
        return {"status": status, "job_id": job["job_id"], **result}
    except JobManualReview as exc:
        _save_state(client, profile, job, "manual_review", reason=exc.reason)
        return {"status": "manual_review", "job_id": job["job_id"], "reason": exc.reason}
    except Exception as exc:
        logger.exception("Falha no job profile=%s job_id=%s", profile, job["job_id"])
        _save_state(client, profile, job, "failed", error=str(exc)[:1000])
        return {"status": "failed", "job_id": job["job_id"], "error": str(exc)[:1000]}


def run_forever(profile: str, queue_name: str, client: Any, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    heartbeat_key = f"negobot:worker:heartbeat:{profile}"
    logger.info("Worker profile=%s queue=%s iniciado", profile, queue_name)
    while True:
        client.setex(heartbeat_key, 90, str(time.time()))
        item = client.blpop(queue_name, timeout=30)
        if not item:
            continue
        try:
            process_once(client, profile, item[1], handler)
        except JobContractError as exc:
            logger.warning("Job rejeitado profile=%s reason=%s", profile, exc)
