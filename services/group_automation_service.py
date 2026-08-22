"""Automação segura para grupos WhatsApp próprios de cada tenant.

Um grupo só entra no módulo quando a identidade WhatsApp guardada no tenant
aparece nos participantes da Evolution com privilégios de administrador. A
função nunca transforma membros do grupo em contactos de marketing.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any
from urllib.parse import quote

import requests

import extensions
from config import Config
from services.ai_queue_service import AIQueueError, request_ai_text
from services.evolution_service import ensure_group_webhook, send_whatsapp

logger = logging.getLogger("negobot-group-automation")

ADMIN_ROLES = {"admin", "superadmin", "super_admin", "creator", "owner"}
GROUP_EVENTS = {"groups.upsert", "groups_upsert", "groups.update", "groups_update", "group.participants.update", "group_participants_update", "group-participants-update"}
OPT_OUT_FIELDS = {"admin_verified", "bot_is_admin"}
GROUP_RETENTION_SECONDS = 7 * 24 * 60 * 60


def _clean(value: Any) -> str:
    return str(value or "").strip()


def normalize_jid(value: Any) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    if raw.endswith("@g.us"):
        return raw
    local = raw.split("@", 1)[0].split(":", 1)[0].split(";", 1)[0]
    digits = re.sub(r"\D", "", local)
    if not digits:
        return ""
    if "@" in raw:
        return f"{digits}@s.whatsapp.net"
    return f"{digits}@s.whatsapp.net"


def normalize_phone(value: Any) -> str:
    local = _clean(value).split("@", 1)[0].split(":", 1)[0].split(";", 1)[0]
    return re.sub(r"\D", "", local)


def group_document_id(group_jid: str) -> str:
    return hashlib.sha256(group_jid.lower().encode("utf-8")).hexdigest()[:40]


def _api_url(path: str, instance_name: str) -> str:
    base = str(Config.EVOLUTION_API_URL or "").rstrip("/")
    return f"{base}/{path}/{quote(str(instance_name).strip())}"


def _headers() -> dict[str, str]:
    return {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}


def _request_json(method: str, path: str, instance_name: str, **kwargs: Any) -> Any:
    response = requests.request(method, _api_url(path, instance_name), headers=_headers(), timeout=25, **kwargs)
    response.raise_for_status()
    return response.json()


def fetch_all_groups(instance_name: str) -> list[dict[str, Any]]:
    payload = _request_json("GET", "group/fetchAllGroups", instance_name, params={"getParticipants": "false"})
    if isinstance(payload, dict):
        payload = payload.get("groups") or payload.get("data") or []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def fetch_group_participants(instance_name: str, group_jid: str) -> list[dict[str, Any]]:
    payload = _request_json("GET", "group/participants", instance_name, params={"groupJid": group_jid})
    if isinstance(payload, dict):
        payload = payload.get("participants") or payload.get("data") or []
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def participant_is_admin(participant: dict[str, Any]) -> bool:
    if bool(participant.get("isAdmin") or participant.get("isSuperAdmin")):
        return True
    role = _clean(participant.get("admin") or participant.get("role") or participant.get("type")).lower()
    return role in ADMIN_ROLES or role.endswith("admin")


def _participant_jid(participant: dict[str, Any]) -> str:
    # Evolution/Baileys may expose an opaque @lid in `id`; phoneNumber is the
    # real WhatsApp identity and must be preferred for admin verification.
    return normalize_jid(participant.get("phoneNumber") or participant.get("phone") or participant.get("jid") or participant.get("participant") or participant.get("id"))


def connected_jids(tenant: dict[str, Any], instance_name: str) -> set[str]:
    candidates = [
        tenant.get("telefone_proprietario"),
        tenant.get("whatsapp_phone"),
        tenant.get("connected_phone"),
        tenant.get("connected_jid"),
        tenant.get("phone"),
    ]
    if str(instance_name).endswith("@s.whatsapp.net") or str(instance_name).isdigit():
        candidates.append(instance_name)
    return {normalize_jid(item) for item in candidates if normalize_jid(item)}


def verify_bot_admin(tenant: dict[str, Any], instance_name: str, participants: list[dict[str, Any]]) -> tuple[bool, str, str]:
    known_jids = connected_jids(tenant, instance_name)
    known_phones = {normalize_phone(item) for item in known_jids}
    if not known_jids:
        return False, "connected_identity_unknown", ""
    for participant in participants:
        jid = _participant_jid(participant)
        if (jid in known_jids or normalize_phone(jid) in known_phones) and participant_is_admin(participant):
            return True, "admin_verified", jid
    return False, "connected_identity_not_admin", ""


def _group_jid(group: dict[str, Any]) -> str:
    jid = _clean(group.get("id") or group.get("jid") or group.get("groupJid"))
    return jid if jid.endswith("@g.us") else ""


def _group_name(group: dict[str, Any]) -> str:
    return _clean(group.get("subject") or group.get("name") or "Grupo WhatsApp")[:180]


def archive_groups_for_instance(instance_name: str, reason: str = "whatsapp_disconnected") -> int:
    """Hide groups immediately; physical deletion is deferred for safe recovery."""
    if extensions.db is None:
        return 0
    now = time.time()
    archived = 0
    documents = extensions.db.collection("whatsapp_groups").where("instance_name", "==", _clean(instance_name)).limit(1000).stream()
    for document in documents:
        document.reference.set({
            "status": "archived",
            "visible": False,
            "archived_at": now,
            "last_error": reason,
        }, merge=True)
        archived += 1
    return archived


def purge_archived_groups(max_age_seconds: int = GROUP_RETENTION_SECONDS) -> int:
    """Delete only archived group metadata older than the recovery window."""
    if extensions.db is None:
        return 0
    cutoff = time.time() - max(3600, int(max_age_seconds))
    deleted = 0
    documents = extensions.db.collection("whatsapp_groups").where("status", "==", "archived").limit(1000).stream()
    for document in documents:
        data = document.to_dict() or {}
        if float(data.get("archived_at") or 0) <= cutoff:
            document.reference.delete()
            deleted += 1
    return deleted


def sync_groups_for_tenant(tenant_id: str, instance_name: str):
    if extensions.db is None:
        extensions.init_extensions()
    if extensions.db is None:
        raise RuntimeError("Firestore indisponível")
    tenant_ref = extensions.db.collection("tenants").document(tenant_id)
    tenant_doc = tenant_ref.get()
    if not tenant_doc.exists:
        raise ValueError("Tenant não encontrado")
    tenant = tenant_doc.to_dict() or {}
    if _clean(tenant.get("instance_name")) != _clean(instance_name):
        raise PermissionError("A instância não pertence a este tenant")

    webhook_configured = ensure_group_webhook(instance_name)
    groups_ref = extensions.db.collection("whatsapp_groups")
    rows: list[dict[str, Any]] = []
    for raw_group in fetch_all_groups(instance_name):
        group_jid = _group_jid(raw_group)
        if not group_jid:
            continue
        participants = fetch_group_participants(instance_name, group_jid)
        verified, reason, bot_jid = verify_bot_admin(tenant, instance_name, participants)
        doc_ref = groups_ref.document(group_document_id(group_jid))
        existing = doc_ref.get().to_dict() if doc_ref.get().exists else {}
        data = {
            "tenant_id": tenant_id,
            "instance_name": instance_name,
            "group_jid": group_jid,
            "name": _group_name(raw_group),
            "bot_jid": bot_jid or existing.get("bot_jid"),
            "bot_is_admin": verified,
            "admin_verified": verified,
            "authorization_reason": reason,
            "admin_verified_at": time.time() if verified else existing.get("admin_verified_at"),
            "status": "active" if verified else "rejected",
            "participant_count": len(participants),
            "last_synced_at": time.time(),
            "last_error": None,
            "visible": True,
            "archived_at": None,
        }
        # A previously configured group keeps settings only while it remains verified.
        if verified:
            data.update({
                "automation_enabled": bool(existing.get("automation_enabled", False)),
                "mention_required": bool(existing.get("mention_required", True)),
                "welcome_enabled": bool(existing.get("welcome_enabled", False)),
                "welcome_message": _clean(existing.get("welcome_message") or "Bem-vindo(a) ao nosso grupo! Escreve @Bot para pedir ajuda.")[:1000],
                "keywords": existing.get("keywords") if isinstance(existing.get("keywords"), list) else [],
            })
        else:
            data.update({"automation_enabled": False, "mention_required": True, "welcome_enabled": False})
        doc_ref.set(data, merge=True)
        rows.append({"id": doc_ref.id, **data})
    return {"groups": rows, "total": len(rows), "verified": sum(1 for item in rows if item.get("admin_verified")), "webhook_configured": webhook_configured}


def authorized_group_jids(tenant_id: str, instance_name: str) -> list[str]:
    if extensions.db is None:
        return []
    documents = extensions.db.collection("whatsapp_groups").where("tenant_id", "==", tenant_id).limit(1000).stream()
    result = []
    for document in documents:
        data = document.to_dict() or {}
        if data.get("instance_name") == instance_name and data.get("admin_verified") and data.get("bot_is_admin") and data.get("status") == "active":
            group_jid = _clean(data.get("group_jid"))
            if group_jid.endswith("@g.us"):
                result.append(group_jid)
    return sorted(set(result))


def _find_tenant_for_instance(instance_name: str) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    if extensions.db is None:
        return None, None
    docs = list(extensions.db.collection("tenants").where("instance_name", "==", instance_name).limit(3).stream())
    if len(docs) != 1:
        return None, None
    return docs[0].id, docs[0].to_dict() or {}


def _event_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    return data if isinstance(data, dict) else {}


def _text_from_payload(data: dict[str, Any]) -> str:
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    context = message.get("extendedTextMessage") if isinstance(message.get("extendedTextMessage"), dict) else {}
    return _clean(message.get("conversation") or context.get("text") or "")


def _mentioned(payload: dict[str, Any], text: str, tenant: dict[str, Any]) -> bool:
    data = _event_data(payload)
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    extended = message.get("extendedTextMessage") if isinstance(message.get("extendedTextMessage"), dict) else {}
    context = extended.get("contextInfo") if isinstance(extended.get("contextInfo"), dict) else {}
    mentioned = context.get("mentionedJid") or context.get("mentionedJids") or []
    known = connected_jids(tenant, str(payload.get("instance") or data.get("instance") or ""))
    known_phones = {normalize_phone(item) for item in known}
    if any(normalize_jid(item) in known or normalize_phone(item) in known_phones for item in mentioned):
        return True
    lowered = text.lower()
    aliases = ("@bot", "@negobot", "#bot", "#negobot", "/bot", "/negobot")
    return any(alias in lowered for alias in aliases)


def _strip_trigger(text: str) -> str:
    return re.sub(r"(?:@|#|/)\s*(?:bot|negobot)(?:\s+moz)?", "", text, flags=re.IGNORECASE).strip(" ,:;-\n")


def _keyword_response(text: str, keywords: Any) -> str:
    lowered = text.lower()
    for item in keywords if isinstance(keywords, list) else []:
        if isinstance(item, dict):
            trigger = _clean(item.get("trigger") or item.get("keyword")).lower()
            response = _clean(item.get("response") or item.get("text"))
        else:
            trigger, response = _clean(item).lower(), ""
        if trigger and trigger in lowered and response:
            return response[:1500]
    return ""


def _log_event(tenant_id: str, group_jid: str, event_id: str, status: str, **fields: Any) -> None:
    if extensions.db is None:
        return
    doc_id = hashlib.sha256(f"{tenant_id}:{group_jid}:{event_id}".encode()).hexdigest()
    extensions.db.collection("group_automation_events").document(doc_id).set({
        "tenant_id": tenant_id,
        "group_jid": group_jid,
        "event_id": event_id,
        "status": status,
        "created_at": time.time(),
        **fields,
    }, merge=True)


def _refresh_group_authorization(tenant_id: str, tenant: dict[str, Any], instance_name: str, group_jid: str, group_name: str | None = None) -> bool:
    participants = fetch_group_participants(instance_name, group_jid)
    verified, reason, bot_jid = verify_bot_admin(tenant, instance_name, participants)
    reference = extensions.db.collection("whatsapp_groups").document(group_document_id(group_jid))
    existing_doc = reference.get()
    existing = existing_doc.to_dict() if existing_doc.exists else {}
    reference.set({
        "tenant_id": tenant_id,
        "instance_name": instance_name,
        "group_jid": group_jid,
        "name": _clean(group_name or existing.get("name") or "Grupo WhatsApp"),
        "bot_jid": bot_jid or existing.get("bot_jid"),
        "bot_is_admin": verified,
        "admin_verified": verified,
        "authorization_reason": reason,
        "admin_verified_at": time.time() if verified else existing.get("admin_verified_at"),
        "status": "active" if verified else "rejected",
        "participant_count": len(participants),
        "last_event_at": time.time(),
        "visible": True,
        "archived_at": None,
        "automation_enabled": bool(existing.get("automation_enabled", False)) if verified else False,
        "mention_required": bool(existing.get("mention_required", True)),
        "welcome_enabled": bool(existing.get("welcome_enabled", False)) if verified else False,
    }, merge=True)
    return verified


def handle_group_message(payload: dict[str, Any]) -> bool:
    if extensions.db is None:
        extensions.init_extensions()
    if extensions.db is None:
        logger.error("Grupo ignorado: Firestore indisponível")
        return True
    data = _event_data(payload)
    key = data.get("key") if isinstance(data.get("key"), dict) else {}
    group_jid = _clean(key.get("remoteJid") or data.get("remoteJid"))
    if not group_jid.endswith("@g.us"):
        return False
    instance_name = _clean(payload.get("instance") or data.get("instance"))
    tenant_id, tenant = _find_tenant_for_instance(instance_name)
    if not tenant_id:
        logger.info("Grupo ignorado: instância sem tenant único instance=%s group=%s", instance_name, group_jid)
        return True
    group_doc = extensions.db.collection("whatsapp_groups").document(group_document_id(group_jid)).get()
    group = group_doc.to_dict() if group_doc.exists else {}
    if group.get("tenant_id") != tenant_id or group.get("instance_name") != instance_name or not group.get("admin_verified") or not group.get("bot_is_admin") or group.get("status") != "active":
        logger.info("Grupo rejeitado por autorização tenant=%s group=%s", tenant_id, group_jid)
        return True
    if not group.get("automation_enabled"):
        return True
    text = _text_from_payload(data)
    event_id = _clean(key.get("id") or payload.get("event_id") or hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest())
    if group.get("mention_required", True) and not _mentioned(payload, text, tenant):
        return True
    prompt_text = _strip_trigger(text)
    response = _keyword_response(prompt_text, group.get("keywords"))
    provider = "keyword"
    if not response and prompt_text:
        try:
            ai_result = request_ai_text(
                tenant_id=tenant_id,
                messages=[{"role": "user", "content": prompt_text}],
                system_prompt=(
                    "És o assistente de um grupo comercial próprio do negócio. Responde em Português de Moçambique, "
                    "com brevidade e profissionalismo. Não inventes preços, stock, links ou políticas. "
                    "Se não souberes, encaminha para a equipa. Nunca envies mensagens privadas nem peças dados sensíveis.\n\n"
                    + _clean(tenant.get("diretrizes_corporativas"))[:5000]
                ),
                request_id=event_id,
            )
            response = _clean(ai_result.get("text"))[:1500]
            provider = _clean(ai_result.get("provider")) or "ai_worker"
        except AIQueueError as exc:
            logger.warning("AI Worker indisponível para grupo tenant=%s reason=%s", tenant_id, exc)
            response = ""
            provider = "ai_worker_unavailable"
    if not response:
        return True
    sent = bool(send_whatsapp(group_jid, response, instance_name=instance_name))
    _log_event(tenant_id, group_jid, event_id, "sent" if sent else "failed", provider=provider, text=text[:1000], response=response[:1500])
    return True


def _participant_values(data: dict[str, Any]) -> list[str]:
    values = data.get("participants") or data.get("participant") or []
    if isinstance(values, (str, dict)):
        values = [values]
    result = []
    for value in values if isinstance(values, list) else []:
        if isinstance(value, dict):
            value = value.get("id") or value.get("jid") or value.get("participant")
        jid = normalize_jid(value)
        if jid:
            result.append(jid)
    return result


def handle_group_metadata_event(payload: dict[str, Any]) -> bool:
    if extensions.db is None:
        return True
    data = _event_data(payload)
    group_jid = _clean(data.get("id") or data.get("groupJid") or data.get("remoteJid"))
    if not group_jid.endswith("@g.us"):
        return False
    instance_name = _clean(payload.get("instance") or data.get("instance"))
    tenant_id, tenant = _find_tenant_for_instance(instance_name)
    if tenant_id:
        _refresh_group_authorization(tenant_id, tenant, instance_name, group_jid, _group_name(data))
    return True


def handle_group_participant_event(payload: dict[str, Any]) -> bool:
    if extensions.db is None:
        extensions.init_extensions()
    if extensions.db is None:
        logger.error("Evento de participantes ignorado: Firestore indisponível")
        return True
    data = _event_data(payload)
    group_jid = _clean(data.get("id") or data.get("groupJid") or data.get("remoteJid"))
    if not group_jid.endswith("@g.us"):
        return False
    instance_name = _clean(payload.get("instance") or data.get("instance"))
    tenant_id, tenant = _find_tenant_for_instance(instance_name)
    if not tenant_id:
        return True
    if not _refresh_group_authorization(tenant_id, tenant, instance_name, group_jid, _group_name(data)):
        return True
    group_doc_ref = extensions.db.collection("whatsapp_groups").document(group_document_id(group_jid))
    group_doc = group_doc_ref.get()
    group = group_doc.to_dict() if group_doc.exists else {}
    if group.get("tenant_id") != tenant_id or not group.get("admin_verified") or not group.get("bot_is_admin") or group.get("status") != "active" or not group.get("automation_enabled") or not group.get("welcome_enabled"):
        return True
    action = _clean(data.get("action") or data.get("type")).lower()
    if action not in {"add", "added"}:
        return True
    event_id = _clean(payload.get("event_id") or data.get("id") or hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest())
    existing = extensions.db.collection("group_automation_events").document(hashlib.sha256(f"{tenant_id}:{group_jid}:{event_id}".encode()).hexdigest()).get()
    if existing.exists:
        return True
    bot_jids = connected_jids(tenant, instance_name)
    new_members = [item for item in _participant_values(data) if item not in bot_jids]
    if not new_members:
        return True
    message = _clean(group.get("welcome_message") or "Bem-vindo(a) ao nosso grupo! Escreve @Bot se precisares de ajuda.")
    sent = bool(send_whatsapp(group_jid, message.replace("{nome}", "novo membro"), instance_name=instance_name))
    _log_event(tenant_id, group_jid, event_id, "welcome_sent" if sent else "welcome_failed", action=action, members=new_members)
    return True


def handle_group_event(payload: dict[str, Any]) -> bool:
    event = _clean(payload.get("event")).lower().replace("/", "_")
    if event in {"messages.upsert", "messages_upsert"}:
        return handle_group_message(payload)
    if event in {"groups.upsert", "groups_upsert", "groups.update", "groups_update"}:
        return handle_group_metadata_event(payload)
    if event in {"group.participants.update", "group_participants_update", "group-participants-update"}:
        return handle_group_participant_event(payload)
    return False
