import csv
import hashlib
import hmac
import io
import os
import re
import secrets
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable
from urllib.parse import quote, urlparse

import requests
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

import extensions

platform_bp = Blueprint("platform", __name__, url_prefix="/api/platform")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW_SECONDS = 900
_LOGIN_MAX_ATTEMPTS = 8


def _request_key(identifier: str) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    address = forwarded or request.remote_addr or "unknown"
    return f"{address}:{identifier[:160]}"


def _login_allowed(identifier: str) -> bool:
    now = time.time()
    key = _request_key(identifier)
    recent = [stamp for stamp in _LOGIN_ATTEMPTS.get(key, []) if now - stamp < _LOGIN_WINDOW_SECONDS]
    if len(recent) >= _LOGIN_MAX_ATTEMPTS:
        _LOGIN_ATTEMPTS[key] = recent
        return False
    recent.append(now)
    _LOGIN_ATTEMPTS[key] = recent
    return True


@platform_bp.before_request
def _same_origin_mutation_guard():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.path in {"/api/platform/auth/login", "/api/platform/auth/logout"}:
        return None
    origin = request.headers.get("Origin")
    if origin:
        origin_host = urlparse(origin).netloc
        if origin_host and origin_host != request.host:
            return jsonify({"error": "Origem da operação não autorizada."}), 403
    return None


def _now():
    return datetime.now(timezone.utc)


def _plan_expired(data: dict[str, Any], now: datetime | None = None) -> bool:
    data = data if isinstance(data, dict) else {}
    expiry = data.get("data_expiracao")
    if isinstance(expiry, str) and expiry.strip():
        try:
            expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        except ValueError:
            expiry = None
    if not isinstance(expiry, datetime) and str(data.get("status_plano", data.get("status", ""))).lower() in {"demonstracao", "trial"}:
        anchor = data.get("data_ativacao") or data.get("created_at")
        if isinstance(anchor, str) and anchor.strip():
            try:
                anchor = datetime.fromisoformat(anchor.replace("Z", "+00:00"))
            except ValueError:
                anchor = None
        if isinstance(anchor, datetime):
            expiry = anchor + timedelta(days=2)
    if not isinstance(expiry, datetime):
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return (now or _now()) >= expiry


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


def _require_tenant_roles(*tenant_roles: str) -> Callable:
    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        def wrapped(*args, **kwargs):
            identity = _identity()
            if not identity:
                return jsonify({"error": "autenticação necessária"}), 401
            if identity.get("role") not in {"client", "operator"}:
                return jsonify({"error": "A operação exige uma conta de tenant."}), 403
            if identity.get("tenant_role") not in tenant_roles:
                return jsonify({"error": "A tua função não permite esta operação."}), 403
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
    if not _login_allowed(identifier):
        return jsonify({"error": "Demasiadas tentativas. Aguarda alguns minutos antes de tentar novamente."}), 429

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
        "tenant_role": user.get("tenant_role"),
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
        "email": email,
        "account_email": email,
        "empresa_nome": name,
        "status": "active",
        "plan": "demonstracao",
        "plano": "demonstracao",
        "nome_plano": "Demonstração",
        "status_plano": "demonstracao",
        "data_ativacao": now,
        "data_expiracao": now + timedelta(days=2),
        "created_at": now,
        "limits": {"contacts": 500, "campaigns_per_month": 2, "messages_per_campaign": 100},
    })
    user_ref.set({
        "name": name,
        "email": email,
        "role": "client",
        "tenant_id": tenant_id,
        "tenant_role": "owner",
        "status": "active",
        "password_hash": generate_password_hash(password),
        "created_at": now,
        "last_login_at": None,
    })
    return jsonify({"created": True, "tenant": {"id": tenant_id, "name": name, "plan": "demonstracao"}}), 201


@platform_bp.get("/client/team")
@_require_roles("client", "operator")
def list_tenant_team():
    tenant_id = _tenant_for_identity(_identity())
    rows = []
    for document in _db().collection("platform_users").where("tenant_id", "==", tenant_id).limit(100).stream():
        item = document.to_dict() or {}
        rows.append({
            "id": document.id,
            "name": item.get("name", ""),
            "email": item.get("email", ""),
            "role": item.get("role", "client"),
            "tenant_role": item.get("tenant_role", "viewer"),
            "status": item.get("status", "active"),
            "created_at": item.get("created_at"),
            "last_login_at": item.get("last_login_at"),
        })
    rows.sort(key=lambda item: item.get("name", "").lower())
    return jsonify({"users": rows, "current_role": (_identity() or {}).get("tenant_role")})


@platform_bp.post("/client/team")
@_require_tenant_roles("owner")
def create_tenant_operator():
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
    tenant_id = _tenant_for_identity(_identity())
    now = _now()
    user_ref.set({
        "name": name,
        "email": email,
        "role": "operator",
        "tenant_role": "operator",
        "tenant_id": tenant_id,
        "status": "active",
        "password_hash": generate_password_hash(password),
        "created_at": now,
        "last_login_at": None,
    })
    _audit("tenant_operator_created", _identity(), tenant_id, {"user_id": user_ref.id})
    return jsonify({"created": True, "user": {"id": user_ref.id, "name": name, "email": email, "role": "operator", "tenant_role": "operator", "status": "active"}}), 201


@platform_bp.patch("/client/team/<user_id>")
@_require_tenant_roles("owner")
def update_tenant_operator(user_id: str):
    tenant_id = _tenant_for_identity(_identity())
    reference = _db().collection("platform_users").document(user_id)
    document = reference.get()
    data = document.to_dict() if document.exists else None
    if not data or data.get("tenant_id") != tenant_id:
        return jsonify({"error": "Utilizador não encontrado neste tenant."}), 404
    if data.get("tenant_role") == "owner":
        return jsonify({"error": "O proprietário principal não pode ser alterado por esta operação."}), 400
    payload = request.get_json(silent=True) or {}
    allowed = {}
    if "status" in payload:
        status = str(payload.get("status") or "").lower()
        if status not in {"active", "suspended"}:
            return jsonify({"error": "Estado inválido."}), 400
        allowed["status"] = status
    if "tenant_role" in payload:
        role = str(payload.get("tenant_role") or "").lower()
        if role not in {"operator", "viewer"}:
            return jsonify({"error": "Função inválida."}), 400
        allowed["tenant_role"] = role
        allowed["role"] = "operator" if role == "operator" else "client"
    if not allowed:
        return jsonify({"error": "Nenhuma alteração válida foi enviada."}), 400
    allowed["updated_at"] = _now()
    reference.set(allowed, merge=True)
    _audit("tenant_operator_updated", _identity(), tenant_id, {"user_id": user_id, "fields": sorted(allowed)})
    return jsonify({"updated": True, "user_id": user_id, "fields": sorted(allowed)})


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


