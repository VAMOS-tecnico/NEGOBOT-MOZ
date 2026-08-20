from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from services.mail_queue_service import MailQueueError, enqueue_email
from werkzeug.security import generate_password_hash


PASSWORD_RESET_COLLECTION = "password_resets"
DEFAULT_TTL_MINUTES = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def token_digest(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _ttl_minutes() -> int:
    try:
        return max(5, min(int(os.getenv("PASSWORD_RESET_TTL_MINUTES", str(DEFAULT_TTL_MINUTES))), 120))
    except ValueError:
        return DEFAULT_TTL_MINUTES


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _is_expired(value: Any, now: datetime | None = None) -> bool:
    expiry = _as_utc(value)
    return expiry is None or expiry <= (now or _now())


def _reset_email_body(reset_url: str) -> str:
    return (
        "Olá,\n\n"
        "Recebemos um pedido para alterar a palavra-passe da tua conta NEGOBOT-MOZ. "
        "Abre esta ligação dentro de 30 minutos para definir uma nova palavra-passe:\n\n"
        f"{reset_url}\n\n"
        "Se não fizeste este pedido, ignora este email. A tua palavra-passe actual não foi enviada nem será mostrada.\n\n"
        "NEGOBOT-MOZ\n\n"
        "--- English ---\n"
        "We received a request to change your NEGOBOT-MOZ password. "
        "Use the link above within 30 minutes to choose a new password. "
        "If you did not request this, ignore this email."
    )


def request_password_reset(db: Any, email: str, frontend_base_url: str) -> bool:
    """Create a one-use reset token and email it when the account exists.

    The caller should always return the same public response for known and
    unknown emails to prevent account enumeration.
    """
    canonical_email = str(email or "").strip().lower()
    if not canonical_email:
        return False
    user_ref = db.collection("platform_users").document(hashlib.sha256(canonical_email.encode("utf-8")).hexdigest())
    user_snapshot = user_ref.get()
    if not getattr(user_snapshot, "exists", False):
        return False
    user = user_snapshot.to_dict() or {}
    if user.get("status", "active") != "active":
        return False
    token = secrets.token_urlsafe(32)
    now = _now()
    reset_ref = db.collection(PASSWORD_RESET_COLLECTION).document(token_digest(token))
    reset_ref.set(
        {
            "user_id": user_ref.id,
            "email": canonical_email,
            "created_at": now,
            "expires_at": now + timedelta(minutes=_ttl_minutes()),
            "used_at": None,
        },
        merge=False,
    )
    base = str(frontend_base_url or "").rstrip("/")
    reset_url = f"{base}/reset-password?token={quote(token)}"
    try:
        enqueue_email(
            tenant_id=str(user.get("tenant_id") or f"user:{user_ref.id}"),
            recipient=canonical_email,
            subject="NEGOBOT-MOZ — Password reset / Recuperação de palavra-passe",
            body=_reset_email_body(reset_url),
            request_id=f"password-reset:{token_digest(token)}",
        )
    except MailQueueError:
        # Do not expose queue state to the requester. The token is harmless
        # without delivery and expires quickly.
        return False
    return True


def consume_password_reset(db: Any, token: str, new_password: str) -> bool:
    """Atomically consume a valid token and replace the account password."""
    token = str(token or "").strip()
    if not token or len(new_password) < 8:
        return False
    reset_ref = db.collection(PASSWORD_RESET_COLLECTION).document(token_digest(token))
    now = _now()

    transaction_factory = getattr(db, "transaction", None)
    if not callable(transaction_factory):
        reset_snapshot = reset_ref.get()
        if not getattr(reset_snapshot, "exists", False):
            return False
        reset = reset_snapshot.to_dict() or {}
        if reset.get("used_at") is not None or _is_expired(reset.get("expires_at"), now):
            return False
        user_ref = db.collection("platform_users").document(str(reset.get("user_id") or ""))
        user_snapshot = user_ref.get()
        if not getattr(user_snapshot, "exists", False) or (user_snapshot.to_dict() or {}).get("status", "active") != "active":
            return False
        user_ref.set({"password_hash": generate_password_hash(new_password), "password_changed_at": now, "updated_at": now}, merge=True)
        reset_ref.set({"used_at": now}, merge=True)
        return True

    for _attempt in range(3):
        try:
            transaction = transaction_factory()
            reset_snapshot = transaction.get(reset_ref)
            if not getattr(reset_snapshot, "exists", False):
                return False
            reset = reset_snapshot.to_dict() or {}
            if reset.get("used_at") is not None or _is_expired(reset.get("expires_at"), now):
                return False
            user_ref = db.collection("platform_users").document(str(reset.get("user_id") or ""))
            user_snapshot = transaction.get(user_ref)
            if not getattr(user_snapshot, "exists", False) or (user_snapshot.to_dict() or {}).get("status", "active") != "active":
                return False
            transaction.set(user_ref, {"password_hash": generate_password_hash(new_password), "password_changed_at": now, "updated_at": now}, merge=True)
            transaction.set(reset_ref, {"used_at": now}, merge=True)
            transaction.commit()
            return True
        except Exception:
            continue
    return False
