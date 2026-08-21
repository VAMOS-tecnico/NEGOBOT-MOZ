"""Contratos de ambiente por processo do NEGOBOT.

Este módulo nunca devolve valores de ambiente. Ele apenas valida presença e expõe
um resumo booleano para logs/health checks, reduzindo falhas pouco explicativas.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ServiceProfile:
    required: tuple[str, ...] = ()
    required_any: tuple[tuple[str, ...], ...] = ()
    optional: tuple[str, ...] = ()


PROFILES: dict[str, ServiceProfile] = {
    "api": ServiceProfile(
        required=("FIREBASE_CONFIG",),
        required_any=(("PLATFORM_SECRET_KEY", "ADMIN_TOKEN"),),
        optional=("REDIS_URL", "VIDEO_SERVICE_URL", "VIDEO_SERVICE_TOKEN"),
    ),
    "whatsapp_ingress": ServiceProfile(
        required=("FIREBASE_CONFIG", "EVOLUTION_API_URL", "EVOLUTION_API_KEY"),
        optional=("REDIS_URL", "WHATSAPP_INCOMING_QUEUE", "OMNICHANNEL_INCOMING_QUEUE"),
    ),
    "campaign": ServiceProfile(
        required=("FIREBASE_CONFIG", "EVOLUTION_API_URL", "EVOLUTION_API_KEY"),
        optional=("REDIS_URL", "N8N_CAMPAIGN_WEBHOOK_URL", "N8N_WEBHOOK_SECRET", "CHANNEL_PUBLICATIONS_QUEUE"),
    ),
    "channel_publication": ServiceProfile(
        required=("FIREBASE_CONFIG",),
        optional=("REDIS_URL", "CHANNEL_PUBLICATIONS_QUEUE", "CHANNEL_PUBLICATIONS_SCHEDULED_QUEUE"),
    ),
    "billing": ServiceProfile(
        required=("FIREBASE_CONFIG",),
        optional=("REDIS_URL", "EVOLUTION_API_URL", "EVOLUTION_API_KEY", "LEMONSQUEEZY_API_KEY", "LEMONSQUEEZY_STORE_ID", "LEMONSQUEEZY_WEBHOOK_SECRET"),
    ),
    "video": ServiceProfile(
        required=("REDIS_URL", "VIDEO_SERVICE_TOKEN"),
        optional=("VIDEO_QUEUE", "VIDEO_OUTPUT_DIR", "VIDEO_RETENTION_DAYS"),
    ),
    "ai": ServiceProfile(
        required=("REDIS_URL",),
        optional=(
            "AI_QUEUE",
            "AI_PRIMARY_TIMEOUT",
            "AI_FALLBACK_TIMEOUT",
            "AI_QUEUE_MAX_PER_SECOND",
            "GROQ_API_KEY",
            "GROQ_MODEL",
            "CEREBRAS_API_KEY",
            "CEREBRAS_MODEL",
            "SAMBANOVA_API_KEY",
            "SAMBANOVA_MODEL",
            "GEMINI_API_KEY",
            "GEMINI_API_KEY_2",
            "GEMINI_MODEL",
            "GEMINI_MODEL_2",
            "GITHUB_MODELS_TOKEN",
            "GITHUB_MODELS_MODEL",
            "MISTRAL_API_KEY",
            "MISTRAL_MODEL",
            "OPENROUTER_API_KEY",
            "OPENROUTER_MODEL",
        ),
    ),
    "image": ServiceProfile(
        required=("REDIS_URL",),
        optional=("IMAGE_QUEUE", "IMAGE_PROVIDER", "IMAGE_CALLBACK_URL"),
    ),
    "audio": ServiceProfile(
        required=("REDIS_URL",),
        optional=("AUDIO_QUEUE", "AUDIO_PROVIDER", "AUDIO_OUTPUT_DIR", "ELEVENLABS_API_KEY", "AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION"),
    ),
    "social": ServiceProfile(
        required=("REDIS_URL",),
        optional=("FIREBASE_CONFIG", "SOCIAL_QUEUE", "SOCIAL_CALLBACK_URL"),
    ),
    "mailer": ServiceProfile(
        required=("REDIS_URL",),
        optional=("MAIL_QUEUE", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_USE_TLS", "SMTP_TIMEOUT_SECONDS"),
    ),
}


class EnvironmentContractError(RuntimeError):
    """Indica que um processo não tem o ambiente mínimo do seu perfil."""


def _present(environment: Mapping[str, str], name: str) -> bool:
    return bool(str(environment.get(name, "") or "").strip())


def environment_report(profile: str, environment: Mapping[str, str] | None = None) -> dict[str, object]:
    selected = PROFILES.get(profile)
    if selected is None:
        raise EnvironmentContractError(f"Perfil de ambiente desconhecido: {profile}")
    values = environment if environment is not None else os.environ
    required_missing = [name for name in selected.required if not _present(values, name)]
    alternatives_missing = [
        list(group) for group in selected.required_any if not any(_present(values, name) for name in group)
    ]
    names = set(selected.required) | set(selected.optional)
    for group in selected.required_any:
        names.update(group)
    return {
        "profile": profile,
        "ok": not required_missing and not alternatives_missing,
        "required_missing": required_missing,
        "required_any_missing": alternatives_missing,
        "configured": {name: _present(values, name) for name in sorted(names)},
    }


def enforce_profile(profile: str, environment: Mapping[str, str] | None = None) -> dict[str, object]:
    report = environment_report(profile, environment)
    if not report["ok"]:
        missing = list(report["required_missing"])
        for group in report["required_any_missing"]:
            missing.append("one-of(" + ",".join(group) + ")")
        raise EnvironmentContractError(f"Ambiente incompleto para {profile}: {', '.join(missing)}")
    return report


def current_profile(default: str = "api") -> str:
    return str(os.getenv("NEGOBOT_SERVICE_PROFILE") or default).strip() or default
