from __future__ import annotations

import json
import logging
import os
import time

import redis
import requests

from video_pipeline import render_job_with_tts
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-video-worker")
QUEUE = os.getenv("VIDEO_QUEUE", "negobot:video_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
OUTPUT_DIR = os.getenv("VIDEO_OUTPUT_DIR", "/tmp/negobot-videos")


def update(client, job: dict, status: str, progress: int, **fields):
    values = {"status": status, "progress": str(max(0, min(100, progress))), "updated_at": time.time(), **{key: str(value) for key, value in fields.items()}}
    client.hset(f"negobot:video:job:{job['id']}", mapping=values)


def callback(job: dict, result: dict):
    url = str(job.get("callback_url") or "").strip()
    if not url.startswith("https://"):
        return
    try:
        requests.post(url, json=result, timeout=10, headers={"X-NEGOBOT-Event": "video.completed"})
    except requests.RequestException as exc:
        logger.warning("Callback do vídeo falhou para %s: %s", job.get("id"), exc)


def process(client, job: dict):
    update(client, job, "processing", 5)
    try:
        update(client, job, "processing", 20)
        output = render_job_with_tts(job, OUTPUT_DIR)
        update(client, job, "completed", 100, output_path=output)
        callback(job, {"job_id": job["id"], "status": "completed", "output_path": output})
        logger.info("Vídeo concluído job=%s", job["id"])
    except Exception as exc:
        logger.exception("Falha no vídeo job=%s", job.get("id"))
        update(client, job, "failed", 100, error=str(exc)[:1000])
        callback(job, {"job_id": job["id"], "status": "failed", "error": str(exc)[:1000]})


def main():
    enforce_profile("video")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    while True:
        item = client.blpop(QUEUE, timeout=30)
        if not item:
            continue
        try:
            process(client, json.loads(item[1]))
        except Exception:
            logger.exception("Job inválido na fila de vídeo")


if __name__ == "__main__":
    main()
