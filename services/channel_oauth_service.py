from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from services.secret_store import SecretStoreError, encrypt_secret

OAUTH_STATE_TTL_SECONDS = 600
REQUEST_TIMEOUT_SECONDS = 15

OAUTH_DEFINITIONS: dict[str, dict[str, Any]] = {
    "instagram": {
        "provider": "Meta Instagram Login",
        "client_id_env": "META_INSTAGRAM_CLIENT_ID",
        "client_secret_env": "META_INSTAGRAM_CLIENT_SECRET",
        "redirect_uri_env": "META_INSTAGRAM_REDIRECT_URI",
        "scopes_env": "META_INSTAGRAM_SCOPES",
        "default_scopes": "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_messages,instagram_business_manage_comments",
        "authorize_url": "https://www.instagram.com/oauth/authorize",
        "token_url": "https://api.instagram.com/oauth/access_token",
        "profile_url": "https://graph.instagram.com/me?fields=user_id,username,name",
        "profile_id_keys": ("user_id", "id"),
        "profile_name_keys": ("username", "name"),
    },
    "facebook": {
        "provider": "Meta Facebook Login for Business",
        "client_id_env": "META_CLIENT_ID",
        "client_secret_env": "META_CLIENT_SECRET",
        "redirect_uri_env": "META_REDIRECT_URI",
        "scopes_env": "META_SCOPES",
        "default_scopes": "public_profile,pages_show_list,pages_read_engagement,pages_manage_posts",
        "authorize_url": "https://www.facebook.com/v23.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v23.0/oauth/access_token",
        "profile_url": "https://graph.facebook.com/me?fields=id,name",
        "profile_id_keys": ("id",),
        "profile_name_keys": ("name",),
    },
    "tiktok": {
        "provider": "TikTok for Developers",
        "client_id_env": "TIKTOK_CLIENT_KEY",
        "client_secret_env": "TIKTOK_CLIENT_SECRET",
        "redirect_uri_env": "TIKTOK_REDIRECT_URI",
        "scopes_env": "TIKTOK_SCOPES",
        "default_scopes": "user.info.basic,video.list",
        "authorize_url": "https://www.tiktok.com/v2/auth/authorize/",
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "profile_url": "https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name,avatar_url",
        "profile_id_keys": ("open_id", "id"),
        "profile_name_keys": ("display_name", "username"),
    },
    "x": {
        "provider": "X API v2",
        "client_id_env": "X_CLIENT_ID",
        "client_secret_env": "X_CLIENT_SECRET",
        "redirect_uri_env": "X_REDIRECT_URI",
        "scopes_env": "X_SCOPES",
        "default_scopes": "tweet.read,users.read,offline.access",
        "authorize_url": "https://x.com/i/oauth2/authorize",
        "token_url": "https://api.x.com/2/oauth2/token",
        "profile_url": "https://api.x.com/2/users/me",
        "profile_id_keys": ("id",),
        "profile_name_keys": ("name", "username"),
        "pkce": True,
    },
    "linkedin": {
        "provider": "LinkedIn API",
        "client_id_env": "LINKEDIN_CLIENT_ID",
        "client_secret_env": "LINKEDIN_CLIENT_SECRET",
        "redirect_uri_env": "LINKEDIN_REDIRECT_URI",
        "scopes_env": "LINKEDIN_SCOPES",
        "default_scopes": "openid,profile,email",
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "profile_url": "https://api.linkedin.com/v2/userinfo",
        "profile_id_keys": ("sub", "id"),
        "profile_name_keys": ("name", "localizedFirstName"),
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _state_id(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def _definition(channel: str) -> dict[str, Any]:
    try:
        return OAUTH_DEFINITIONS[str(channel).strip().lower()]
    except KeyError as exc:
        raise ValueError("Canal OAuth não suportado") from exc


def _redirect_uri(channel: str, definition: dict[str, Any]) -> str:
    configured = os.getenv(definition["redirect_uri_env"], "").strip()
    if configured:
        return configured
    base = os.getenv("PUBLIC_API_BASE_URL", "https://negobot-api.duckdns.org").rstrip("/")
    return f"{base}/api/platform/client/channels/{channel}/callback"


def provider_config(channel: str) -> dict[str, Any]:
    definition = _definition(channel)
    client_id = os.getenv(definition["client_id_env"], "").strip()
    client_secret = os.getenv(definition["client_secret_env"], "").strip()
    redirect_uri = _redirect_uri(channel, definition)
    scopes = os.getenv(definition["scopes_env"], definition["default_scopes"]).strip()
    return {
        "configured": bool(client_id and client_secret and redirect_uri),
        "provider": definition["provider"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "scopes": scopes,
    }


def _store_state(db: Any, state: str, data: dict[str, Any]) -> None:
    db.collection("oauth_states").document(_state_id(state)).set(data)


def _load_state(db: Any, state: str) -> tuple[Any, dict[str, Any]]:
    reference = db.collection("oauth_states").document(_state_id(state))
    snapshot = reference.get()
    data = snapshot.to_dict() if snapshot.exists else None
    if not isinstance(data, dict):
        raise ValueError("Estado OAuth inválido ou expirado")
    if data.get("status") != "pending":
        raise ValueError("Estado OAuth já utilizado")
    expires_at = str(data.get("expires_at") or "")
    try:
        if datetime.fromisoformat(expires_at).astimezone(timezone.utc) < utc_now():
            raise ValueError("Estado OAuth expirado")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Estado OAuth inválido") from exc
    return reference, data


def start_oauth(db: Any, channel: str, tenant_id: str, platform_user_id: str) -> dict[str, Any]:
    channel = str(channel).strip().lower()
    definition = _definition(channel)
    config = provider_config(channel)
    if not config["configured"]:
        raise RuntimeError(f"As credenciais de {definition['provider']} ainda não estão configuradas no servidor.")
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(48) if definition.get("pkce") else ""
    params: dict[str, str] = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": config["scopes"],
        "state": state,
    }
    if channel == "tiktok":
        params["client_key"] = params.pop("client_id")
    if definition.get("pkce"):
        # X accepts S256; the verifier is retained only in the short-lived state record.
        import base64
        import hashlib as _hashlib
        challenge = base64.urlsafe_b64encode(_hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    _store_state(db, state, {
        "status": "pending",
        "channel": channel,
        "tenant_id": str(tenant_id),
        "platform_user_id": str(platform_user_id),
        "code_verifier": code_verifier,
        "redirect_uri": config["redirect_uri"],
        "created_at": _iso(utc_now()),
        "expires_at": _iso(utc_now() + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)),
    })
    return {
        "channel": channel,
        "provider": definition["provider"],
        "status": "pending_authorization",
        "authorize_url": f"{definition['authorize_url']}?{urlencode(params)}",
        "expires_in": OAUTH_STATE_TTL_SECONDS,
    }


def _token_request(channel: str, definition: dict[str, Any], config: dict[str, Any], code: str, code_verifier: str) -> dict[str, Any]:
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": config["redirect_uri"]}
    auth = None
    if channel == "tiktok":
        data.update({"client_key": config["client_id"], "client_secret": config["client_secret"]})
    elif channel == "x":
        data.update({"client_id": config["client_id"], "code_verifier": code_verifier})
        auth = (config["client_id"], config["client_secret"])
    else:
        data.update({"client_id": config["client_id"], "client_secret": config["client_secret"]})
    response = requests.post(definition["token_url"], data=data, auth=auth, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise RuntimeError("O fornecedor não devolveu um access token válido.")
    return payload


def _profile_request(channel: str, definition: dict[str, Any], access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(definition["profile_url"], headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if not isinstance(payload, dict):
        raise RuntimeError("O fornecedor devolveu um perfil inválido.")
    return payload


def _first_value(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def complete_oauth(db: Any, channel: str, code: str, state: str) -> dict[str, Any]:
    channel = str(channel).strip().lower()
    definition = _definition(channel)
    if not code or not state:
        raise ValueError("Callback OAuth incompleto")
    state_reference, state_data = _load_state(db, state)
    if state_data.get("channel") != channel:
        raise ValueError("O callback OAuth não corresponde ao canal solicitado")
    config = provider_config(channel)
    if not config["configured"]:
        raise RuntimeError("As credenciais do fornecedor não estão configuradas no servidor.")
    try:
        token_data = _token_request(channel, definition, config, code, str(state_data.get("code_verifier") or ""))
        profile = _profile_request(channel, definition, str(token_data["access_token"]))
        external_id = _first_value(profile, definition["profile_id_keys"])
        if not external_id:
            raise RuntimeError("O fornecedor não devolveu a identidade da conta autorizada.")
        external_name = _first_value(profile, definition["profile_name_keys"]) or external_id
        token_fields = {
            "status": "connected",
            "provider": definition["provider"],
            "external_account_id": external_id,
            "external_account_name": external_name,
            "scope": token_data.get("scope") or config["scopes"],
            "access_token_ciphertext": encrypt_secret(str(token_data["access_token"])),
            "updated_at": _iso(utc_now()),
            "connected_at": _iso(utc_now()),
            "last_error": None,
        }
        if token_data.get("refresh_token"):
            token_fields["refresh_token_ciphertext"] = encrypt_secret(str(token_data["refresh_token"]))
        if token_data.get("expires_in"):
            token_fields["token_expires_at"] = _iso(utc_now() + timedelta(seconds=int(token_data["expires_in"])))
        tenant_ref = db.collection("tenants").document(str(state_data["tenant_id"]))
        tenant_snapshot = tenant_ref.get()
        tenant = tenant_snapshot.to_dict() if tenant_snapshot.exists else None
        if not isinstance(tenant, dict):
            raise ValueError("Tenant do callback OAuth não encontrado")
        channels = dict(tenant.get("channels") or {})
        channels[channel] = {**dict(channels.get(channel) or {}), **token_fields}
        tenant_ref.set({"channels": channels, "updated_at": utc_now()}, merge=True)
        state_reference.set({"status": "consumed", "consumed_at": _iso(utc_now())}, merge=True)
        return {"connected": True, "channel": channel, "tenant_id": str(state_data["tenant_id"]), "external_account_id": external_id, "external_account_name": external_name, "status": "connected"}
    except (requests.RequestException, ValueError, SecretStoreError) as exc:
        state_reference.set({"status": "error", "last_error": str(exc)[:240], "updated_at": _iso(utc_now())}, merge=True)
        raise RuntimeError("Não foi possível concluir a autorização deste canal.") from exc


def disconnect_oauth(db: Any, channel: str, tenant_id: str) -> None:
    channel = str(channel).strip().lower()
    _definition(channel)
    tenant_ref = db.collection("tenants").document(str(tenant_id))
    snapshot = tenant_ref.get()
    tenant = snapshot.to_dict() if snapshot.exists else None
    if not isinstance(tenant, dict):
        raise ValueError("Tenant não encontrado")
    channels = dict(tenant.get("channels") or {})
    current = dict(channels.get(channel) or {})
    for key in ("access_token_ciphertext", "refresh_token_ciphertext", "external_account_id", "external_account_name", "scope", "token_expires_at", "connected_at"):
        current.pop(key, None)
    current.update({"status": "disabled", "last_error": None, "updated_at": _iso(utc_now())})
    channels[channel] = current
    tenant_ref.set({"channels": channels, "updated_at": utc_now()}, merge=True)
