"""Regras partilhadas do ciclo de demonstração do Negobot Moz."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

TRIAL_DAYS = 2
PENDING_STATUS = "trial_pending_connection"
ACTIVE_STATUS = "trial_active"
EXPIRED_STATUS = "trial_expired"
DEMO_PLAN = "demonstracao"


def as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def is_paid_plan(data: dict[str, Any] | None) -> bool:
    data = data if isinstance(data, dict) else {}
    plan_status = str(data.get("status_plano", "")).strip().lower()
    plan = str(data.get("plano", data.get("plan", ""))).strip().lower()
    if plan_status in {"ativo", "active", "paid", "premium"}:
        return True
    return bool(plan and plan not in {DEMO_PLAN, "trial", "demonstracao"})


def has_real_connection(data: dict[str, Any] | None) -> bool:
    data = data if isinstance(data, dict) else {}
    return bool(as_utc(data.get("trial_connected_at")) or data.get("trial_connection_confirmed") is True)


def is_trial_pending(data: dict[str, Any] | None) -> bool:
    data = data if isinstance(data, dict) else {}
    if is_paid_plan(data):
        return False
    return str(data.get("trial_status", "")).strip().lower() == PENDING_STATUS or not has_real_connection(data)


def trial_expiry(data: dict[str, Any] | None) -> datetime | None:
    data = data if isinstance(data, dict) else {}
    if is_paid_plan(data):
        return as_utc(data.get("data_expiracao"))
    if not has_real_connection(data):
        return None
    expiry = as_utc(data.get("trial_expires_at")) or as_utc(data.get("data_expiracao"))
    connected_at = as_utc(data.get("trial_connected_at"))
    return expiry or (connected_at + timedelta(days=TRIAL_DAYS) if connected_at else None)


def is_expired(data: dict[str, Any] | None, now: datetime | None = None) -> bool:
    data = data if isinstance(data, dict) else {}
    status = str(data.get("status_plano", data.get("status", ""))).strip().lower()
    if status in {"expirado", "suspenso", "cancelado"} or data.get("trial_status") == EXPIRED_STATUS:
        return True
    expiry = trial_expiry(data)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return bool(expiry and current >= expiry)


def pending_fields(phone: str, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    return {
        "status_plano": DEMO_PLAN,
        "status": "pending_connection",
        "trial_status": PENDING_STATUS,
        "trial_connection_confirmed": False,
        "trial_access_level": "none",
        "trial_instance_name": str(phone),
        "instance_name": str(phone),
        "telefone_proprietario": str(phone),
        "trial_qr_sent_at": current,
    }


def active_fields(phone: str, connected_at: datetime | None = None) -> dict[str, Any]:
    current = connected_at or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    expiry = current + timedelta(days=TRIAL_DAYS)
    return {
        "status_plano": DEMO_PLAN,
        "status": "trial",
        "trial_status": ACTIVE_STATUS,
        "trial_access_level": "premium",
        "trial_connection_confirmed": True,
        "trial_connected_at": current,
        "trial_expires_at": expiry,
        "data_ativacao": current,
        "data_expiracao": expiry,
        "trial_instance_name": str(phone),
        "instance_name": str(phone),
        "telefone_proprietario": str(phone),
        "evolution_state": "open",
    }
