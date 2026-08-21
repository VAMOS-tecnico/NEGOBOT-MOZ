"""API isolada para jobs de vídeos curtos do NEGOBOT-MOZ."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from services.service_config import enforce_profile

app = FastAPI(title="NEGOBOT Video Service", version="1.0.0")


@app.on_event("startup")
def validate_environment() -> None:
    enforce_profile("video")
QUEUE = os.getenv("VIDEO_QUEUE", "negobot:video_jobs")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
OUTPUT_DIR = Path(os.getenv("VIDEO_OUTPUT_DIR", "/var/lib/negobot/videos")).resolve()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def queue_client():
    return redis.from_url(REDIS_URL, decode_responses=True)


def require_service_token(x_video_service_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("VIDEO_SERVICE_TOKEN", "").strip()
    if not expected or x_video_service_token is None or x_video_service_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Vídeo service não autorizado.")


def _job_from_redis(job_id: str) -> tuple[dict[str, str], dict[str, Any]]:
    data = queue_client().hgetall(f"negobot:video:job:{job_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Job de vídeo não encontrado.")
    try:
        payload: dict[str, Any] = json.loads(data.get("payload", "{}"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Dados do job de vídeo inválidos.") from exc
    payload.update({"status": data.get("status", payload.get("status")), "progress": int(data.get("progress", payload.get("progress", 0))), "updated_at": data.get("updated_at", payload.get("updated_at"))})
    for key in ("output_path", "error", "deleted_at"):
        if data.get(key):
            payload[key] = data[key]
    return data, payload


def _tenant_guard(payload: dict[str, Any], x_video_tenant_id: str | None) -> None:
    tenant_id = str(payload.get("tenant_id") or "").strip()
    if not tenant_id or not x_video_tenant_id or tenant_id != x_video_tenant_id.strip():
        raise HTTPException(status_code=404, detail="Job de vídeo não encontrado.")


def _safe_output_path(value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = OUTPUT_DIR / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(OUTPUT_DIR)
    except (OSError, ValueError):
        return None
    return resolved


def _filename(title: str, job_id: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-._")[:80] or "negobot-video"
    return f"{clean}-{job_id[:8]}.mp4"


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
def get_job(job_id: str, x_video_tenant_id: str | None = Header(default=None)):
    data, payload = _job_from_redis(job_id)
    _tenant_guard(payload, x_video_tenant_id)
    if data.get("output_url"):
        payload["output_url"] = data["output_url"]
    output_path = _safe_output_path(str(payload.get("output_path") or ""))
    payload["output_available"] = bool(payload.get("status") == "completed" and output_path is not None and output_path.is_file())
    payload.pop("output_path", None)
    return {"job": payload}


@app.get("/api/video/jobs/{job_id}/preview", dependencies=[Depends(require_service_token)])
def preview_job(job_id: str, x_video_tenant_id: str | None = Header(default=None)):
    _, payload = _job_from_redis(job_id)
    _tenant_guard(payload, x_video_tenant_id)
    if payload.get("status") != "completed":
        raise HTTPException(status_code=409, detail="O vídeo ainda não está pronto para pré-visualização.")
    path = _safe_output_path(str(payload.get("output_path") or ""))
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="O ficheiro de vídeo já não está disponível.")
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'inline; filename="{_filename(str(payload.get("title") or "video"), job_id)}"',
            "Cache-Control": "no-store",
            "Accept-Ranges": "bytes",
        },
    )


@app.get("/api/video/jobs/{job_id}/download", dependencies=[Depends(require_service_token)])
def download_job(job_id: str, x_video_tenant_id: str | None = Header(default=None)):
    _, payload = _job_from_redis(job_id)
    _tenant_guard(payload, x_video_tenant_id)
    if payload.get("status") != "completed":
        raise HTTPException(status_code=409, detail="O vídeo ainda não está pronto para download.")
    path = _safe_output_path(str(payload.get("output_path") or ""))
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="O ficheiro de vídeo já não está disponível.")
    size = path.stat().st_size
    client = queue_client()
    completed = False

    def stream():
        nonlocal completed
        sent = 0
        try:
            with path.open("rb") as video_file:
                while True:
                    chunk = video_file.read(1024 * 1024)
                    if not chunk:
                        break
                    sent += len(chunk)
                    yield chunk
            completed = sent == size
        finally:
            if completed:
                try:
                    path.unlink(missing_ok=True)
                    client.hset(f"negobot:video:job:{job_id}", mapping={"status": "deleted", "progress": "100", "output_path": "", "deleted_at": now(), "updated_at": now(), "deletion_reason": "download_completed"})
                except OSError:
                    client.hset(f"negobot:video:job:{job_id}", mapping={"deletion_error": "file_delete_failed", "updated_at": now()})

    return StreamingResponse(stream(), media_type="video/mp4", headers={"Content-Disposition": f'attachment; filename="{_filename(str(payload.get("title") or "video"), job_id)}"', "Content-Length": str(size), "Cache-Control": "no-store"})


@app.delete("/api/video/jobs/{job_id}", dependencies=[Depends(require_service_token)])
def delete_job(job_id: str, x_video_tenant_id: str | None = Header(default=None)):
    _, payload = _job_from_redis(job_id)
    _tenant_guard(payload, x_video_tenant_id)
    if payload.get("status") not in {"completed", "deleted"}:
        raise HTTPException(status_code=409, detail="Só é possível apagar um vídeo concluído.")
    path = _safe_output_path(str(payload.get("output_path") or ""))
    if path is not None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=500, detail="Não foi possível apagar o ficheiro de vídeo.") from exc
    queue_client().hset(f"negobot:video:job:{job_id}", mapping={"status": "deleted", "progress": "100", "output_path": "", "deleted_at": now(), "updated_at": now(), "deletion_reason": "manual"})
    return {"deleted": True, "job_id": job_id}
