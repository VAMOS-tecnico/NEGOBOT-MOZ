"""API isolada para jobs de vídeos curtos do NEGOBOT-MOZ."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import redis
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="NEGOBOT Video Service", version="1.0.0")
QUEUE = os.getenv("VIDEO_QUEUE", "negobot:video_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def queue_client():
    return redis.from_url(REDIS_URL, decode_responses=True)


def require_service_token(x_video_service_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("VIDEO_SERVICE_TOKEN", "").strip()
    if not expected or x_video_service_token is None or x_video_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vídeo service não autorizado.")


class Scene(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    duration_seconds: float = Field(default=3.5, ge=1, le=20)
    asset_url: str | None = Field(default=None, max_length=2000)

    @field_validator("asset_url")
    @classmethod
    def public_asset_url(cls, value: str | None) -> str | None:
        if value and not re.match(r"^https://[^\s]+$", value, flags=re.IGNORECASE):
            raise ValueError("Os assets devem usar URLs HTTPS públicas.")
        return value


class VideoJobRequest(BaseModel):
    tenant_id: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=160)
    scenes: list[Scene] = Field(min_length=1, max_length=20)
    language: str = Field(default="pt-MZ", min_length=2, max_length=20)
    voice: str | None = Field(default=None, max_length=100)
    subtitles: bool = True
    callback_url: str | None = Field(default=None, max_length=2000)

    @field_validator("callback_url")
    @classmethod
    def public_callback_url(cls, value: str | None) -> str | None:
        if value and not re.match(r"^https://[^\s]+$", value, flags=re.IGNORECASE):
            raise ValueError("O callback deve usar uma URL HTTPS pública.")
        return value


@app.get("/health")
def health():
    try:
        queue_client().ping()
        redis_status = "online"
    except Exception:
        redis_status = "offline"
    return {"service": "negobot-video", "status": "online", "redis": redis_status}


@app.post("/api/video/jobs", status_code=202, dependencies=[Depends(require_service_token)])
def create_job(payload: VideoJobRequest):
    job_id = uuid.uuid4().hex
    job = {"id": job_id, **payload.model_dump(), "status": "queued", "progress": 0, "created_at": now(), "updated_at": now()}
    client = queue_client()
    client.hset(f"negobot:video:job:{job_id}", mapping={"payload": json.dumps(job, ensure_ascii=False), "status": "queued", "progress": "0", "updated_at": job["updated_at"]})
    client.rpush(QUEUE, json.dumps(job, ensure_ascii=False))
    return {"accepted": True, "job": job}


@app.get("/api/video/jobs/{job_id}", dependencies=[Depends(require_service_token)])
def get_job(job_id: str):
    data = queue_client().hgetall(f"negobot:video:job:{job_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Job de vídeo não encontrado.")
    payload: dict[str, Any] = json.loads(data.get("payload", "{}"))
    payload.update({"status": data.get("status", payload.get("status")), "progress": int(data.get("progress", payload.get("progress", 0))), "updated_at": data.get("updated_at", payload.get("updated_at"))})
    if data.get("output_url"):
        payload["output_url"] = data["output_url"]
    if data.get("error"):
        payload["error"] = data["error"]
    return {"job": payload}
