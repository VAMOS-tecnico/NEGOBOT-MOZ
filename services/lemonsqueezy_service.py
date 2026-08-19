"""Integração segura com Lemon Squeezy para pagamentos online do SaaS."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


LEMONSQUEEZY_API_URL = "https://api.lemonsqueezy.com/v1"


def _variant_env_key(plan_id: str) -> str:
    return f"LEMONSQUEEZY_VARIANT_{str(plan_id).strip().upper()}"


def variant_for_plan(plan_id: str) -> str:
    value = os.getenv(_variant_env_key(plan_id), "").strip()
    if not value.isdigit():
        raise ValueError(f"Variant Lemon Squeezy não configurada para o plano {plan_id}.")
    return value


def variant_for_addon(addon_id: str) -> str:
    key = f"LEMONSQUEEZY_VARIANT_ADDON_{str(addon_id).strip().upper()}"
    value = os.getenv(key, "").strip()
    if not value.isdigit():
        raise ValueError(f"Variant Lemon Squeezy não configurada para o extra {addon_id}.")
    return value


def configured() -> bool:
    return bool(
        os.getenv("LEMONSQUEEZY_STORE_ID", "").strip()
        and os.getenv("LEMONSQUEEZY_API_KEY", "").strip()
        and os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "").strip()
    )


def verify_signature(raw_body: bytes, signature: str | None, secret: str | None = None) -> bool:
    signing_secret = (secret or os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "")).encode("utf-8")
    provided = (signature or "").strip().encode("utf-8")
    if not signing_secret or not provided:
        return False
    digest = hmac.new(signing_secret, raw_body, hashlib.sha256).hexdigest().encode("utf-8")
    return hmac.compare_digest(digest, provided)


def _checkout_payload(store_id: str, variant_id: str, custom_data: dict[str, Any], email: str | None, name: str | None) -> dict[str, Any]:
    checkout_data: dict[str, Any] = {"custom": custom_data}
    if email:
        checkout_data["email"] = email
    if name:
        checkout_data["name"] = name
    return {
        "data": {
            "type": "checkouts",
            "attributes": {"checkout_data": checkout_data},
            "relationships": {
                "store": {"data": {"type": "stores", "id": str(store_id)}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }


def _create_checkout(*, variant_id: str, custom_data: dict[str, Any], email: str | None = None, name: str | None = None) -> dict[str, Any]:
    api_key = os.getenv("LEMONSQUEEZY_API_KEY", "").strip()
    store_id = os.getenv("LEMONSQUEEZY_STORE_ID", "").strip()
    if not api_key or not store_id:
        raise RuntimeError("Lemon Squeezy ainda não está configurada.")
    payload = _checkout_payload(store_id, variant_id, custom_data, email, name)
    response = requests.post(
        f"{LEMONSQUEEZY_API_URL}/checkouts",
        headers={
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {api_key}",
        },
        json=payload,
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(f"Lemon Squeezy recusou o checkout ({response.status_code}).")
    body = response.json() or {}
    attributes = ((body.get("data") or {}).get("attributes") or {})
    checkout_url = str(attributes.get("url") or "").strip()
    if not checkout_url.startswith("https://"):
        raise RuntimeError("Lemon Squeezy não devolveu um URL de checkout válido.")
    return {"url": checkout_url, "variant_id": variant_id, "store_id": store_id}


def create_checkout(*, plan_id: str, tenant_id: str, payment_intent_id: str, email: str | None = None, name: str | None = None) -> dict[str, Any]:
    variant_id = variant_for_plan(plan_id)
    return _create_checkout(
        variant_id=variant_id,
        custom_data={"tenant_id": str(tenant_id), "payment_intent_id": str(payment_intent_id), "plan_id": str(plan_id), "purchase_type": "plan"},
        email=email,
        name=name,
    )


def create_addon_checkout(*, addon_id: str, tenant_id: str, payment_intent_id: str, email: str | None = None, name: str | None = None) -> dict[str, Any]:
    variant_id = variant_for_addon(addon_id)
    return _create_checkout(
        variant_id=variant_id,
        custom_data={"tenant_id": str(tenant_id), "payment_intent_id": str(payment_intent_id), "addon_id": str(addon_id), "purchase_type": "addon"},
        email=email,
        name=name,
    )


def event_key(payload: dict[str, Any]) -> str:
    meta = payload.get("meta") or {}
    data = payload.get("data") or {}
    event_name = str(meta.get("event_name") or "unknown")
    return hashlib.sha256(f"{event_name}:{data.get('type')}:{data.get('id')}".encode("utf-8")).hexdigest()


def extract_event(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("meta") or {}
    data = payload.get("data") or {}
    attributes = data.get("attributes") or {}
    relationships = data.get("relationships") or {}
    variant_data = ((relationships.get("variant") or {}).get("data") or {})
    custom_data = meta.get("custom_data") or {}
    return {
        "event_name": str(meta.get("event_name") or "unknown"),
        "object_type": str(data.get("type") or "unknown"),
        "object_id": str(data.get("id") or ""),
        "attributes": attributes,
        "custom_data": custom_data if isinstance(custom_data, dict) else {},
        "variant_id": str(attributes.get("variant_id") or variant_data.get("id") or ""),
    }


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def expiry_for_event(attributes: dict[str, Any], now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return parse_datetime(attributes.get("renews_at")) or parse_datetime(attributes.get("ends_at")) or (now + timedelta(days=30))
