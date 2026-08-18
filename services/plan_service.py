"""Catálogo comercial e limites operacionais da NEGOBOT-MOZ.

Este módulo é a única fonte de verdade para preços, benefícios e limites.
Os IDs `basico`, `medio` e `premium` permanecem compatíveis com pagamentos existentes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


TABELA_PLANOS: dict[float, dict[str, Any]] = {
    500.0: {
        "id": "basico",
        "nome": "Plano Básico",
        "price_usd": 8,
        "dias_validade": 30,
        "disparo_liberado": False,
        "limite_conversas": 1500,
        "limite_contactos": 1500,
        "campanhas_por_mes": 2,
        "lugares_equipa": 1,
        "canais_incluidos": ["whatsapp"],
        "canais_adicionais": 0,
        "ia_media": False,
        "api_incluida": False,
        "beneficios": [
            "Até 1.500 conversas por mês",
            "FAQ, horário e catálogo em texto",
            "1 número de WhatsApp",
            "1 utilizador",
            "Suporte básico até 24 horas",
        ],
    },
    1000.0: {
        "id": "medio",
        "nome": "Plano Médio",
        "price_usd": 16,
        "dias_validade": 30,
        "disparo_liberado": False,
        "limite_conversas": 5000,
        "limite_contactos": 5000,
        "campanhas_por_mes": 10,
        "lugares_equipa": 3,
        "canais_incluidos": ["whatsapp"],
        "canais_adicionais": 1,
        "ia_media": True,
        "api_incluida": False,
        "beneficios": [
            "Até 5.000 conversas por mês",
            "WhatsApp + 1 canal adicional aprovado",
            "Fotos e leitura básica de Excel",
            "Até 3 utilizadores",
            "Campanhas básicas e relatórios",
            "Suporte prioritário até 12 horas",
        ],
    },
    1500.0: {
        "id": "premium",
        "nome": "Plano Premium",
        "price_usd": 24,
        "dias_validade": 30,
        "disparo_liberado": True,
        "limite_conversas": 15000,
        "limite_contactos": 15000,
        "campanhas_por_mes": 25,
        "lugares_equipa": 5,
        "canais_incluidos": ["whatsapp"],
        "canais_adicionais": 3,
        "ia_media": True,
        "api_incluida": False,
        "beneficios": [
            "Até 15.000 conversas por mês",
            "WhatsApp + até 3 canais adicionais aprovados",
            "IA avançada, áudio, PDFs e documentos",
            "Até 5 utilizadores",
            "Campanhas e disparos em massa",
            "Suporte dedicado e configuração assistida",
        ],
    },
}

ADDONS: dict[str, dict[str, Any]] = {
    "canais_plus": {
        "name": "Pacote Canais+",
        "description": "Até 2 canais adicionais aprovados",
        "price_mt": 500,
        "price_usd": 8,
        "type": "recurring",
    },
    "campanhas_avancadas": {
        "name": "Campanhas avançadas",
        "description": "Segmentação e orquestração adicional",
        "price_mt": 500,
        "price_usd": 8,
        "type": "recurring",
    },
    "utilizador_adicional": {
        "name": "Utilizador adicional",
        "description": "Mais um lugar na equipa do tenant",
        "price_mt": 100,
        "price_usd": 2,
        "type": "recurring",
    },
}

DEMO_ENTITLEMENTS: dict[str, Any] = {
    "plan_id": "demonstracao",
    "plan_name": "Demonstração",
    "conversation_limit": 500,
    "contact_limit": 500,
    "campaigns_per_month": 2,
    "team_seats": 1,
    "included_channels": ["whatsapp"],
    "additional_channel_slots": 0,
    "mass_broadcast": False,
    "ai_media": False,
    "api_enabled": False,
    "video_enabled": False,
    "document_ai": False,
    "audio_ai": False,
    "image_ai": False,
    "trial_access": False,
    "trial_access_level": "standard",
}

PLAN_BY_ID = {data["id"]: data for data in TABELA_PLANOS.values()}


def trial_premium_entitlements() -> dict[str, Any]:
    """Acesso Premium temporário do trial; nunca altera o plano pago do tenant."""
    premium = PLAN_BY_ID["premium"]
    return {
        "plan_id": "demonstracao",
        "plan_name": "Demonstração Premium",
        "conversation_limit": premium["limite_conversas"],
        "contact_limit": premium["limite_contactos"],
        "campaigns_per_month": premium["campanhas_por_mes"],
        "team_seats": premium["lugares_equipa"],
        "included_channels": list(premium["canais_incluidos"]),
        "additional_channel_slots": premium["canais_adicionais"],
        "mass_broadcast": True,
        "ai_media": True,
        "api_enabled": bool(premium["api_incluida"]),
        "video_enabled": True,
        "document_ai": True,
        "audio_ai": True,
        "image_ai": True,
        "trial_access": True,
        "trial_access_level": "premium",
    }


def plan_for_id(plan_id: str | None) -> dict[str, Any] | None:
    """Obter uma cópia do plano sem expor referências mutáveis do catálogo."""
    return deepcopy(PLAN_BY_ID.get(str(plan_id or "").strip().lower()))


def entitlements_for_tenant(tenant: dict[str, Any] | None) -> dict[str, Any]:
    """Calcular limites a partir do plano efectivo, com fallback seguro para demonstração."""
    data = tenant or {}
    plan_id = str(data.get("plan_id") or data.get("plano") or data.get("plan") or "demonstracao").strip().lower()
    plan = plan_for_id(plan_id)
    trial_status = str(data.get("trial_status") or "").strip().lower()
    if trial_status == "trial_active" and not data.get("plan_rules_version") and not (str(data.get("status_plano") or data.get("status") or "").lower() in {"ativo", "active", "paid"}):
        from services.trial_service import is_expired as trial_is_expired
        if not trial_is_expired(data):
            return trial_premium_entitlements()
    if not plan or str(data.get("status_plano") or data.get("status") or "").lower() not in {"ativo", "active"}:
        result = deepcopy(DEMO_ENTITLEMENTS)
        stored_limits = data.get("limits") or {}
        for key in ("conversation_limit", "contact_limit", "campaigns_per_month", "team_seats"):
            if key in stored_limits and isinstance(stored_limits[key], int):
                result[key] = stored_limits[key]
        return result
    result = {
        "plan_id": plan["id"],
        "plan_name": plan["nome"],
        "conversation_limit": plan["limite_conversas"],
        "contact_limit": plan["limite_contactos"],
        "campaigns_per_month": plan["campanhas_por_mes"],
        "team_seats": plan["lugares_equipa"],
        "included_channels": list(plan["canais_incluidos"]),
        "additional_channel_slots": plan["canais_adicionais"],
        "mass_broadcast": bool(plan["disparo_liberado"]),
        "ai_media": bool(plan["ia_media"]),
        "api_enabled": bool(plan["api_incluida"]),
        "video_enabled": bool(plan["id"] == "premium"),
        "document_ai": bool(plan["id"] in {"medio", "premium"}),
        "audio_ai": bool(plan["id"] == "premium"),
        "image_ai": bool(plan["id"] == "premium"),
        "trial_access": False,
        "trial_access_level": "paid",
    }
    # Clientes pagos antes desta tabela são grandfathered até à renovação.
    # Assim, uma alteração comercial não corta silenciosamente conversas ou campanhas.
    if not data.get("plan_rules_version"):
        if plan["id"] in {"medio", "premium"}:
            result["conversation_limit"] = data.get("limite_conversas") or None
            result["contact_limit"] = None
            result["campaigns_per_month"] = None
            result["team_seats"] = 100
    return result


def plan_channel_limit(tenant: dict[str, Any] | None) -> int:
    entitlements = entitlements_for_tenant(tenant)
    return len(entitlements["included_channels"]) + int(entitlements["additional_channel_slots"])


def public_plan_rows() -> list[dict[str, Any]]:
    """Serializar o catálogo para a API, sem segredos nem dados de tenant."""
    rows = []
    for amount, data in sorted(TABELA_PLANOS.items()):
        rows.append({
            "id": data["id"],
            "name": data["nome"],
            "price_mt": int(amount),
            "price_usd": int(data["price_usd"]),
            "validity_days": data["dias_validade"],
            "conversation_limit": data["limite_conversas"],
            "contact_limit": data["limite_contactos"],
            "campaigns_per_month": data["campanhas_por_mes"],
            "team_seats": data["lugares_equipa"],
            "included_channels": list(data["canais_incluidos"]),
            "additional_channel_slots": data["canais_adicionais"],
            "mass_broadcast": bool(data["disparo_liberado"]),
            "ai_media": bool(data["ia_media"]),
            "benefits": list(data["beneficios"]),
        })
    return rows
