"""Catálogo e contrato comum dos canais omnichannel da NEGOBOT-MOZ."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

CHANNEL_STATUSES = {
    "not_configured",
    "pending_authorization",
    "pending_review",
    "connected",
    "disabled",
    "error",
}

CHANNEL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "whatsapp": {
        "label": "WhatsApp",
        "kind": "messaging",
        "provider": "Evolution API",
        "setup": "qr",
        "availability": "active",
    },
    "instagram": {
        "label": "Instagram",
        "kind": "messaging",
        "provider": "Meta Graph API",
        "setup": "oauth",
        "availability": "requires_review",
    },
    "facebook": {
        "label": "Facebook",
        "kind": "messaging",
        "provider": "Meta Graph API",
        "setup": "oauth",
        "availability": "requires_review",
    },
    "telegram": {
        "label": "Telegram",
        "kind": "messaging",
        "provider": "Telegram Bot API",
        "setup": "bot_token",
        "availability": "available_with_bot",
    },
    "tiktok": {
        "label": "TikTok",
        "kind": "messaging",
        "provider": "TikTok Business Messaging API",
        "setup": "oauth",
        "availability": "requires_business_review",
    },
    "linkedin": {
        "label": "LinkedIn",
        "kind": "social",
        "provider": "LinkedIn API",
        "setup": "partner_oauth",
        "availability": "restricted",
    },
    "x": {
        "label": "X",
        "kind": "messaging",
        "provider": "X API v2",
        "setup": "oauth",
        "availability": "available_with_approval",
    },
    "email": {
        "label": "Email",
        "kind": "messaging",
        "provider": "SMTP / inbound provider",
        "setup": "smtp",
        "availability": "requires_provider",
    },
}


def channel_keys() -> tuple[str, ...]:
    return tuple(CHANNEL_DEFINITIONS)


def ensure_channel(channel: str) -> str:
    normalized = str(channel or "").strip().lower().replace("twitter", "x")
    if normalized not in CHANNEL_DEFINITIONS:
        raise ValueError("Canal não suportado")
    return normalized


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configured_status(channel: str, tenant: dict[str, Any], config: dict[str, Any]) -> str:
    explicit = str(config.get("status") or "").strip().lower()
    if explicit in CHANNEL_STATUSES:
        return explicit
    if channel == "whatsapp":
        state = str(tenant.get("evolution_state") or "").strip().lower()
        return "connected" if state == "open" else "not_configured"
    if CHANNEL_DEFINITIONS[channel]["availability"] == "restricted":
        return "pending_review"
    return "not_configured"


def client_channel_rows(tenant: dict[str, Any]) -> list[dict[str, Any]]:
    stored = tenant.get("channels") if isinstance(tenant.get("channels"), dict) else {}
    rows: list[dict[str, Any]] = []
    for key, definition in CHANNEL_DEFINITIONS.items():
        config = stored.get(key) if isinstance(stored.get(key), dict) else {}
        status = _configured_status(key, tenant, config)
        rows.append({
            "key": key,
            **definition,
            "status": status,
            "external_account_id": str(config.get("external_account_id") or "") or None,
            "last_event_at": config.get("last_event_at"),
            "last_error": config.get("last_error"),
            "can_connect": status in {"not_configured", "disabled", "error"} and definition["availability"] != "restricted",
            "requires_review": definition["availability"] in {"requires_review", "requires_business_review", "restricted", "available_with_approval"},
        })
    return rows


def normalize_event(channel: str, tenant_id: str, payload: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    channel = ensure_channel(channel)
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    message = data.get("message") if isinstance(data.get("message"), dict) else data
    sender_data = message.get("from") if isinstance(message, dict) and isinstance(message.get("from"), dict) else {}
    chat_data = message.get("chat") if isinstance(message, dict) and isinstance(message.get("chat"), dict) else {}
    sender = data.get("from") or data.get("sender") or data.get("sender_id") or data.get("user_id") or sender_data.get("id")
    conversation = data.get("conversation_id") or data.get("chat_id") or data.get("thread_id") or data.get("conversation") or chat_data.get("id")
    message_id = data.get("message_id") or data.get("event_id") or data.get("id") or message.get("message_id")
    text = message.get("text") if isinstance(message, dict) else data.get("text")
    return {
        "tenant_id": str(tenant_id),
        "channel": channel,
        "external_account_id": str(data.get("account_id") or data.get("page_id") or data.get("bot_id") or data.get("business_id") or "") or None,
        "conversation_id": str(conversation or "") or None,
        "contact_external_id": str(sender or "") or None,
        "message_id": str(message_id or "") or None,
        "direction": "inbound",
        "text": str(text or ""),
        "received_at": utc_now(),
        "request_id": request_id or str(payload.get("request_id") or "") or None,
        "provider_event": str(payload.get("event") or payload.get("type") or "message"),
        "payload": payload,
    }
