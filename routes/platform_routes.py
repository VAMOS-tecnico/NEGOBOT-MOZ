import csv
import hashlib
import hmac
import io
import os
import re
import secrets
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

import requests
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

import extensions

platform_bp = Blueprint("platform", __name__, url_prefix="/api/platform")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now():
    return datetime.now(timezone.utc)


def _db():
    if extensions.db is None:
        raise RuntimeError("Base de dados da plataforma indisponível")
    return extensions.db


def _doc_id(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _identity() -> dict[str, Any] | None:
    value = session.get("platform_identity")
    return value if isinstance(value, dict) and value.get("role") else None


def _require_roles(*roles: str) -> Callable:
    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        def wrapped(*args, **kwargs):
            identity = _identity()
            if not identity:
                return jsonify({"error": "autenticação necessária"}), 401
            if identity.get("role") not in roles:
                return jsonify({"error": "permissão insuficiente"}), 403
            return handler(*args, **kwargs)

        return wrapped

    return decorator


def _tenant_for_identity(identity: dict[str, Any]) -> str | None:
    tenant_id = identity.get("tenant_id")
    return str(tenant_id) if tenant_id else None


@platform_bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    identifier = str(payload.get("email") or payload.get("identifier") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not identifier or not password:
        return jsonify({"error": "Introduza o email e a palavra-passe."}), 400

    admin_token = os.getenv("ADMIN_TOKEN", "")
    if identifier in {"admin", "owner", "administrador"} and admin_token and hmac.compare_digest(password, admin_token):
        identity = {"id": "platform-owner", "name": "Administrador", "role": "owner", "tenant_id": None}
        session.clear()
        session["platform_identity"] = identity
        session.permanent = True
        return jsonify({"authenticated": True, "user": identity})

    if not _EMAIL_RE.fullmatch(identifier) or len(password) < 8:
        return jsonify({"error": "Credenciais inválidas."}), 401
    try:
        document = _db().collection("platform_users").document(_doc_id(identifier)).get()
    except Exception:
        return jsonify({"error": "Não foi possível consultar a conta neste momento."}), 503
    if not document.exists:
        return jsonify({"error": "Credenciais inválidas."}), 401
    user = document.to_dict() or {}
    if user.get("status", "active") != "active" or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"error": "Credenciais inválidas."}), 401
    identity = {
        "id": document.id,
        "name": user.get("name") or identifier,
        "email": identifier,
        "role": user.get("role", "client"),
        "tenant_id": user.get("tenant_id"),
    }
    session.clear()
    session["platform_identity"] = identity
    session.permanent = True
    document.reference.set({"last_login_at": _now()}, merge=True)
    return jsonify({"authenticated": True, "user": identity})


@platform_bp.post("/auth/logout")
def logout():
    session.pop("platform_identity", None)
    return jsonify({"authenticated": False})


@platform_bp.get("/auth/me")
def me():
    identity = _identity()
    return jsonify({"authenticated": bool(identity), "user": identity})


@platform_bp.get("/admin/overview")
@_require_roles("owner", "admin")
def admin_overview():
    db = _db()
    tenants = list(db.collection("tenants").stream())
    users = list(db.collection("platform_users").stream())
    return jsonify({
        "role": _identity().get("role"),
        "tenants": len(tenants),
        "users": len(users),
        "active_tenants": sum(1 for item in tenants if (item.to_dict() or {}).get("status", "active") == "active"),
        "features": ["clientes", "instâncias", "campanhas", "integrações", "pagamentos", "auditoria"],
    })


@platform_bp.get("/admin/tenants")
@_require_roles("owner", "admin")
def list_tenants():
    rows = []
    for document in _db().collection("tenants").stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        rows.append(item)
    rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jsonify({"tenants": rows})


