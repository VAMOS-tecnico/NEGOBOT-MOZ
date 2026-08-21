#!/usr/bin/env python3
"""Teste rápido e individual dos fornecedores de IA do NEGOBOT.

O script nunca imprime valores de variáveis secretas nem o texto devolvido pelos
fornecedores. Por defeito lê o ambiente já injectado no container; com --env-file
pode carregar um ficheiro dotenv para testes locais.
"""
from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - permite executar com Python mínimo
    load_dotenv = None


@dataclass(frozen=True)
class Provider:
    name: str
    key_env: str
    model_env: str
    base_url: str | None = None
    gemini: bool = False
    default_model: str = ""


PROVIDERS = (
    Provider("groq", "GROQ_API_KEY", "GROQ_MODEL", "https://api.groq.com/openai/v1"),
    Provider("cerebras", "CEREBRAS_API_KEY", "CEREBRAS_MODEL", "https://api.cerebras.ai/v1"),
    Provider("sambanova", "SAMBANOVA_API_KEY", "SAMBANOVA_MODEL", "https://api.sambanova.ai/v1"),
    Provider("gemini_1", "GEMINI_API_KEY", "GEMINI_MODEL", gemini=True),
    Provider("gemini_2", "GEMINI_API_KEY_2", "GEMINI_MODEL_2", gemini=True),
    Provider(
        "github_models",
        "GITHUB_MODELS_TOKEN",
        "GITHUB_MODELS_MODEL",
        "https://models.inference.ai.azure.com",
    ),
    Provider("mistral", "MISTRAL_API_KEY", "MISTRAL_MODEL", "https://api.mistral.ai/v1"),
    Provider(
        "openrouter",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "https://openrouter.ai/api/v1",
        default_model="openrouter/free",
    ),
)

PROMPT_TEXT = "Reply with the single word OK."
PROMPT_JSON = "Return a JSON object with exactly one boolean key named ok."


def _load_environment(env_file: str | None) -> None:
    if env_file and load_dotenv is not None:
        load_dotenv(env_file, override=False)


def _configured_model(provider: Provider) -> str:
    return (os.getenv(provider.model_env) or provider.default_model).strip()


def _result(provider: str, model: str, status: str, started: float, **extra: Any) -> dict[str, Any]:
    result = {
        "provider": provider,
        "model": model or "-",
        "status": status,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
    result.update(extra)
    return result


def _test_openai_compatible(provider: Provider, key: str, model: str, timeout: float, json_mode: bool) -> dict[str, Any]:
    started = time.monotonic()
    try:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT_JSON if json_mode else PROMPT_TEXT}],
            "temperature": 0,
            "max_tokens": 32,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = requests.post(
            f"{provider.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if response.status_code != 200:
            return _result(provider.name, model, "FAIL", started, http=response.status_code)
        data = response.json()
        choices = data.get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else None
        if not str(content or "").strip():
            return _result(provider.name, model, "FAIL", started, http=200, reason="empty_response")
        return _result(provider.name, model, "PASS", started, http=200)
    except requests.Timeout:
        return _result(provider.name, model, "FAIL", started, reason="timeout")
    except requests.RequestException:
        return _result(provider.name, model, "FAIL", started, reason="network_error")
    except (ValueError, TypeError, KeyError):
        return _result(provider.name, model, "FAIL", started, http=200, reason="invalid_json_response")


def _test_gemini(provider: Provider, key: str, model: str, timeout: float, json_mode: bool) -> dict[str, Any]:
    started = time.monotonic()
    try:
        generation_config: dict[str, Any] = {"temperature": 0, "maxOutputTokens": 32}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"role": "user", "parts": [{"text": PROMPT_JSON if json_mode else PROMPT_TEXT}]}],
                "generationConfig": generation_config,
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            return _result(provider.name, model, "FAIL", started, http=response.status_code)
        data = response.json()
        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
        text = "".join(str(part.get("text") or "") for part in parts)
        if not text.strip():
            return _result(provider.name, model, "FAIL", started, http=200, reason="empty_response")
        return _result(provider.name, model, "PASS", started, http=200)
    except requests.Timeout:
        return _result(provider.name, model, "FAIL", started, reason="timeout")
    except requests.RequestException:
        return _result(provider.name, model, "FAIL", started, reason="network_error")
    except (ValueError, TypeError, KeyError, IndexError):
        return _result(provider.name, model, "FAIL", started, http=200, reason="invalid_json_response")


def test_provider(provider: Provider, timeout: float, json_mode: bool) -> dict[str, Any]:
    key = (os.getenv(provider.key_env) or "").strip()
    model = _configured_model(provider)
    if not key:
        return {"provider": provider.name, "model": model or "-", "status": "SKIP", "reason": "missing_key"}
    if not model:
        return {"provider": provider.name, "model": "-", "status": "SKIP", "reason": "missing_model"}
    if provider.gemini:
        return _test_gemini(provider, key, model, timeout, json_mode)
    return _test_openai_compatible(provider, key, model, timeout, json_mode)


def _print_result(result: dict[str, Any]) -> None:
    fields = [f"{key}={value}" for key, value in result.items()]
    print(" ".join(fields))


def main() -> int:
    parser = argparse.ArgumentParser(description="Testa individualmente os fornecedores de IA configurados.")
    parser.add_argument("--provider", choices=[p.name for p in PROVIDERS] + ["all"], default="all")
    parser.add_argument("--timeout", type=float, default=15.0, help="Timeout por fornecedor em segundos (default: 15).")
    parser.add_argument("--env-file", help="Ficheiro dotenv opcional; no container, prefira o ambiente injectado.")
    parser.add_argument("--json-mode", action="store_true", help="Testa também o formato JSON; por defeito faz um teste simples de texto.")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout deve ser maior que zero")
    _load_environment(args.env_file)
    selected = PROVIDERS if args.provider == "all" else tuple(p for p in PROVIDERS if p.name == args.provider)
    print("AI_PROVIDER_TEST_BEGIN")
    results = []
    for provider in selected:
        result = test_provider(provider, args.timeout, args.json_mode)
        results.append(result)
        _print_result(result)
    passed = sum(result.get("status") == "PASS" for result in results)
    failed = sum(result.get("status") == "FAIL" for result in results)
    skipped = sum(result.get("status") == "SKIP" for result in results)
    print(f"AI_PROVIDER_TEST_SUMMARY passed={passed} failed={failed} skipped={skipped}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
