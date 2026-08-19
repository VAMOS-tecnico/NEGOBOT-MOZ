from __future__ import annotations

import json
import logging
import os

import redis
from dotenv import load_dotenv

load_dotenv(os.getenv("NEGOBOT_ENV_FILE", "/run/negobot-env/.env"), override=False)

from services.image_generator_service import gerar_imagem_publicitaria
from services.job_runtime import run_forever
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-image-worker")
QUEUE = os.getenv("IMAGE_QUEUE", "negobot:image_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def handle(client, job: dict) -> dict:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else job
    prompt = str(payload.get("prompt") or "").strip()
    image_url = gerar_imagem_publicitaria(prompt)
    if not image_url:
        raise RuntimeError("image_provider_failed")
    client.setex(
        f"negobot:image:result:{job['job_id']}",
        24 * 60 * 60,
        json.dumps({"job_id": job["job_id"], "tenant_id": job["tenant_id"], "image_url": image_url}, ensure_ascii=False),
    )
    return {"provider": os.getenv("IMAGE_PROVIDER", "pollinations"), "image_url": image_url}


def main() -> None:
    enforce_profile("image")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    run_forever("image", QUEUE, client, lambda job: handle(client, job))


if __name__ == "__main__":
    main()
