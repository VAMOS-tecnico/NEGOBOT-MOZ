from __future__ import annotations

from typing import Any

import requests


TELEGRAM_API_BASE = "https://api.telegram.org/bot{}"
TELEGRAM_TIMEOUT_SECONDS = 12


class TelegramApiError(RuntimeError):
    pass


def _api_url(token: str, method: str) -> str:
    return TELEGRAM_API_BASE.format(token) + f"/{method}"


def _call(token: str, method: str, payload: dict[str, Any] | None = None) -> Any:
    response = requests.post(_api_url(token, method), json=payload or {}, timeout=TELEGRAM_TIMEOUT_SECONDS)
    try:
        body = response.json()
    except ValueError as exc:
        raise TelegramApiError("Resposta inválida da API Telegram") from exc
    if not response.ok or not body.get("ok"):
        description = body.get("description") or f"HTTP {response.status_code}"
        raise TelegramApiError(f"Telegram {method}: {description}")
    return body.get("result")


def get_me(token: str) -> dict[str, Any]:
    result = _call(token, "getMe")
    if not isinstance(result, dict) or not result.get("id"):
        raise TelegramApiError("Token Telegram inválido")
    return result


def set_webhook(token: str, *, url: str, secret_token: str) -> None:
    _call(token, "setWebhook", {
        "url": url,
        "secret_token": secret_token,
        "allowed_updates": ["message", "edited_message", "callback_query"],
        "drop_pending_updates": False,
        "max_connections": 40,
    })


def get_webhook_info(token: str) -> dict[str, Any]:
    result = _call(token, "getWebhookInfo")
    return result if isinstance(result, dict) else {}


def delete_webhook(token: str) -> None:
    _call(token, "deleteWebhook", {"drop_pending_updates": False})


def send_message(token: str, *, chat_id: str | int, text: str, reply_to_message_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": str(text)[:4096]}
    if isinstance(reply_to_message_id, int):
        payload["reply_parameters"] = {"message_id": reply_to_message_id}
    result = _call(token, "sendMessage", payload)
    return result if isinstance(result, dict) else {}
