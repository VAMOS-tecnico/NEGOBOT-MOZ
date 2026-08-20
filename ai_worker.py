from __future__ import annotations

import base64
import json
import logging
import os

import redis
import requests
from dotenv import load_dotenv

load_dotenv(os.getenv("NEGOBOT_ENV_FILE", "/run/negobot-env/.env"), override=False)

from services.ai_pool_service import generate_text
from services.job_runtime import run_forever
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-ai-worker")
QUEUE = os.getenv("AI_QUEUE", "negobot:ai_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def _save_result(client, job: dict, result: dict) -> None:
    client.setex(
        f"negobot:ai:result:{job['job_id']}",
        24 * 60 * 60,
        json.dumps({"job_id": job["job_id"], "tenant_id": job["tenant_id"], **result}, ensure_ascii=False),
    )


def _transcribe_audio(payload: dict) -> dict:
    api_key = str(os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY não configurada no AI Worker")
    encoded = str(payload.get("audio_base64") or "")
    if not encoded:
        raise ValueError("audio_base64_obrigatorio")
    audio_bytes = base64.b64decode(encoded, validate=True)
    filename = str(payload.get("filename") or "audio.wav")[:160]
    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": (filename, audio_bytes, "audio/wav")},
        data={"model": "whisper-large-v3", "language": "pt", "response_format": "json"},
        timeout=30,
    )
    response.raise_for_status()
    return {"text": str((response.json() or {}).get("text") or "").strip(), "provider": "groq-whisper"}


def handle(client, job: dict) -> dict:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else job
    if str(job.get("kind") or "") == "audio_transcription":
        result = _transcribe_audio(payload)
        _save_result(client, job, result)
        return {"provider": result["provider"]}
    messages = payload.get("messages") or payload.get("historico_mensagens") or []
    if not isinstance(messages, list):
        raise ValueError("messages_deve_ser_lista")
    result = generate_text(messages, system_prompt=str(payload.get("system_prompt") or ""), request_id=str(job["job_id"]))
    _save_result(client, job, result)
    return {"provider": result.get("provider", "none"), "fallback": bool(result.get("fallback"))}


def main() -> None:
    enforce_profile("ai")
    client = redis.from_url(REDIS_URL, decode_responses=True)
    run_forever("ai", QUEUE, client, lambda job: handle(client, job))


if __name__ == "__main__":
    main()