_SOCIAL_PROFILE_KEYS = ("facebook", "instagram", "twitter_x", "tiktok", "telegram", "linkedin")


@platform_bp.get("/client/profile")
@_require_roles("client", "operator")
def get_client_profile():
    identity = _identity() or {}
    tenant_id = _tenant_for_identity(identity)
    tenant = _db().collection("tenants").document(tenant_id).get().to_dict() or {}
    socials = tenant.get("redes_sociais") if isinstance(tenant.get("redes_sociais"), dict) else {}
    return jsonify({
        "email": tenant.get("account_email") or tenant.get("email") or identity.get("email"),
        "empresa_nome": tenant.get("empresa_nome") or tenant.get("name", ""),
        "nicho": tenant.get("nicho", ""),
        "email_corporativo": tenant.get("email_corporativo", ""),
        "redes_sociais": {key: str(socials.get(key) or "") for key in _SOCIAL_PROFILE_KEYS},
        "instance_name": tenant.get("instance_name"),
        "status_conexao": tenant.get("evolution_state", "desconectado"),
    })


@platform_bp.patch("/client/profile")
@_require_tenant_roles("owner", "operator")
def update_client_profile():
    payload = request.get_json(silent=True) or {}
    tenant_id = _tenant_for_identity(_identity())
    changes = {}
    if "empresa_nome" in payload:
        value = str(payload.get("empresa_nome") or "").strip()[:160]
        if len(value) < 2:
            return jsonify({"error": "Indica o nome da empresa."}), 400
        changes["empresa_nome"] = value
        changes["name"] = value
    if "nicho" in payload:
        changes["nicho"] = str(payload.get("nicho") or "").strip()[:160]
    if "email_corporativo" in payload:
        email = str(payload.get("email_corporativo") or "").strip().lower()
        if email and not _EMAIL_RE.fullmatch(email):
            return jsonify({"error": "Indica um email corporativo válido."}), 400
        changes["email_corporativo"] = email
    if "redes_sociais" in payload:
        if not isinstance(payload.get("redes_sociais"), dict):
            return jsonify({"error": "As redes sociais devem ser enviadas como objeto."}), 400
        changes["redes_sociais"] = {
            key: str(payload["redes_sociais"].get(key) or "").strip()[:400]
            for key in _SOCIAL_PROFILE_KEYS
        }
    if not changes:
        return jsonify({"error": "Nenhuma alteração de perfil foi enviada."}), 400
    changes["updated_at"] = _now()
    tenant_ref = _db().collection("tenants").document(tenant_id)
    tenant_ref.set(changes, merge=True)
    current_tenant = tenant_ref.get().to_dict() or {}
    instance_name = str(current_tenant.get("instance_name") or "").strip()
    if instance_name:
        _db().collection("clientes_bot").document(instance_name).set({
            key: changes[key] for key in ("empresa_nome", "nicho", "email_corporativo", "redes_sociais") if key in changes
        }, merge=True)
    _audit("client_profile_updated", _identity(), tenant_id, {"fields": sorted(changes)})
    return jsonify({"updated": True, "fields": sorted(changes)})


@platform_bp.get("/client/contacts")
@_require_roles("client", "operator")
def list_contacts():
    tenant_id = _tenant_for_identity(_identity())
    search = str(request.args.get("search") or "").strip().lower()[:120]
    tag = str(request.args.get("tag") or "").strip().lower()[:80]
    opt_in_filter = str(request.args.get("opt_in") or "").strip().lower()
    query = _db().collection("contacts").where("tenant_id", "==", tenant_id)
    if tag:
        query = query.where("tags", "array_contains", tag)
    if opt_in_filter in {"true", "false"}:
        query = query.where("opt_in", "==", opt_in_filter == "true")
    rows = []
    for document in query.limit(1000).stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        item.setdefault("tags", [])
        if search and search not in f"{item.get('name', '')} {item.get('phone', '')}".lower():
            continue
        if item.get("status", "active") == "archived":
            continue
        rows.append(item)
    rows.sort(key=lambda item: str(item.get("name") or "").lower())
    return jsonify({"contacts": rows, "count": len(rows), "filters": {"search": search, "tag": tag, "opt_in": opt_in_filter or None}})


@platform_bp.post("/client/contacts")
@_require_roles("client", "operator")
def create_contact():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    phone = re.sub(r"\D", "", str(payload.get("phone") or ""))
    if len(name) < 2 or len(phone) < 8:
        return jsonify({"error": "Nome e número de telefone válidos são obrigatórios."}), 400
    tenant_id = _tenant_for_identity(_identity())
    tags = sorted({str(item).strip().lower() for item in (payload.get("tags") or []) if str(item).strip()})[:20]
    ref = _db().collection("contacts").document()
    ref.set({"tenant_id": tenant_id, "name": name, "phone": phone, "opt_in": bool(payload.get("opt_in", True)), "tags": tags, "status": "active", "created_at": _now(), "updated_at": _now()})
    _audit("contact_created", _identity(), tenant_id, {"contact_id": ref.id})
    return jsonify({"created": True, "contact": {"id": ref.id, "name": name, "phone": phone, "opt_in": bool(payload.get("opt_in", True)), "tags": tags}}), 201


@platform_bp.patch("/client/contacts/<contact_id>")
@_require_roles("client", "operator")
def update_contact(contact_id: str):
    tenant_id = _tenant_for_identity(_identity())
    reference = _db().collection("contacts").document(contact_id)
    document = reference.get()
    data = document.to_dict() if document.exists else None
    if not data or data.get("tenant_id") != tenant_id or data.get("status", "active") == "archived":
        return jsonify({"error": "Contacto não encontrado neste tenant."}), 404
    payload = request.get_json(silent=True) or {}
    changes = {}
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if len(name) < 2:
            return jsonify({"error": "Nome de contacto inválido."}), 400
        changes["name"] = name
    if "phone" in payload:
        phone = re.sub(r"\D", "", str(payload.get("phone") or ""))
        if len(phone) < 8:
            return jsonify({"error": "Número de contacto inválido."}), 400
        changes["phone"] = phone
    if "opt_in" in payload:
        changes["opt_in"] = bool(payload.get("opt_in"))
    if "tags" in payload:
        if not isinstance(payload.get("tags"), list):
            return jsonify({"error": "As etiquetas devem ser uma lista."}), 400
        changes["tags"] = sorted({str(item).strip().lower() for item in payload["tags"] if str(item).strip()})[:20]
    if not changes:
        return jsonify({"error": "Nenhuma alteração válida foi enviada."}), 400
    changes["updated_at"] = _now()
    reference.set(changes, merge=True)
    _audit("contact_updated", _identity(), tenant_id, {"contact_id": contact_id, "fields": sorted(changes)})
    return jsonify({"updated": True, "contact_id": contact_id, "fields": sorted(changes)})


