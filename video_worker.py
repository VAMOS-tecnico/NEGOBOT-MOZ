from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import redis
import requests
from dotenv import load_dotenv

def _load_environment():
    path = os.getenv("NEGOBOT_ENV_FILE", "/run/negobot-env/.env")
    try:
        load_dotenv(path, override=False)
    except TypeError:
        try:
            load_dotenv(path)
        except TypeError:
            load_dotenv()


_load_environment()

from video_pipeline import render_job_with_tts
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-video-worker")
QUEUE = os.getenv("VIDEO_QUEUE", "negobot:video_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
OUTPUT_DIR = os.getenv("VIDEO_OUTPUT_DIR", "/tmp/negobot-videos")
RETENTION_DAYS = max(1, int(os.getenv("VIDEO_RETENTION_DAYS", "7")))
CLEANUP_INTERVAL_SECONDS = 300


def update(client, job: dict, status: str, progress: int, **fields):
    values = {"status": status, "progress": str(max(0, min(100, progress))), "updated_at": time.time(), **{key: str(value) for key, value in fields.items()}}
    client.hset(f"negobot:video:job:{job['id']}", mapping=values)


def _safe_output_path(value: str) -> Path | None:
    candidate = Path(value)
    root = Path(OUTPUT_DIR).resolve()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved


def cleanup_expired_outputs(client):
    cutoff = time.time() - (RETENTION_DAYS * 86400)
    removed = 0
    for key in client.scan_iter(match="negobot:video:job:*"):
        data = client.hgetall(key)
        if data.get("status") != "completed" or not data.get("output_path"):
            continue
        path = _safe_output_path(data["output_path"])
        if path is None or not path.is_file():
            continue
        try:
            reference_time = path.stat().st_mtime
            if data.get("updated_at"):
                try:
                    reference_time = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")).timestamp()
                except ValueError:
                    pass
            if reference_time > cutoff:
                continue
            path.unlink()
            client.hset(key, mapping={"status": "deleted", "progress": "100", "output_path": "", "deleted_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat(), "deletion_reason": "retention"})
            removed += 1
        except OSError:
            logger.warning("Não foi possível limpar o vídeo expirado key=%s", key)
    if removed:
        logger.info("Limpeza de vídeos: %s output(s) removido(s)", removed)
    return removed


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
    heartbeat_key = "negobot:worker:heartbeat:video"
    last_cleanup = 0.0
    while True:
        client.setex(heartbeat_key, 90, str(time.time()))
        if time.time() - last_cleanup >= CLEANUP_INTERVAL_SECONDS:
            cleanup_expired_outputs(client)
            last_cleanup = time.time()
        item = client.blpop(QUEUE, timeout=30)
        if not item:
            continue
        try:
            process(client, json.loads(item[1]))
        except Exception:
            logger.exception("Job inválido na fila de vídeo")


if __name__ == "__main__":
    main()
