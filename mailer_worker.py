from __future__ import annotations

import logging
import os

import redis
from dotenv import load_dotenv

load_dotenv(os.getenv("NEGOBOT_ENV_FILE", "/run/negobot-env/.env"), override=False)

from services.job_runtime import run_forever
from services.mailer_service import send_email
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-mailer-worker")
QUEUE = os.getenv("MAIL_QUEUE", "negobot:mail_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def handle(_client, job: dict) -> dict:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else job
    result = send_email(
        str(payload.get("to") or payload.get("recipient") or ""),
        str(payload.get("subject") or "NEGOBOT MOZ"),
        str(payload.get("body") or ""),
        html=payload.get("html"),
    )
    return {"recipient": result["recipient"]}


def main() -> None:
    enforce_profile("mailer")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    run_forever("mailer", QUEUE, client, lambda job: handle(client, job))


if __name__ == "__main__":
    main()