@platform_bp.delete("/client/contacts/<contact_id>")
@_require_roles("client", "operator")
def archive_contact(contact_id: str):
    tenant_id = _tenant_for_identity(_identity())
    reference = _db().collection("contacts").document(contact_id)
    document = reference.get()
    data = document.to_dict() if document.exists else None
    if not data or data.get("tenant_id") != tenant_id:
        return jsonify({"error": "Contacto não encontrado neste tenant."}), 404
    reference.set({"status": "archived", "opt_in": False, "updated_at": _now()}, merge=True)
    _audit("contact_archived", _identity(), tenant_id, {"contact_id": contact_id})
    return jsonify({"archived": True, "contact_id": contact_id})


@platform_bp.get("/client/templates")
@_require_roles("client", "operator")
def list_campaign_templates():
    tenant_id = _tenant_for_identity(_identity())
    rows = []
    for document in _db().collection("campaign_templates").where("tenant_id", "==", tenant_id).limit(100).stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        rows.append(item)
    rows.sort(key=lambda item: str(item.get("name") or "").lower())
    return jsonify({"templates": rows})


@platform_bp.post("/client/templates")
@_require_roles("client", "operator")
def create_campaign_template():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    body = str(payload.get("body") or payload.get("message") or "").strip()
    if not 2 <= len(name) <= 100 or not 1 <= len(body) <= 4000:
        return jsonify({"error": "O nome deve ter 2–100 caracteres e a mensagem 1–4000 caracteres."}), 400
    variables = sorted({str(item).strip().lower() for item in (payload.get("variables") or []) if str(item).strip()})[:30]
    tenant_id = _tenant_for_identity(_identity())
    reference = _db().collection("campaign_templates").document()
    reference.set({"tenant_id": tenant_id, "name": name, "body": body, "variables": variables, "status": "active", "created_at": _now(), "updated_at": _now()})
    _audit("campaign_template_created", _identity(), tenant_id, {"template_id": reference.id})
    return jsonify({"created": True, "template": {"id": reference.id, "name": name, "body": body, "variables": variables, "status": "active"}}), 201