@platform_bp.post("/admin/tenants")
@_require_roles("owner", "admin")
def create_tenant():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if len(name) < 2 or not _EMAIL_RE.fullmatch(email) or len(password) < 8:
        return jsonify({"error": "Nome, email válido e palavra-passe com pelo menos 8 caracteres são obrigatórios."}), 400
    db = _db()
    user_ref = db.collection("platform_users").document(_doc_id(email))
    if user_ref.get().exists:
        return jsonify({"error": "Já existe uma conta com este email."}), 409
    tenant_id = f"tnt_{secrets.token_urlsafe(8)}"
    now = _now()
    tenant_ref = db.collection("tenants").document(tenant_id)
    tenant_ref.set({
        "name": name,
        "status": "active",
        "plan": "demonstracao",
        "created_at": now,
        "limits": {"contacts": 500, "campaigns_per_month": 2, "messages_per_campaign": 100},
    })
    user_ref.set({
        "name": name,
        "email": email,
        "role": "client",
        "tenant_id": tenant_id,
        "status": "active",
        "password_hash": generate_password_hash(password),
        "created_at": now,
        "last_login_at": None,
    })
    return jsonify({"created": True, "tenant": {"id": tenant_id, "name": name, "plan": "demonstracao"}}), 201


@platform_bp.get("/client/overview")
@_require_roles("client", "operator")
def client_overview():
    identity = _identity()
    tenant_id = _tenant_for_identity(identity)
    if not tenant_id:
        return jsonify({"error": "tenant não configurado"}), 403
    db = _db()
    tenant = db.collection("tenants").document(tenant_id).get()
    if not tenant.exists:
        return jsonify({"error": "tenant não encontrado"}), 404
    contacts = list(db.collection("contacts").where("tenant_id", "==", tenant_id).limit(500).stream())
    campaigns = list(db.collection("campaigns").where("tenant_id", "==", tenant_id).limit(100).stream())
    return jsonify({
        "role": identity.get("role"),
        "tenant": {"id": tenant_id, **(tenant.to_dict() or {})},
        "contacts": len(contacts),
        "campaigns": len(campaigns),
        "conversations": 0,
        "features": ["contactos", "segmentos", "campanhas", "disparos", "conversas", "assistente", "integração WhatsApp"],
    })


@platform_bp.get("/client/contacts")
@_require_roles("client", "operator")
def list_contacts():
    tenant_id = _tenant_for_identity(_identity())
    rows = []
    for document in _db().collection("contacts").where("tenant_id", "==", tenant_id).limit(500).stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        rows.append(item)
    return jsonify({"contacts": rows})


@platform_bp.post("/client/contacts")
@_require_roles("client", "operator")
def create_contact():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    phone = re.sub(r"\D", "", str(payload.get("phone") or ""))
    if len(name) < 2 or len(phone) < 8:
        return jsonify({"error": "Nome e número de telefone válidos são obrigatórios."}), 400
    tenant_id = _tenant_for_identity(_identity())
    ref = _db().collection("contacts").document()
    ref.set({"tenant_id": tenant_id, "name": name, "phone": phone, "opt_in": bool(payload.get("opt_in", True)), "tags": [], "created_at": _now()})
    return jsonify({"created": True, "contact": {"id": ref.id, "name": name, "phone": phone}}), 201


@platform_bp.get("/client/campaigns")
@_require_roles("client", "operator")
def list_campaigns():
    tenant_id = _tenant_for_identity(_identity())
    rows = []
    for document in _db().collection("campaigns").where("tenant_id", "==", tenant_id).limit(100).stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        rows.append(item)
    rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jsonify({"campaigns": rows})


