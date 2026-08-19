"""Identidade central e reclamação única do trial por conta.

O trial pertence à Conta Central, não ao canal. Este módulo mantém a regra
independente de WhatsApp, Telegram ou futuros adaptadores OAuth.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from services.trial_service import ACTIVE_STATUS, EXPIRED_STATUS, PENDING_STATUS, TRIAL_DAYS, as_utc


TRIAL_REGISTRY_COLLECTION = "central_trial_registry"


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_phone(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def hash_identity(value: Any, kind: str) -> str | None:
    normalized = normalize_email(value) if kind == "email" else normalize_phone(value)
    if not normalized:
        return None
    return hashlib.sha256(f"negobot:{kind}:v1:{normalized}".encode("utf-8")).hexdigest()


def central_account_id_for_tenant(tenant: dict[str, Any] | None) -> str | None:
    data = tenant if isinstance(tenant, dict) else {}
    value = data.get("central_account_id") or data.get("central_id")
    if value:
        return str(value)
    email_hash = hash_identity(data.get("account_email") or data.get("email"), "email")
    return f"ca_{email_hash[:24]}" if email_hash else None


def pending_registry_fields(
    central_account_id: str,
    tenant_id: str,
    email: Any = None,
    phone: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    fields: dict[str, Any] = {
        "central_account_id": central_account_id,
        "tenant_id": tenant_id,
        "trial_status": PENDING_STATUS,
        "trial_access_level": "none",
        "trial_consumed": False,
        "created_at": current,
        "updated_at": current,
    }
    email_hash = hash_identity(email, "email")
    phone_hash = hash_identity(phone, "phone")
    if email_hash:
        fields["email_hash"] = email_hash
    if phone_hash:
        fields["phone_hash"] = phone_hash
    return fields


def _consumed_identity_blocker(db: Any, central_account_id: str, email: Any = None, phone: Any = None) -> dict[str, Any] | None:
    candidates = [("email_hash", hash_identity(email, "email")), ("phone_hash", hash_identity(phone, "phone"))]
    for field, value in candidates:
        if not value:
            continue
        try:
            snapshots = db.collection(TRIAL_REGISTRY_COLLECTION).where(field, "==", value).limit(10).stream()
        except Exception:
            continue
        for snapshot in snapshots:
            if str(getattr(snapshot, "id", "")) == central_account_id:
                continue
            data = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
            if data.get("trial_consumed") or str(data.get("trial_status") or "").lower() in {ACTIVE_STATUS, EXPIRED_STATUS}:
                return {**data, "blocked_by_identity": True, "blocked_identity_field": field}
    return None


def _claim_once_fallback(reference: Any, fields: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    snapshot = reference.get()
    existing = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
    status = str(existing.get("trial_status") or "").lower()
    if existing.get("trial_consumed") or status in {ACTIVE_STATUS, EXPIRED_STATUS}:
        return False, existing
    reference.set(fields, merge=True)
    return True, {**existing, **fields}


def claim_trial_for_account(
    db: Any,
    central_account_id: str | None,
    tenant_id: str,
    channel: str,
    *,
    email: Any = None,
    phone: Any = None,
    now: datetime | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Claim the one trial window for the first successfully connected channel.

    Firestore transactions are used in production to avoid two channels winning
    simultaneously. The small fallback keeps unit-test fakes deterministic.
    """
    if not central_account_id:
        return False, {"trial_status": EXPIRED_STATUS, "trial_consumed": True}
    blocker = _consumed_identity_blocker(db, central_account_id, email=email, phone=phone)
    if blocker:
        return False, blocker
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    reference = db.collection(TRIAL_REGISTRY_COLLECTION).document(central_account_id)
    fields = pending_registry_fields(central_account_id, tenant_id, email, phone, current)
    fields.update({
        "trial_status": ACTIVE_STATUS,
        "trial_access_level": "premium",
        "trial_consumed": True,
        "started_channel": str(channel).strip().lower(),
        "started_at": current,
        "expires_at": current + __import__("datetime").timedelta(days=TRIAL_DAYS),
        "updated_at": current,
    })
    if not hasattr(db, "transaction"):
        return _claim_once_fallback(reference, fields)
    try:
        transaction = db.transaction()
        snapshot = transaction.get(reference)
        existing = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
        status = str(existing.get("trial_status") or "").lower()
        if existing.get("trial_consumed") or status in {ACTIVE_STATUS, EXPIRED_STATUS}:
            return False, existing
        transaction.set(reference, fields, merge=True)
        transaction.commit()
        return True, {**existing, **fields}
    except Exception:
        # If a test double or older Firestore client has no transaction API,
        # preserve the deterministic fallback rather than exposing a secret.
        return _claim_once_fallback(reference, fields)


def trial_fields_from_registry(record: dict[str, Any] | None, channel: str, instance_name: str | None = None) -> dict[str, Any]:
    data = record if isinstance(record, dict) else {}
    started_at = data.get("started_at")
    expires_at = data.get("expires_at")
    fields: dict[str, Any] = {
        "trial_status": ACTIVE_STATUS,
        "trial_access_level": "premium",
        "trial_connection_confirmed": True,
        "trial_connected_at": started_at,
        "trial_expires_at": expires_at,
        "data_ativacao": started_at,
        "data_expiracao": expires_at,
        "trial_started_channel": data.get("started_channel") or str(channel).strip().lower(),
        "trial_last_connected_channel": str(channel).strip().lower(),
    }
    if instance_name:
        fields["trial_instance_name"] = str(instance_name)
    return fields


def registry_is_expired(data: dict[str, Any] | None, now: datetime | None = None) -> bool:
    record = data if isinstance(data, dict) else {}
    expiry = as_utc(record.get("expires_at"))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return bool(expiry and current >= expiry)


def registry_status(db: Any, central_account_id: str | None) -> dict[str, Any]:
    if not central_account_id:
        return {}
    reference = db.collection(TRIAL_REGISTRY_COLLECTION).document(central_account_id)
    snapshot = reference.get()
    return snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
