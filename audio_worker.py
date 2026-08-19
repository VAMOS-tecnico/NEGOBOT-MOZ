from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import redis
from dotenv import load_dotenv

load_dotenv(os.getenv("NEGOBOT_ENV_FILE", "/run/negobot-env/.env"), override=False)

from services.groq_service import gerar_audio_resposta
from services.job_runtime import run_forever
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-audio-worker")
QUEUE = os.getenv("AUDIO_QUEUE", "negobot:audio_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
OUTPUT_DIR = Path(os.getenv("AUDIO_OUTPUT_DIR", "/tmp/negobot-audio"))


def handle(client, job: dict) -> dict:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else job
    text = str(payload.get("text") or payload.get("texto") or "").strip()
    if not text:
        raise ValueError("text_obrigatorio")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{job['job_id']}.mp3"
    result = gerar_audio_resposta(text, caminho_saida=str(output), idioma=payload.get("language"))
    if not result or not output.exists():
        raise RuntimeError("audio_provider_failed")
    client.setex(
        f"negobot:audio:result:{job['job_id']}",
        24 * 60 * 60,
        json.dumps({"job_id": job["job_id"], "tenant_id": job["tenant_id"], "output_path": str(output)}, ensure_ascii=False),
    )
    return {"provider": os.getenv("AUDIO_PROVIDER", "edge-tts"), "output_path": str(output)}


def main() -> None:
    enforce_profile("audio")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    run_forever("audio", QUEUE, client, lambda job: handle(client, job))


if __name__ == "__main__":
    main()