@platform_bp.post("/client/contacts/import")
@_require_roles("client", "operator")
def import_contacts():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Envie um ficheiro CSV ou XLSX."}), 400
    tenant_id = _tenant_for_identity(_identity())
    rows = []
    filename = uploaded.filename.lower()
    try:
        if filename.endswith(".csv"):
            text = uploaded.read().decode("utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(text)))
        elif filename.endswith(".xlsx"):
            from openpyxl import load_workbook
            workbook = load_workbook(uploaded, read_only=True, data_only=True)
            sheet = workbook.active
            values = list(sheet.values)
            if values:
                headers = [str(item or "").strip().lower() for item in values[0]]
                rows = [dict(zip(headers, value)) for value in values[1:]]
        else:
            return jsonify({"error": "Formato não suportado. Use CSV ou XLSX."}), 400
    except Exception:
        return jsonify({"error": "Não foi possível ler o ficheiro."}), 400
    db = _db()
    existing = {re.sub(r"\D", "", str((doc.to_dict() or {}).get("phone") or "")) for doc in db.collection("contacts").where("tenant_id", "==", tenant_id).limit(5000).stream()}
    batch = db.batch()
    imported = 0
    skipped = 0
    for row in rows[:5000]:
        normalized = {str(key).strip().lower(): value for key, value in row.items()}
        name = str(normalized.get("name") or normalized.get("nome") or "").strip()
        phone = re.sub(r"\D", "", str(normalized.get("phone") or normalized.get("telefone") or normalized.get("whatsapp") or ""))
        if len(name) < 2 or len(phone) < 8 or phone in existing:
            skipped += 1
            continue
        ref = db.collection("contacts").document()
        batch.set(ref, {"tenant_id": tenant_id, "name": name, "phone": phone, "opt_in": str(normalized.get("opt_in") or normalized.get("consentimento") or "true").lower() not in {"false", "0", "nao", "não"}, "tags": [], "created_at": _now()})
        existing.add(phone)
        imported += 1
        if imported % 400 == 0:
            batch.commit()
            batch = db.batch()
    if imported % 400:
        batch.commit()
    return jsonify({"imported": imported, "skipped": skipped, "total_rows": len(rows)})


@platform_bp.post("/client/campaigns")
@_require_roles("client", "operator")
def create_campaign():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    message = str(payload.get("message") or "").strip()
    if len(name) < 2 or not message:
        return jsonify({"error": "Nome e mensagem são obrigatórios."}), 400
    tenant_id = _tenant_for_identity(_identity())
    db = _db()
    contacts = list(db.collection("contacts").where("tenant_id", "==", tenant_id).where("opt_in", "==", True).limit(1000).stream())
    if not contacts:
        return jsonify({"error": "Adicione primeiro contactos com consentimento para receber mensagens."}), 400
    campaign_ref = db.collection("campaigns").document()
    campaign_ref.set({
        "tenant_id": tenant_id,
        "name": name,
        "message": message,
        "instance_name": str(payload.get("instance_name") or "").strip() or None,
        "status": "queued",
        "total": len(contacts),
        "sent": 0,
        "failed": 0,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
    })
    recipients = []
    for contact in contacts:
        data = contact.to_dict() or {}
        phone = re.sub(r"\D", "", str(data.get("phone") or ""))
        if not phone:
            continue
        recipient_ref = db.collection("campaign_recipients").document(f"{campaign_ref.id}_{contact.id}")
        recipient_ref.set({"tenant_id": tenant_id, "campaign_id": campaign_ref.id, "contact_id": contact.id, "phone": phone, "status": "queued", "attempts": 0})
        recipients.append(phone)
    campaign_ref.set({"total": len(recipients)}, merge=True)
    try:
        import redis
        queue = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/1"), decode_responses=True)
        queue.rpush("negobot:campaigns", campaign_ref.id)
    except Exception as exc:
        campaign_ref.set({"status": "failed", "error": "Fila indisponível"}, merge=True)
        return jsonify({"error": "Não foi possível iniciar a fila da campanha."}), 503
    return jsonify({"created": True, "campaign": {"id": campaign_ref.id, "name": name, "status": "queued", "total": len(recipients)}}), 201


@platform_bp.post("/client/campaigns/<campaign_id>/actions/<action>")
@_require_roles("client", "operator")
def campaign_action(campaign_id: str, action: str):
    tenant_id = _tenant_for_identity(_identity())
    reference = _db().collection("campaigns").document(campaign_id)
    document = reference.get()
    if not document.exists or (document.to_dict() or {}).get("tenant_id") != tenant_id:
        return jsonify({"error": "Campanha não encontrada."}), 404
    if action not in {"pause", "resume", "cancel"}:
        return jsonify({"error": "Ação não suportada."}), 400
    state = {"pause": "paused", "resume": "queued", "cancel": "cancelled"}[action]
    reference.set({"status": state, "updated_at": _now()}, merge=True)
    try:
        import redis
        queue = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/1"), decode_responses=True)
        queue.set(f"negobot:campaign:{campaign_id}:control", action, ex=86400)
        if action == "resume":
            queue.rpush("negobot:campaigns", campaign_id)
    except Exception:
        pass
    return jsonify({"updated": True, "campaign_id": campaign_id, "status": state})


_INTEGRATION_DEFAULTS = {
    "evolution": {"label": "Evolution API", "kind": "WhatsApp e webhooks", "env": "EVOLUTION_API_KEY"},
    "groq": {"label": "Groq AI", "kind": "Conversação, Whisper e Vision", "env": "GROQ_API_KEY"},
    "firebase": {"label": "Firebase Firestore", "kind": "Dados e histórico", "env": "FIREBASE_CONFIG"},
    "redis": {"label": "Redis Queue", "kind": "Fila de campanhas", "env": "REDIS_URL"},
    "n8n": {"label": "n8n Automations", "kind": "Workflows e automações", "env": "N8N_HOST"},
}


@platform_bp.get("/admin/integrations")
@_require_roles("owner", "admin")
def list_integrations():
    db = _db()
    stored = {doc.id: (doc.to_dict() or {}) for doc in db.collection("platform_integrations").stream()}
    rows = []
    for key, default in _INTEGRATION_DEFAULTS.items():
        item = {"key": key, **default, **stored.get(key, {})}
        configured = bool(os.getenv(default["env"], "").strip()) if default["env"] != "REDIS_URL" else True
        item["configured"] = configured
        item.pop("env", None)
        rows.append(item)
    return jsonify({"integrations": rows})


@platform_bp.patch("/admin/integrations/<integration_key>")
@_require_roles("owner", "admin")
def update_integration(integration_key: str):
    if integration_key not in _INTEGRATION_DEFAULTS:
        return jsonify({"error": "Integração não encontrada."}), 404
    payload = request.get_json(silent=True) or {}
    allowed = {key: str(payload[key]).strip() for key in ("label", "public_url", "notes") if key in payload}
    if "label" in allowed and not 2 <= len(allowed["label"]) <= 80:
        return jsonify({"error": "O nome da integração deve ter entre 2 e 80 caracteres."}), 400
    _db().collection("platform_integrations").document(integration_key).set({**allowed, "updated_at": _now(), "updated_by": _identity().get("id")}, merge=True)
    return jsonify({"updated": True, "key": integration_key, "fields": sorted(allowed)})


@platform_bp.get("/client/integration/status")
@_require_roles("client", "operator")
def client_integration_status():
    tenant_id = _tenant_for_identity(_identity())
    tenant_doc = _db().collection("tenants").document(tenant_id).get()
    tenant = tenant_doc.to_dict() or {}
    instance_name = tenant.get("instance_name") or tenant_id
    base_url = str(os.getenv("EVOLUTION_API_URL", "")).rstrip("/")
    api_key = os.getenv("EVOLUTION_API_KEY", "")
    state = "not_configured"
    if base_url and api_key:
        try:
            response = requests.get(f"{base_url}/instance/connectionState/{instance_name}", headers={"apikey": api_key}, timeout=8)
            if response.ok:
                state = str((response.json() or {}).get("instance", {}).get("state") or (response.json() or {}).get("state") or "unknown")
            else:
                state = "offline"
        except requests.RequestException:
            state = "offline"
    return jsonify({"instance_name": instance_name, "state": state, "configured": bool(tenant.get("instance_name"))})


@platform_bp.get("/client/assistant")
@_require_roles("client", "operator")
def get_assistant_settings():
    tenant_id = _tenant_for_identity(_identity())
    document = _db().collection("tenants").document(tenant_id).get()
    data = document.to_dict() or {}
    return jsonify({
        "diretrizes_corporativas": data.get("diretrizes_corporativas", ""),
        "base_conhecimento_documentos": data.get("base_conhecimento_documentos", ""),
        "timeout_humano_minutos": data.get("timeout_humano_minutos", 15),
        "models": {"text": os.getenv("GROQ_MODEL", "configured"), "vision": os.getenv("GROQ_VISION_MODEL", "configured")},
    })


@platform_bp.patch("/client/assistant")
@_require_roles("client", "operator")
def update_assistant_settings():
    tenant_id = _tenant_for_identity(_identity())
    payload = request.get_json(silent=True) or {}
    allowed = {}
    if "diretrizes_corporativas" in payload:
        allowed["diretrizes_corporativas"] = str(payload["diretrizes_corporativas"])[:12000]
    if "base_conhecimento_documentos" in payload:
        allowed["base_conhecimento_documentos"] = str(payload["base_conhecimento_documentos"])[:12000]
    if "timeout_humano_minutos" in payload:
        try:
            allowed["timeout_humano_minutos"] = max(1, min(240, int(payload["timeout_humano_minutos"])))
        except (TypeError, ValueError):
            return jsonify({"error": "Timeout inválido."}), 400
    if not allowed:
        return jsonify({"error": "Nenhuma definição válida foi enviada."}), 400
    _db().collection("tenants").document(tenant_id).set({**allowed, "updated_at": _now()}, merge=True)
    return jsonify({"updated": True, "fields": sorted(allowed)})


@platform_bp.get("/client/conversations")
@_require_roles("client", "operator")
def list_conversations():
    tenant_id = _tenant_for_identity(_identity())
    rows = []
    for document in _db().collection("clientes_bot").document(tenant_id).collection("conversas").limit(200).stream():
        item = document.to_dict() or {}
        item["phone"] = document.id
        rows.append(item)
    return jsonify({"conversations": rows})


@platform_bp.post("/client/conversations/<phone>/handoff")
@_require_roles("client", "operator")
def conversation_handoff(phone: str):
    tenant_id = _tenant_for_identity(_identity())
    clean_phone = re.sub(r"\D", "", phone)
    if len(clean_phone) < 8:
        return jsonify({"error": "Telefone inválido."}), 400
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode") or "").lower()
    if mode not in {"bot", "humano"}:
        return jsonify({"error": "O modo deve ser bot ou humano."}), 400
    reference = _db().collection("clientes_bot").document(tenant_id).collection("conversas").document(clean_phone)
    if not reference.get().exists:
        return jsonify({"error": "Conversa não encontrada."}), 404
    reference.set({"status_atendimento": mode, "ultima_interacao": _now()}, merge=True)
    return jsonify({"updated": True, "phone": clean_phone, "mode": mode})


@platform_bp.get("/client/plan")
@_require_roles("client", "operator")
def client_plan():
    tenant_id = _tenant_for_identity(_identity())
    document = _db().collection("tenants").document(tenant_id).get()
    data = document.to_dict() or {}
    return jsonify({
        "plan": data.get("plano", data.get("plan", "demonstracao")),
        "plan_name": data.get("nome_plano", "Demonstração"),
        "status": data.get("status_plano", data.get("status", "demonstracao")),
        "expires_at": data.get("data_expiracao"),
        "mass_broadcast": bool(data.get("disparo_liberado", False)),
        "limits": data.get("limits", {}),
    })


@platform_bp.post("/client/payments/mpesa/verify")
@_require_roles("client", "operator")
def verify_mpesa_payment():
    payload = request.get_json(silent=True) or {}
    message_text = str(payload.get("message_text") or "").strip()
    client_phone = str(payload.get("client_phone") or "").strip()
    if not message_text:
        return jsonify({"error": "Introduza o código ou SMS do M-Pesa."}), 400
    tenant_id = _tenant_for_identity(_identity())
    try:
        from services.payment_service import validar_e_ativar_pagamento_mpesa
        response = validar_e_ativar_pagamento_mpesa(tenant_id, client_phone, message_text)
    except Exception:
        return jsonify({"error": "O serviço de pagamentos está temporariamente indisponível."}), 503
    return jsonify({"processed": True, "response": response})



def _audit(event: str, actor: dict[str, Any] | None, tenant_id: str | None = None, metadata: dict[str, Any] | None = None):
    try:
        _db().collection("audit_events").add({
            "event": event,
            "actor_id": (actor or {}).get("id"),
            "actor_role": (actor or {}).get("role"),
            "tenant_id": tenant_id,
            "metadata": metadata or {},
            "created_at": _now(),
        })
    except Exception:
        pass


@platform_bp.get("/admin/audit")
@_require_roles("owner", "admin")
def list_audit_events():
    rows = []
    for document in _db().collection("audit_events").limit(200).stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        rows.append(item)
    return jsonify({"events": rows})


@platform_bp.get("/admin/health")
@_require_roles("owner", "admin")
def admin_health():
    services = {"backend": "online", "firestore": "online", "redis": "unknown", "evolution": "unknown"}
    try:
        import redis
        redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/1"), decode_responses=True).ping()
        services["redis"] = "online"
    except Exception:
        services["redis"] = "offline"
    base_url = str(os.getenv("EVOLUTION_API_URL", "")).rstrip("/")
    if base_url and os.getenv("EVOLUTION_API_KEY"):
        try:
            response = requests.get(f"{base_url}/instance/fetchInstances", headers={"apikey": os.getenv("EVOLUTION_API_KEY")}, timeout=8)
            services["evolution"] = "online" if response.ok else "degraded"
        except requests.RequestException:
            services["evolution"] = "offline"
    return jsonify({"services": services, "worker": "managed by Docker Compose"})