@platform_bp.patch("/client/templates/<template_id>")
@_require_roles("client", "operator")
def update_campaign_template(template_id: str):
    tenant_id = _tenant_for_identity(_identity())
    reference = _db().collection("campaign_templates").document(template_id)
    document = reference.get()
    data = document.to_dict() if document.exists else None
    if not data or data.get("tenant_id") != tenant_id:
        return jsonify({"error": "Template não encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    changes = {}
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not 2 <= len(name) <= 100:
            return jsonify({"error": "Nome de template inválido."}), 400
        changes["name"] = name
    if "body" in payload:
        body = str(payload.get("body") or "").strip()
        if not 1 <= len(body) <= 4000:
            return jsonify({"error": "Mensagem de template inválida."}), 400
        changes["body"] = body
    if "status" in payload:
        status = str(payload.get("status") or "").lower()
        if status not in {"active", "archived"}:
            return jsonify({"error": "Estado de template inválido."}), 400
        changes["status"] = status
    if not changes:
        return jsonify({"error": "Nenhuma alteração válida foi enviada."}), 400
    changes["updated_at"] = _now()
    reference.set(changes, merge=True)
    _audit("campaign_template_updated", _identity(), tenant_id, {"template_id": template_id, "fields": sorted(changes)})
    return jsonify({"updated": True, "template_id": template_id, "fields": sorted(changes)})


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
    requested_channels = payload.get("channels") or ["whatsapp"]
    channels = sorted({str(channel).strip().lower() for channel in requested_channels if str(channel).strip()})
    supported_channels = {"whatsapp", "facebook", "instagram", "tiktok", "x", "linkedin", "telegram", "email"}
    if not channels or not set(channels).issubset(supported_channels):
        return jsonify({"error": "Escolhe pelo menos um canal suportado: WhatsApp, Facebook, Instagram, TikTok, X, LinkedIn, Telegram ou email."}), 400
    language = str(payload.get("language") or "pt-MZ").strip()[:20]
    tone = str(payload.get("tone") or "profissional").strip()[:60]
    offer = str(payload.get("offer") or "").strip()[:1000]
    scheduled_at = str(payload.get("scheduled_at") or "").strip()[:80] or None
    tenant_id = _tenant_for_identity(_identity())
    db = _db()
    template_id = str(payload.get("template_id") or "").strip()
    if template_id:
        template_document = db.collection("campaign_templates").document(template_id).get()
        template = template_document.to_dict() if template_document.exists else None
        if not template or template.get("tenant_id") != tenant_id or template.get("status", "active") != "active":
            return jsonify({"error": "Template não encontrado ou arquivado."}), 404
        message = str(template.get("body") or "").strip()
    if len(name) < 2 or not message or len(message) > 4000:
        return jsonify({"error": "Nome e mensagem são obrigatórios e a mensagem não pode exceder 4000 caracteres."}), 400
    segment_tags = sorted({str(item).strip().lower() for item in (payload.get("tags") or payload.get("segment_tags") or []) if str(item).strip()})[:20]
    contacts = list(db.collection("contacts").where("tenant_id", "==", tenant_id).where("opt_in", "==", True).limit(1000).stream())
    if segment_tags:
        contacts = [contact for contact in contacts if set(segment_tags).issubset(set((contact.to_dict() or {}).get("tags") or []))]
    if not contacts:
        return jsonify({"error": "Adicione primeiro contactos com consentimento para receber mensagens."}), 400
    campaign_ref = db.collection("campaigns").document()
    campaign_ref.set({
        "tenant_id": tenant_id,
        "name": name,
        "message": message,
        "template_id": template_id or None,
        "segment_tags": segment_tags,
        "instance_name": str(payload.get("instance_name") or "").strip() or None,
        "channels": channels,
        "language": language,
        "tone": tone,
        "offer": offer,
        "scheduled_at": scheduled_at,
        "orchestration_status": "queued",
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
    return jsonify({"created": True, "campaign": {"id": campaign_ref.id, "name": name, "status": "queued", "total": len(recipients), "channels": channels, "scheduled_at": scheduled_at}}), 201


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
    "lemonsqueezy": {"label": "Lemon Squeezy", "kind": "Checkout online e subscrições", "env": "LEMONSQUEEZY_API_KEY"},
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
    intent_ref = None
    tx_id = None
    try:
        # A intenção permite ao listener AutoPay associar uma transação nova
        # ao tenant mesmo quando o Android ainda não gravou tenant_id.
        from services.payment_service import extrair_codigo_mpesa, validar_e_ativar_pagamento_mpesa
        tx_id = extrair_codigo_mpesa(message_text)
        if client_phone:
            intent_ref = _db().collection("payment_intents").document()
            intent_ref.set({
                "tenant_id": tenant_id,
                "client_phone": re.sub(r"\D", "", client_phone),
                "transaction_id": tx_id,
                "status": "pending",
                "source": "platform_verify",
                "created_at": _now(),
            })
        response = validar_e_ativar_pagamento_mpesa(tenant_id, client_phone, message_text)
        if "PAGAMENTO CONFIRMADO" in str(response):
            paid_doc = _db().collection("clientes_bot").document(tenant_id).get()
            paid = paid_doc.to_dict() or {}
            _db().collection("tenants").document(tenant_id).set({
                "plan": paid.get("plano", paid.get("plan", "demonstracao")),
                "plano": paid.get("plano", paid.get("plan", "demonstracao")),
                "plan_name": paid.get("nome_plano", "Demonstração"),
                "nome_plano": paid.get("nome_plano", "Demonstração"),
                "status": paid.get("status_plano", "ativo"),
                "status_plano": paid.get("status_plano", "ativo"),
                "data_expiracao": paid.get("data_expiracao"),
                "mass_broadcast": bool(paid.get("disparo_liberado", False)),
                "disparo_liberado": bool(paid.get("disparo_liberado", False)),
                "limite_conversas": paid.get("limite_conversas"),
                "telefone_proprietario": client_phone or paid.get("telefone_proprietario"),
                "updated_at": _now(),
            }, merge=True)
            if intent_ref is not None:
                intent_ref.set({"status": "confirmed", "transaction_id": tx_id, "confirmed_at": _now()}, merge=True)
            _audit("mpesa_payment_confirmed", _identity(), tenant_id, {"plan": paid.get("plano"), "transaction_id": tx_id, "mass_broadcast": bool(paid.get("disparo_liberado", False))})
        elif intent_ref is not None:
            intent_ref.set({"status": "pending_validation", "transaction_id": tx_id, "updated_at": _now()}, merge=True)
    except Exception:
        return jsonify({"error": "O serviço de pagamentos está temporariamente indisponível."}), 503
    qr_payload = {"state": "not_requested", "qrcode": None, "instance_name": None}
    if "PAGAMENTO CONFIRMADO" in str(response):
        try:
            owner_phone = re.sub(r"\D", "", str(client_phone or ""))
            if owner_phone:
                from services.evolution_service import criar_e_configurar_instancia_automatica, obter_qrcode_instancia
                if criar_e_configurar_instancia_automatica(owner_phone):
                    qr_data = obter_qrcode_instancia(owner_phone)
                    base64_qr = qr_data.get("base64")
                    qr_payload = {
                        "state": qr_data.get("state", "connecting"),
                        "instance_name": qr_data.get("instance_name"),
                        "qrcode": base64_qr and (base64_qr if str(base64_qr).startswith("data:") else f"data:image/png;base64,{base64_qr}"),
                    }
        except Exception:
            qr_payload["state"] = "pending"
    return jsonify({"processed": True, "response": response, **qr_payload})


@platform_bp.get("/client/payments/history")
@_require_roles("client", "operator")
def payment_history():
    tenant_id = _tenant_for_identity(_identity())
    rows = []
    for document in _db().collection("payment_intents").where("tenant_id", "==", tenant_id).limit(100).stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        item.pop("message_text", None)
        rows.append(item)
    rows.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return jsonify({"payments": rows})



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


def _lemon_plan_from_variant(variant_id: str, requested_plan: str = "") -> str | None:
    from services.payment_service import TABELA_PLANOS
    variant_id = str(variant_id or "").strip()
    requested_plan = str(requested_plan or "").strip().lower()
    for data in TABELA_PLANOS.values():
        plan_id = str(data["id"])
        configured_variant = os.getenv(f"LEMONSQUEEZY_VARIANT_{plan_id.upper()}", "").strip()
        if configured_variant and configured_variant == variant_id:
            return plan_id
    if requested_plan in {str(data["id"]) for data in TABELA_PLANOS.values()} and not variant_id:
        return requested_plan
    return None


def _apply_lemon_plan(tenant_id: str, plan_id: str, attributes: dict[str, Any], intent_ref, event: dict[str, Any]):
    from services.payment_service import TABELA_PLANOS
    plan = next((item for item in TABELA_PLANOS.values() if item["id"] == plan_id), None)
    if not plan:
        raise ValueError("Plano Lemon Squeezy não encontrado.")
    now = _now()
    expires_at = __import__("services.lemonsqueezy_service", fromlist=["expiry_for_event"]).expiry_for_event(attributes, now)
    lemon_fields = {
        "provider": "lemonsqueezy",
        "payment_provider": "lemonsqueezy",
        "plan_id": plan_id,
        "plan": plan_id,
        "plan_name": plan["nome"],
        "nome_plano": plan["nome"],
        "status": "active",
        "status_plano": "ativo",
        "mass_broadcast": bool(plan["disparo_liberado"]),
        "disparo_liberado": bool(plan["disparo_liberado"]),
        "limite_conversas": plan["limite_conversas"],
        "data_ativacao": now,
        "data_expiracao": expires_at,
        "metodo_pagamento": "Lemon Squeezy",
        "lemon_subscription_id": event["object_id"] if event["object_type"] == "subscriptions" else attributes.get("subscription_id"),
        "lemon_order_id": attributes.get("order_id"),
        "lemon_customer_id": attributes.get("customer_id"),
        "lemon_variant_id": event["variant_id"],
        "lemon_status": attributes.get("status") or "active",
        "updated_at": now,
    }
    _db().collection("tenants").document(tenant_id).set(lemon_fields, merge=True)
    _db().collection("clientes_bot").document(tenant_id).set(lemon_fields, merge=True)
    intent_ref.set({**lemon_fields, "status": "confirmed", "provider_status": "active", "confirmed_at": now, "activated_at": now}, merge=True)


@platform_bp.get("/client/payments/lemonsqueezy/status")
@_require_roles("client", "operator")
def lemonsqueezy_status():
    from services.lemonsqueezy_service import configured
    from services.payment_service import TABELA_PLANOS
    plans = {data["id"]: bool(os.getenv(f"LEMONSQUEEZY_VARIANT_{str(data['id']).upper()}", "").strip()) for data in TABELA_PLANOS.values()}
    return jsonify({"configured": configured(), "currency": os.getenv("LEMONSQUEEZY_CURRENCY", "USD"), "plans": plans})


@platform_bp.post("/client/payments/lemonsqueezy/checkout")
@_require_roles("client", "operator")
def create_lemonsqueezy_checkout():
    from services.lemonsqueezy_service import create_checkout
    payload = request.get_json(silent=True) or {}
    plan_id = str(payload.get("plan_id") or "").strip().lower()
    from services.payment_service import TABELA_PLANOS
    plan = next((item for item in TABELA_PLANOS.values() if item["id"] == plan_id), None)
    if not plan:
        return jsonify({"error": "Plano não encontrado."}), 400
    tenant_id = _tenant_for_identity(_identity())
    if not tenant_id:
        return jsonify({"error": "Tenant não encontrado na sessão."}), 400
    intent_ref = _db().collection("payment_intents").document()
    intent_ref.set({
        "tenant_id": tenant_id,
        "provider": "lemonsqueezy",
        "payment_provider": "lemonsqueezy",
        "plan_id": plan_id,
        "plan_name": plan["nome"],
        "status": "pending_checkout",
        "created_at": _now(),
    })
    identity = _identity() or {}
    tenant_doc = _db().collection("tenants").document(tenant_id).get()
    tenant = tenant_doc.to_dict() or {}
    try:
        checkout = create_checkout(
            plan_id=plan_id,
            tenant_id=tenant_id,
            payment_intent_id=intent_ref.id,
            email=str(identity.get("email") or tenant.get("email") or "").strip() or None,
            name=str(identity.get("name") or tenant.get("name") or "").strip() or None,
        )
    except (RuntimeError, ValueError, requests.RequestException) as exc:
        intent_ref.set({"status": "checkout_failed", "error": str(exc), "updated_at": _now()}, merge=True)
        return jsonify({"error": "O checkout Lemon Squeezy ainda não está disponível. Usa M-Pesa ou tenta novamente mais tarde."}), 503
    intent_ref.set({"status": "pending", "checkout_url": checkout["url"], "variant_id": checkout["variant_id"], "updated_at": _now()}, merge=True)
    _audit("lemonsqueezy_checkout_created", _identity(), tenant_id, {"payment_intent_id": intent_ref.id, "plan_id": plan_id})
    return jsonify({"created": True, "payment_intent_id": intent_ref.id, "checkout_url": checkout["url"], "plan_id": plan_id}), 201


@platform_bp.post("/webhooks/lemonsqueezy")
def lemonsqueezy_webhook():
    from services.lemonsqueezy_service import event_key, extract_event, verify_signature
    raw_body = request.get_data(cache=True)
    if not verify_signature(raw_body, request.headers.get("X-Signature")):
        return jsonify({"error": "Assinatura Lemon Squeezy inválida."}), 401
    payload = request.get_json(silent=True) or {}
    event = extract_event(payload)
    key = event_key(payload)
    event_ref = _db().collection("lemonsqueezy_webhook_events").document(key)
    if event_ref.get().exists:
        return jsonify({"received": True, "duplicate": True})
    event_ref.set({"event_key": key, "event_name": event["event_name"], "object_id": event["object_id"], "received_at": _now(), "payload": payload})
    custom = event["custom_data"]
    tenant_id = str(custom.get("tenant_id") or "").strip()
    intent_id = str(custom.get("payment_intent_id") or "").strip()
    if not tenant_id or not intent_id:
        event_ref.set({"status": "unlinked"}, merge=True)
        return jsonify({"received": True, "linked": False})
    intent_ref = _db().collection("payment_intents").document(intent_id)
    intent_doc = intent_ref.get()
    intent = intent_doc.to_dict() or {}
    if not intent_doc.exists or str(intent.get("tenant_id") or "") != tenant_id:
        event_ref.set({"status": "tenant_mismatch"}, merge=True)
        return jsonify({"received": True, "linked": False})
    plan_id = _lemon_plan_from_variant(event["variant_id"], str(custom.get("plan_id") or intent.get("plan_id") or ""))
    if not plan_id:
        intent_ref.set({"status": "manual_review", "provider_event": event["event_name"], "updated_at": _now()}, merge=True)
        event_ref.set({"status": "manual_review", "tenant_id": tenant_id, "payment_intent_id": intent_id}, merge=True)
        return jsonify({"received": True, "linked": True, "status": "manual_review"})
    event_name = event["event_name"]
    attributes = event["attributes"]
    if event_name in {"subscription_created", "subscription_payment_success", "subscription_payment_recovered"} or (event_name == "subscription_updated" and str(attributes.get("status") or "").lower() == "active"):
        _apply_lemon_plan(tenant_id, plan_id, attributes, intent_ref, event)
        result_status = "confirmed"
    elif event_name in {"subscription_payment_failed"}:
        intent_ref.set({"status": "payment_failed", "provider_event": event_name, "updated_at": _now()}, merge=True)
        result_status = "payment_failed"
    elif event_name in {"subscription_cancelled", "subscription_expired", "order_refunded"}:
        intent_ref.set({"status": "cancelled" if "cancel" in event_name else "expired", "provider_event": event_name, "updated_at": _now()}, merge=True)
        _db().collection("tenants").document(tenant_id).set({"status_plano": "cancelado" if "cancel" in event_name else "expirado", "status": "cancelado" if "cancel" in event_name else "expirado", "updated_at": _now()}, merge=True)
        result_status = "cancelled" if "cancel" in event_name else "expired"
    else:
        intent_ref.set({"status": "received", "provider_event": event_name, "updated_at": _now()}, merge=True)
        result_status = "received"
    event_ref.set({"status": result_status, "tenant_id": tenant_id, "payment_intent_id": intent_id, "processed_at": _now()}, merge=True)
    _audit(f"lemonsqueezy_{result_status}", None, tenant_id, {"event_name": event_name, "payment_intent_id": intent_id, "object_id": event["object_id"]})
    return jsonify({"received": True, "linked": True, "status": result_status})


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


@platform_bp.get("/client/plans")
@_require_roles("client", "operator")
def client_plans_catalog():
    from services.payment_service import TABELA_PLANOS
    benefits = {
        "basico": [
            "FAQ, horário, localização e catálogo em texto",
            "Até 1.500 conversas por mês",
            "1 número de WhatsApp",
            "Suporte básico até 24 horas",
            "Sem PDFs, Excel, fotos, áudios ou disparos em massa",
        ],
        "medio": [
            "Tudo do Plano Básico",
            "Conversas ilimitadas",
            "Processamento de fotos e leitura básica de Excel",
            "Menu interativo e relatórios mensais",
            "Suporte prioritário até 12 horas",
        ],
        "premium": [
            "Tudo do Plano Médio",
            "Leitura de PDFs e documentos extensos",
            "Interpretação de áudios e geração de artes (#imagem)",
            "Disparos em massa e campanhas de marketing",
            "Suporte dedicado e configuração inicial assistida",
        ],
    }
    plans = []
    for amount, data in sorted(TABELA_PLANOS.items()):
        plans.append({
            "id": data["id"],
            "name": data["nome"],
            "price_mt": int(amount),
            "validity_days": data["dias_validade"],
            "conversation_limit": data["limite_conversas"],
            "mass_broadcast": bool(data["disparo_liberado"]),
            "benefits": benefits.get(data["id"], []),
        })
    return jsonify({"plans": plans, "trial_days": 2, "mpesa_number": "855000929", "mpesa_name": "Abel Francisco"})


@platform_bp.post("/client/evolution/qr")
@_require_roles("client", "operator")
def request_evolution_qr():
    tenant_id = _tenant_for_identity(_identity())
    payload = request.get_json(silent=True) or {}
    tenant_ref = _db().collection("tenants").document(tenant_id)
    tenant = tenant_ref.get().to_dict() or {}
    status = str(tenant.get("status_plano", tenant.get("status", "demonstracao"))).lower()
    if status in {"expirado", "suspenso", "cancelado"} or _plan_expired(tenant):
        return jsonify({"error": "A demonstração/plano expirou. Ativa ou renova o plano antes de ligar o WhatsApp ou gerar outro QR Code."}), 402
    phone = re.sub(r"\D", "", str(payload.get("phone") or tenant.get("telefone_proprietario") or tenant.get("phone") or ""))
    if len(phone) < 8:
        return jsonify({"error": "Indica o número de WhatsApp que será automatizado."}), 400
    try:
        from services.evolution_service import criar_e_configurar_instancia_automatica, obter_qrcode_instancia
        if not criar_e_configurar_instancia_automatica(phone):
            return jsonify({"error": "Não foi possível preparar a instância Evolution."}), 502
        data = obter_qrcode_instancia(phone)
        instance_name = data["instance_name"]
        state = data["state"]
        base64_qr = data.get("base64")
        tenant_ref.set({"instance_name": instance_name, "telefone_proprietario": phone, "evolution_state": state, "updated_at": _now()}, merge=True)
        profile_sync = {key: tenant.get(key) for key in ("empresa_nome", "nicho", "email_corporativo", "redes_sociais") if tenant.get(key) is not None}
        if profile_sync:
            _db().collection("clientes_bot").document(instance_name).set(profile_sync, merge=True)
        return jsonify({"state": state, "instance_name": instance_name, "qrcode": base64_qr and (base64_qr if str(base64_qr).startswith("data:") else f"data:image/png;base64,{base64_qr}")})
    except requests.RequestException:
        return jsonify({"error": "A Evolution API não respondeu ao pedido de QR Code."}), 502
    except Exception:
        return jsonify({"error": "Não foi possível gerar o QR Code neste momento."}), 502


_PUBLIC_CHAT_RATE: dict[str, list[float]] = {}


def _public_plan_answer() -> str:
    return (
        "Aqui estão os planos NEGOBOT-MOZ:\n\n"
        "• Básico — 500 MT/mês: até 1.500 conversas, FAQ, horário e catálogo em texto, 1 número de WhatsApp e suporte básico até 24 horas.\n"
        "• Médio — 1.000 MT/mês: conversas ilimitadas, fotos, leitura básica de Excel, menu interativo, relatórios e suporte prioritário até 12 horas.\n"
        "• Premium — 1.500 MT/mês: IA avançada, áudio, PDFs, documentos, artes publicitárias, campanhas e disparos em massa e suporte dedicado.\n\n"
        "Todos os planos têm validade de 30 dias e começam com demonstração de 2 dias. O pagamento é feito manualmente por M-Pesa para 855000929, em nome de Abel Francisco. Depois da validação pelo AutoPay, a Evolution API prepara o QR Code para ligares o WhatsApp."
    )


def _public_is_plan_question(message: str) -> bool:
    normalized = message.casefold()
    return any(term in normalized for term in ("plano", "preço", "preco", "quanto", "custa", "mensal", "mt", "benefício", "beneficio"))


@platform_bp.post("/public/assistant/chat")
def public_assistant_chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "").strip()
    source = str(payload.get("source") or "platform").lower()
    if source not in {"platform", "facebook", "instagram", "whatsapp", "other"}:
        source = "platform"
    if not message or len(message) > 1200:
        return jsonify({"error": "Escreve uma mensagem entre 1 e 1.200 caracteres."}), 400
    now = time.time()
    visitor = request.headers.get("X-Forwarded-For", request.remote_addr or "public").split(",")[0].strip()
    recent = [stamp for stamp in _PUBLIC_CHAT_RATE.get(visitor, []) if now - stamp < 600]
    if len(recent) >= 12:
        return jsonify({"error": "Atingiste o limite temporário de mensagens. Tenta novamente mais tarde."}), 429
    recent.append(now)
    _PUBLIC_CHAT_RATE[visitor] = recent
    try:
        _db().collection("public_leads").add({"source": source, "message": message[:1200], "created_at": _now()})
    except Exception:
        pass
    prompt = """És o assistente comercial público do NEGOBOT-MOZ, em Português de Moçambique. Explica com clareza os planos reais: Básico 500 MT/mês com até 1.500 conversas e FAQ/catalogo em texto; Médio 1.000 MT/mês com conversas ilimitadas, fotos, Excel básico, menus e relatórios; Premium 1.500 MT/mês com IA avançada, PDFs, documentos, áudio, artes publicitárias e disparos em massa. Todos têm validade de 30 dias e existe demonstração de 2 dias. O pagamento é manual via M-Pesa para 855000929 em nome de Abel Francisco. Nunca digas que um pagamento foi confirmado sem validação AutoPay. Explica que o cliente deve enviar o SMS ou ID da transferência na plataforma ou ao bot WhatsApp; depois da confirmação, a Evolution API prepara o QR Code. Sê comercial, honesto e breve. Não inventes preços, limites ou integrações."""
    if _public_is_plan_question(message):
        answer = _public_plan_answer()
    else:
        try:
            from services.groq_service import chamar_groq_rest
            answer = chamar_groq_rest([{"role": "user", "content": message}], system_prompt=prompt)
        except Exception:
            answer = "Posso ajudar com os planos, pagamentos M-Pesa, ligação do WhatsApp e demonstração de 2 dias."
        if not answer or "processar muitas mensagens" in answer.casefold():
            answer = "Posso ajudar com os planos, pagamentos M-Pesa, ligação do WhatsApp e demonstração de 2 dias. Escreve 'planos' para veres a tabela completa."
    return jsonify({"answer": answer, "source": source, "next": {"whatsapp": "/falar-whatsapp", "platform": "/plataforma"}})


# ─────────────────────────────────────────────────────────────────────────────
# Métricas, relatórios e suporte SaaS
# ─────────────────────────────────────────────────────────────────────────────

_TICKET_STATUSES = {"open", "in_progress", "waiting_client", "resolved", "closed"}
_TICKET_PRIORITIES = {"low", "normal", "high", "urgent"}


def _tenant_collection_rows(collection: str, tenant_id: str, limit: int = 2000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for document in _db().collection(collection).where("tenant_id", "==", tenant_id).limit(limit).stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        rows.append(item)
    return rows


def _campaign_metrics_for_tenant(tenant_id: str) -> dict[str, Any]:
    campaigns = _tenant_collection_rows("campaigns", tenant_id, 500)
    recipients = _tenant_collection_rows("campaign_recipients", tenant_id, 5000)
    conversations = list(_db().collection("clientes_bot").document(tenant_id).collection("conversas").limit(500).stream())
    contacts = _tenant_collection_rows("contacts", tenant_id, 5000)
    statuses: dict[str, int] = {}
    for campaign in campaigns:
        status = str(campaign.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    recipient_statuses: dict[str, int] = {}
    for recipient in recipients:
        status = str(recipient.get("status") or "unknown")
        recipient_statuses[status] = recipient_statuses.get(status, 0) + 1
    sent = recipient_statuses.get("sent", 0) + recipient_statuses.get("delivered", 0)
    failed = recipient_statuses.get("failed", 0)
    attempted = sent + failed
    recent = sorted(campaigns, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:10]
    return {
        "contacts": {"total": len(contacts), "opt_in": sum(1 for item in contacts if item.get("opt_in", True)), "opt_out": sum(1 for item in contacts if not item.get("opt_in", True))},
        "conversations": len(conversations),
        "campaigns": {"total": len(campaigns), "by_status": statuses, "recent": recent},
        "deliveries": {"total": len(recipients), "by_status": recipient_statuses, "sent": sent, "failed": failed, "delivery_rate": round((sent / attempted) * 100, 2) if attempted else 0},
    }


@platform_bp.get("/client/metrics")
@_require_roles("client", "operator")
def client_metrics():
    tenant_id = _tenant_for_identity(_identity())
    return jsonify({"tenant_id": tenant_id, "metrics": _campaign_metrics_for_tenant(tenant_id)})


@platform_bp.get("/client/reports/campaigns")
@_require_roles("client", "operator")
def client_campaign_report():
    tenant_id = _tenant_for_identity(_identity())
    metrics = _campaign_metrics_for_tenant(tenant_id)
    return jsonify({"tenant_id": tenant_id, "generated_at": _now(), "campaigns": metrics["campaigns"], "deliveries": metrics["deliveries"]})


@platform_bp.get("/client/support/tickets")
@_require_roles("client", "operator")
def client_support_tickets():
    tenant_id = _tenant_for_identity(_identity())
    rows = _tenant_collection_rows("support_tickets", tenant_id, 200)
    rows.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return jsonify({"tickets": rows})


@platform_bp.post("/client/support/tickets")
@_require_roles("client", "operator")
def create_support_ticket():
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").strip()
    message = str(payload.get("message") or "").strip()
    category = str(payload.get("category") or "general").strip().lower()[:40]
    priority = str(payload.get("priority") or "normal").strip().lower()
    if not 4 <= len(subject) <= 160 or not 10 <= len(message) <= 5000:
        return jsonify({"error": "Indica um assunto e uma descrição válidos."}), 400
    if priority not in _TICKET_PRIORITIES:
        priority = "normal"
    tenant_id = _tenant_for_identity(_identity())
    reference = _db().collection("support_tickets").document()
    now = _now()
    ticket = {"tenant_id": tenant_id, "subject": subject, "message": message, "category": category or "general", "priority": priority, "status": "open", "created_by": (_identity() or {}).get("id"), "created_at": now, "updated_at": now}
    reference.set(ticket)
    _audit("support_ticket_created", _identity(), tenant_id, {"ticket_id": reference.id, "priority": priority, "category": category})
    return jsonify({"created": True, "ticket": {"id": reference.id, **ticket}}), 201


@platform_bp.patch("/client/support/tickets/<ticket_id>")
@_require_roles("client", "operator")
def update_client_support_ticket(ticket_id: str):
    tenant_id = _tenant_for_identity(_identity())
    reference = _db().collection("support_tickets").document(ticket_id)
    document = reference.get()
    data = document.to_dict() if document.exists else None
    if not data or data.get("tenant_id") != tenant_id:
        return jsonify({"error": "Ticket não encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    changes: dict[str, Any] = {}
    if "message" in payload:
        message = str(payload.get("message") or "").strip()
        if not 10 <= len(message) <= 5000:
            return jsonify({"error": "A mensagem deve ter entre 10 e 5000 caracteres."}), 400
        changes["last_client_message"] = message
        changes["last_client_message_at"] = _now()
        if data.get("status") == "waiting_client":
            changes["status"] = "open"
    if "status" in payload and str(payload.get("status")) in {"closed", "open"}:
        changes["status"] = str(payload["status"])
    if not changes:
        return jsonify({"error": "Nenhuma alteração válida foi enviada."}), 400
    changes["updated_at"] = _now()
    reference.set(changes, merge=True)
    _audit("support_ticket_updated", _identity(), tenant_id, {"ticket_id": ticket_id, "fields": sorted(changes)})
    return jsonify({"updated": True, "ticket_id": ticket_id, "fields": sorted(changes)})


@platform_bp.get("/admin/metrics")
@_require_roles("owner", "admin")
def admin_metrics():
    db = _db()
    tenants = list(db.collection("tenants").limit(5000).stream())
    users = list(db.collection("platform_users").limit(5000).stream())
    campaigns = list(db.collection("campaigns").limit(5000).stream())
    payments = list(db.collection("payment_intents").limit(5000).stream())
    tickets = list(db.collection("support_tickets").limit(5000).stream())
    return jsonify({
        "generated_at": _now(),
        "tenants": {"total": len(tenants), "active": sum(1 for item in tenants if (item.to_dict() or {}).get("status", "active") in {"active", "ativo"})},
        "users": {"total": len(users), "active": sum(1 for item in users if (item.to_dict() or {}).get("status", "active") == "active")},
        "campaigns": {"total": len(campaigns), "by_status": _count_statuses(campaigns)},
        "payments": {"total": len(payments), "confirmed": sum(1 for item in payments if (item.to_dict() or {}).get("status") in {"confirmed", "active"})},
        "support": {"total": len(tickets), "open": sum(1 for item in tickets if (item.to_dict() or {}).get("status", "open") in {"open", "in_progress", "waiting_client"})},
    })


def _count_statuses(documents: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for document in documents:
        status = str((document.to_dict() or {}).get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


@platform_bp.get("/admin/support/tickets")
@_require_roles("owner", "admin")
def admin_support_tickets():
    rows = []
    for document in _db().collection("support_tickets").limit(500).stream():
        item = document.to_dict() or {}
        item["id"] = document.id
        rows.append(item)
    rows.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return jsonify({"tickets": rows})


@platform_bp.patch("/admin/support/tickets/<ticket_id>")
@_require_roles("owner", "admin")
def admin_update_support_ticket(ticket_id: str):
    reference = _db().collection("support_tickets").document(ticket_id)
    document = reference.get()
    if not document.exists:
        return jsonify({"error": "Ticket não encontrado."}), 404
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status") or "").strip().lower()
    if status not in _TICKET_STATUSES:
        return jsonify({"error": "Estado de ticket inválido."}), 400
    changes = {"status": status, "updated_at": _now(), "updated_by": (_identity() or {}).get("id")}
    if "reply" in payload:
        reply = str(payload.get("reply") or "").strip()
        if reply:
            changes["last_admin_reply"] = reply[:5000]
            changes["last_admin_reply_at"] = _now()
    reference.set(changes, merge=True)
    tenant_id = str((document.to_dict() or {}).get("tenant_id") or "") or None
    _audit("support_ticket_admin_updated", _identity(), tenant_id, {"ticket_id": ticket_id, "status": status})
    return jsonify({"updated": True, "ticket_id": ticket_id, "status": status})


@platform_bp.post("/client/videos/jobs")
@_require_roles("client", "operator")
def create_video_job():
    base_url = str(os.getenv("VIDEO_SERVICE_URL", "")).rstrip("/")
    service_token = os.getenv("VIDEO_SERVICE_TOKEN", "").strip()
    if not base_url or not service_token:
        return jsonify({"error": "O motor de vídeos ainda não está configurado."}), 503
    payload = request.get_json(silent=True) or {}
    scenes = payload.get("scenes") or []
    title = str(payload.get("title") or "").strip()
    if not 2 <= len(title) <= 160 or not isinstance(scenes, list) or not 1 <= len(scenes) <= 20:
        return jsonify({"error": "Indica um título e pelo menos uma cena válida."}), 400
    tenant_id = _tenant_for_identity(_identity())
    outgoing = {"tenant_id": tenant_id, "title": title, "scenes": scenes, "language": str(payload.get("language") or "pt-MZ"), "voice": payload.get("voice"), "subtitles": bool(payload.get("subtitles", True))}
    try:
        response = requests.post(f"{base_url}/api/video/jobs", json=outgoing, headers={"X-Video-Service-Token": service_token}, timeout=20)
    except requests.RequestException:
        return jsonify({"error": "O motor de vídeos está temporariamente indisponível."}), 503
    if not response.ok:
        return jsonify({"error": "O motor de vídeos rejeitou o job."}), 502
    data = response.json()
    job = data.get("job") or {}
    job_id = str(job.get("id") or "").strip()
    if not job_id:
        return jsonify({"error": "O motor de vídeos devolveu uma resposta inválida."}), 502
    _db().collection("video_jobs").document(job_id).set({"tenant_id": tenant_id, "job_id": job_id, "title": title, "status": "queued", "created_at": _now()}, merge=True)
    _audit("video_job_created", _identity(), tenant_id, {"job_id": job_id, "scenes": len(scenes)})
    return jsonify({"accepted": True, "job": job}), 202


@platform_bp.get("/client/videos/jobs/<job_id>")
@_require_roles("client", "operator")
def get_video_job(job_id: str):
    base_url = str(os.getenv("VIDEO_SERVICE_URL", "")).rstrip("/")
    service_token = os.getenv("VIDEO_SERVICE_TOKEN", "").strip()
    tenant_id = _tenant_for_identity(_identity())
    document = _db().collection("video_jobs").document(job_id).get()
    if not document.exists or (document.to_dict() or {}).get("tenant_id") != tenant_id:
        return jsonify({"error": "Job de vídeo não encontrado."}), 404
    if not base_url or not service_token:
        return jsonify({"error": "O motor de vídeos ainda não está configurado."}), 503
    try:
        response = requests.get(f"{base_url}/api/video/jobs/{quote(job_id)}", headers={"X-Video-Service-Token": service_token}, timeout=15)
    except requests.RequestException:
        return jsonify({"error": "O motor de vídeos está temporariamente indisponível."}), 503
    if not response.ok:
        return jsonify({"error": "Não foi possível obter o estado do vídeo."}), 502
    data = response.json()
    job = data.get("job") or {}
    _db().collection("video_jobs").document(job_id).set({"status": job.get("status"), "progress": job.get("progress", 0), "updated_at": _now(), "output_path": job.get("output_path")}, merge=True)
    return jsonify({"job": job})
