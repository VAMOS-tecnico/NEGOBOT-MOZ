from __future__ import annotations

import logging
import os

import redis
from dotenv import load_dotenv

load_dotenv(os.getenv("NEGOBOT_ENV_FILE", "/run/negobot-env/.env"), override=False)

from services.job_runtime import JobManualReview, run_forever
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-social-poster")
QUEUE = os.getenv("SOCIAL_QUEUE", "negobot:social_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def handle(_client, _job: dict) -> dict:
    raise JobManualReview("social_adapter_not_configured_or_provider_review_pending")


def main() -> None:
    enforce_profile("social")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    run_forever("social", QUEUE, client, handle)


if __name__ == "__main__":
    main()
