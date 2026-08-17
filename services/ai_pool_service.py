"""Pool multi-provedor de IA com rotação round-robin e fallback final.

As chaves são lidas apenas do ambiente do backend. Provedores sem chave são
ignorados; uma falha numa API não interrompe a tentativa nos restantes nós.
"""
from __future__ import annotations

import itertools
import logging
import os
import time
import uuid
from typing import Any

import requests

logger = logging.getLogger("negobot-ai-pool")

_FRIENDLY_FALLBACK = (
    "O nosso sistema está a processar muitas mensagens neste momento. "
    "Por favor, aguarde alguns instantes e tente novamente."
)

# O índice é mantido apenas em memória; cada processo Gunicorn tem o seu cursor
# independente, mas a seleção continua distribuída e sem estado sensível.
_CURSOR = itertools.count()

_PRIMARY_PROVIDERS: tuple[dict[str, Any], ...] = (
    {"name": "groq", "key": "GROQ_API_KEY", "model": "GROQ_MODEL", "base_url": "https://api.groq.com/openai/v1"},
    {"name": "cerebras", "key": "CEREBRAS_API_KEY", "model": "CEREBRAS_MODEL", "base_url": "https://api.cerebras.ai/v1"},
    {"name": "sambanova", "key": "SAMBANOVA_API_KEY", "model": "SAMBANOVA_MODEL", "base_url": "https://api.sambanova.ai/v1"},
    {"name": "gemini_1", "key": "GEMINI_API_KEY", "model": "GEMINI_MODEL", "gemini": True},
    {"name": "gemini_2", "key": "GEMINI_API_KEY_2", "model": "GEMINI_MODEL_2", "gemini": True},
    {"name": "github_models", "key": "GITHUB_MODELS_TOKEN", "model": "GITHUB_MODELS_MODEL", "base_url": "https://models.inference.ai.azure.com", "key_aliases": ("GITHUB_TOKEN",)},
    {"name": "mistral", "key": "MISTRAL_API_KEY", "model": "MISTRAL_MODEL", "base_url": "https://api.mistral.ai/v1"},
)


def _env(provider: dict[str, Any], name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    if name == "GITHUB_MODELS_TOKEN":
        for alias in provider.get("key_aliases", ()):
            value = os.getenv(alias, "").strip()
            if value:
                return value
    return default


def _messages(historico_mensagens: list[dict[str, Any]] | None, system_prompt: str | None) -> list[dict[str, str]]:
    prompt = system_prompt or ""
    prompt += "\n\n[INSTRUÇÃO DE IDIOMA]: Responda sempre no mesmo idioma usado pelo cliente."
    result: list[dict[str, str]] = [{"role": "system", "content": prompt}]
    for message in (historico_mensagens or [])[-6:]:
        if not isinstance(message, dict) or "content" not in message:
            continue
        role = "assistant" if message.get("role") in {"assistant", "model", "atendente"} else "user"
        result.append({"role": role, "content": str(message.get("content", ""))})
    return result


def _extract_openai(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def _call_openai(provider: dict[str, Any], key: str, model: str, messages: list[dict[str, str]], timeout: int) -> str:
    url = f"{provider['base_url'].rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider["name"] == "github_models":
        headers["Accept"] = "application/json"
    response = requests.post(
        url,
        headers=headers,
        json={"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 400},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:240]}")
    text = _extract_openai(response.json())
    if not text:
        raise RuntimeError("Resposta sem texto")
    return text


def _call_gemini(key: str, model: str, messages: list[dict[str, str]], timeout: int) -> str:
    system_parts = [item["content"] for item in messages if item["role"] == "system"]
    contents = [{"role": "user" if item["role"] == "user" else "model", "parts": [{"text": item["content"]}]} for item in messages if item["role"] != "system"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = requests.post(
        url,
        params={"key": key},
        json={"systemInstruction": {"parts": [{"text": "\n".join(system_parts)}]}, "contents": contents, "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400}},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:240]}")
    candidates = response.json().get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") if candidates else []
    text = "".join(str(part.get("text") or "") for part in (parts or [])).strip()
    if not text:
        raise RuntimeError("Resposta Gemini sem texto")
    return text


def configured_provider_names() -> list[str]:
    return [provider["name"] for provider in _PRIMARY_PROVIDERS if _env(provider, provider["key"])]


def generate_text(historico_mensagens: list[dict[str, Any]] | None, system_prompt: str | None = None, request_id: str | None = None) -> dict[str, Any]:
    correlation_id = request_id or uuid.uuid4().hex
    messages = _messages(historico_mensagens, system_prompt)
    providers = [provider for provider in _PRIMARY_PROVIDERS if _env(provider, provider["key"])]
    if providers:
        start = next(_CURSOR) % len(providers)
        ordered = providers[start:] + providers[:start]
    else:
        ordered = []
    primary_timeout = max(1, min(10, int(os.getenv("AI_PRIMARY_TIMEOUT", "4"))))
    for provider in ordered:
        key = _env(provider, provider["key"])
        model = _env(provider, provider["model"], "gemini-2.0-flash" if provider.get("gemini") else "")
        if not model:
            logger.warning("AI provider=%s ignorado: modelo não configurado", provider["name"])
            continue
        started = time.monotonic()
        try:
            text = _call_gemini(key, model, messages, primary_timeout) if provider.get("gemini") else _call_openai(provider, key, model, messages, primary_timeout)
            logger.info("AI provider=%s request_id=%s latency_ms=%d", provider["name"], correlation_id, int((time.monotonic() - started) * 1000))
            return {"text": text, "provider": provider["name"], "request_id": correlation_id, "fallback": False}
        except Exception as exc:
            logger.warning("AI provider=%s failed request_id=%s: %s", provider["name"], correlation_id, str(exc)[:300])

    fallback_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if fallback_key:
        model = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"
        try:
            provider = {"name": "openrouter", "base_url": "https://openrouter.ai/api/v1"}
            text = _call_openai(provider, fallback_key, model, messages, max(2, min(15, int(os.getenv("AI_FALLBACK_TIMEOUT", "8")))))
            logger.info("AI provider=openrouter request_id=%s fallback=true", correlation_id)
            return {"text": text, "provider": "openrouter", "request_id": correlation_id, "fallback": True}
        except Exception as exc:
            logger.error("AI fallback=openrouter failed request_id=%s: %s", correlation_id, str(exc)[:300])

    logger.error("AI pool exhausted request_id=%s providers=%s", correlation_id, [item["name"] for item in ordered])
    return {"text": _FRIENDLY_FALLBACK, "provider": "none", "request_id": correlation_id, "fallback": True, "error": "pool_exhausted"}
