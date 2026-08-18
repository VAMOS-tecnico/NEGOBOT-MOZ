"""Endpoints de entrada para canais externos além do webhook Evolution."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from typing import Any

from flask import Blueprint, jsonify, request

import extensions
from services.channel_registry import ensure_channel, normalize_event
from services.incoming_queue import enqueue_omnichannel_event

logger = logging.getLogger(__name__)
omnichannel_bp = Blueprint("omnichannel", __name__, url_prefix="/api/omnichannel")


def _db():
    if extensions.db is None:
        extensions.init_extensions()
    if extensions.db is None:
        raise RuntimeError("Base de dados indisponível")
    return extensions.db


def _tenant(tenant_id: str) -> tuple[Any, dict[str, Any]] | tuple[None, None]:
    reference = _db().collection("tenants").document(str(tenant_id).strip())
    document = reference.get()
    if not document.exists:
        return None, None
    return reference, document.to_dict() or {}


def _configured_secret(channel: str, tenant: dict[str, Any]) -> str:
    channels = tenant.get("channels") if isinstance(tenant.get("channels"), dict) else {}
    config = channels.get(channel) if isinstance(channels.get(channel), dict) else {}
    return str(config.get("webhook_secret") or os.getenv(f"{channel.upper()}_WEBHOOK_SECRET", ""))


def _provided_secret(channel: str) -> str:
    if channel == "telegram":
        return request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    return request.headers.get("X-NEGOBOT-Webhook-Secret", "") or request.headers.get("X-Webhook-Secret", "")


def _valid_secret(channel: str, tenant: dict[str, Any]) -> bool:
    expected = _configured_secret(channel, tenant)
    provided = _provided_secret(channel)
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided, expected)


def _mark_channel_event(reference: Any, tenant: dict[str, Any], channel: str, event: dict[str, Any], *, error: str | None = None) -> None:
    channels = dict(tenant.get("channels") or {}) if isinstance(tenant.get("channels"), dict) else {}
    config = dict(channels.get(channel) or {})
    config.update({
        "status": "error" if error else "connected",
        "last_event_at": event.get("received_at"),
        "last_error": error,
        "external_account_id": event.get("external_account_id"),
    })
    channels[channel] = config
    reference.set({"channels": channels, "updated_at": event.get("received_at")}, merge=True)


@omnichannel_bp.get("/<channel>/<tenant_id>")
def provider_verification(channel: str, tenant_id: str):
    """Verification handshake used by Meta and compatible providers."""
    try:
        channel = ensure_channel(channel)
    except ValueError:
        return jsonify({"error": "Canal não suportado"}), 404
    if channel not in {"instagram", "facebook", "tiktok"}:
        return jsonify({"error": "Este canal não usa esta verificação"}), 405
    if request.args.get("hub.mode") != "subscribe":
        return jsonify({"error": "Pedido de verificação inválido"}), 400
    _, tenant = _tenant(tenant_id)
    if tenant is None:
        return jsonify({"error": "Tenant não encontrado"}), 404
    expected = _configured_secret(channel, tenant)
    supplied = request.args.get("hub.verify_token", "")
    verify_token = str((tenant.get("channels") or {}).get(channel, {}).get("verify_token") or os.getenv("META_VERIFY_TOKEN", ""))
    if not verify_token or not hmac.compare_digest(supplied, verify_token):
        return jsonify({"error": "Token de verificação inválido"}), 403
    challenge = request.args.get("hub.challenge", "")
    return challenge, 200, {"Content-Type": "text/plain; charset=utf-8"}


@omnichannel_bp.get("/x/<tenant_id>")
def x_crc(tenant_id: str):
    """CRC challenge-response para validação de webhooks X."""
    _, tenant = _tenant(tenant_id)
    if tenant is None:
        return jsonify({"error": "Tenant não encontrado"}), 404
    crc_token = request.args.get("crc_token", "")
    consumer_secret = str((tenant.get("channels") or {}).get("x", {}).get("consumer_secret") or os.getenv("X_CONSUMER_SECRET", ""))
    if not crc_token or not consumer_secret:
        return jsonify({"error": "CRC não configurado"}), 400
    digest = hmac.new(consumer_secret.encode(), crc_token.encode(), hashlib.sha256).digest()
    return jsonify({"response_token": "sha256=" + __import__("base64").b64encode(digest).decode()})


@omnichannel_bp.post("/<channel>/<tenant_id>")
def receive_provider_event(channel: str, tenant_id: str):
    try:
        channel = ensure_channel(channel)
    except ValueError:
        return jsonify({"error": "Canal não suportado"}), 404
    reference, tenant = _tenant(tenant_id)
    if reference is None or tenant is None:
        return jsonify({"error": "Tenant não encontrado"}), 404
    if channel in {"linkedin", "email"}:
        return jsonify({"error": "Este adaptador ainda não foi activado"}), 501
    if not _valid_secret(channel, tenant):
        return jsonify({"error": "Assinatura ou secret do webhook inválido"}), 401
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON inválido"}), 400
    request_id = request.headers.get("X-Request-ID") or secrets.token_hex(12)
    event = normalize_event(channel, tenant_id, payload, request_id=request_id)
    event_id = hashlib.sha256(json.dumps({"channel": channel, "tenant": tenant_id, "payload": payload}, sort_keys=True, default=str).encode()).hexdigest()
    event["event_id"] = event_id
    try:
        existing = _db().collection("omnichannel_events").document(event_id).get()
        if existing.exists:
            return jsonify({"accepted": True, "duplicate": True, "event_id": event_id}), 200
        _db().collection("omnichannel_events").document(event_id).set({
            "tenant_id": tenant_id,
            "channel": channel,
            "status": "queued",
            "request_id": request_id,
            "received_at": event["received_at"],
            "message_id": event.get("message_id"),
            "conversation_id": event.get("conversation_id"),
        })
        result = enqueue_omnichannel_event(event)
        _mark_channel_event(reference, tenant, channel, event)
    except Exception:
        logger.exception("Falha ao aceitar evento omnichannel channel=%s tenant=%s", channel, tenant_id)
        try:
            _mark_channel_event(reference, tenant, channel, event, error="queue_unavailable")
        except Exception:
            logger.debug("Não foi possível guardar erro do canal", exc_info=True)
        return jsonify({"error": "Fila omnichannel indisponível"}), 503
    return jsonify({"accepted": True, "event_id": event_id, "queue": result["queue"]}), 200
