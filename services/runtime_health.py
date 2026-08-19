"""Health checks sanitizados para o processo HTTP do NEGOBOT."""
from __future__ import annotations

import os
from typing import Any


def liveness_report() -> dict[str, str]:
    return {"status": "ok"}


def readiness_report() -> dict[str, Any]:
    checks: dict[str, str] = {}

    try:
        import firebase_admin

        checks["firebase"] = "online" if firebase_admin._apps else "offline"
    except Exception:
        checks["firebase"] = "offline"

    try:
        import redis

        client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/1"), decode_responses=True)
        client.ping()
        checks["redis"] = "online"
    except Exception:
        checks["redis"] = "offline"

    ready = all(value == "online" for value in checks.values())
    return {"status": "ready" if ready else "not_ready", "checks": checks}
