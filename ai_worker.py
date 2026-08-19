from __future__ import annotations

import json
import logging
import os

import redis
from dotenv import load_dotenv

load_dotenv(os.getenv("NEGOBOT_ENV_FILE", "/run/negobot-env/.env"), override=False)

from services.ai_pool_service import generate_text
from services.job_runtime import run_forever
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-ai-worker")
QUEUE = os.getenv("AI_QUEUE", "negobot:ai_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def handle(client, job: dict) -> dict:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else job
    messages = payload.get("messages") or payload.get("historico_mensagens") or []
    if not isinstance(messages, list):
        raise ValueError("messages_deve_ser_lista")
    result = generate_text(messages, system_prompt=str(payload.get("system_prompt") or ""), request_id=str(job["job_id"]))
    client.setex(
        f"negobot:ai:result:{job['job_id']}",
        24 * 60 * 60,
        json.dumps({"job_id": job["job_id"], "tenant_id": job["tenant_id"], **result}, ensure_ascii=False),
    )
    return {"provider": result.get("provider", "none"), "fallback": bool(result.get("fallback"))}


def main() -> None:
    enforce_profile("ai")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    run_forever("ai", QUEUE, client, lambda job: handle(client, job))


if __name__ == "__main__":
    main()
