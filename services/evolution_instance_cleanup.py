"""Limpeza segura de instâncias Evolution desconectadas ou órfãs."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from urllib.parse import quote

import requests

from config import Config

logger = logging.getLogger("negobot-evolution-cleanup")
DEFAULT_GRACE_SECONDS = 30 * 60
ORPHAN_STATUSES = {"close", "closed", "disconnected", "refused", "offline"}


def _suffix(value: object) -> str:
    text = str(value or "")
    return text[-4:] if text else "none"


def _age_seconds(value: object) -> float:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return max(0.0, time.time() - parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _status(item: dict) -> str:
    return str(item.get("connectionStatus") or item.get("state") or "unknown").strip().lower()


def _is_candidate(item: dict, grace_seconds: int) -> tuple[bool, str]:
    status = _status(item)
    # A connected instance is never removed, even if it has a historical
    # disconnectionReasonCode in Evolution's record.
    if status == "open":
        return False, "connected"
    reason_code = str(item.get("disconnectionReasonCode") or "")
    reason_object = str(item.get("disconnectionObject") or "").lower()
    if reason_code == "401" and "device_removed" in reason_object:
        return True, "device_removed"
    if status in ORPHAN_STATUSES:
        return True, status
    if status == "connecting" and not item.get("ownerJid"):
        age = _age_seconds(item.get("updatedAt") or item.get("createdAt"))
        if age >= grace_seconds:
            return True, "connecting_without_owner_after_grace"
    return False, "within_grace_or_unknown"


def _headers() -> dict[str, str]:
    return {"apikey": str(Config.EVOLUTION_API_KEY or ""), "Content-Type": "application/json"}


def _base_url() -> str:
    return str(Config.EVOLUTION_API_URL or "").rstrip("/")


def _central_instance() -> str:
    return str(os.getenv("EVOLUTION_CENTRAL_INSTANCE_NAME") or getattr(Config, "EVOLUTION_INSTANCE_NAME", "") or "").strip()


def cleanup_orphan_instances(*, apply: bool = True, grace_seconds: int | None = None) -> dict[str, int]:
    """Delete only clearly orphaned client instances; safe to call repeatedly."""
    if str(os.getenv("EVOLUTION_AUTO_DELETE_DISCONNECTED", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
        return {"scanned": 0, "candidates": 0, "deleted": 0, "failed": 0}
    base = _base_url()
    if not base or not Config.EVOLUTION_API_KEY:
        return {"scanned": 0, "candidates": 0, "deleted": 0, "failed": 0}
    grace = max(300, int(grace_seconds or os.getenv("EVOLUTION_CONNECTING_GRACE_SECONDS", DEFAULT_GRACE_SECONDS)))
    response = requests.get(f"{base}/instance/fetchInstances", headers=_headers(), timeout=20)
    response.raise_for_status()
    payload = response.json() or []
    instances = payload if isinstance(payload, list) else payload.get("data") or payload.get("instances") or []
    central = _central_instance()
    summary = {"scanned": len(instances), "candidates": 0, "deleted": 0, "failed": 0}
    for item in instances:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("instanceName") or "").strip()
        if not name or name == central:
            continue
        candidate, reason = _is_candidate(item, grace)
        if not candidate:
            continue
        summary["candidates"] += 1
        if not apply:
            continue
        try:
            result = requests.delete(f"{base}/instance/delete/{quote(name, safe='')}", headers=_headers(), timeout=20)
            if 200 <= result.status_code < 300:
                summary["deleted"] += 1
                logger.info("Instância órfã removida name_suffix=%s status=%s reason=%s", _suffix(name), _status(item), reason)
            else:
                summary["failed"] += 1
                logger.warning("Falha ao remover instância name_suffix=%s http=%s", _suffix(name), result.status_code)
        except requests.RequestException:
            summary["failed"] += 1
            logger.exception("Erro ao remover instância órfã name_suffix=%s", _suffix(name))
    return summary


def delete_disconnected_instance(instance_name: str, state: str) -> bool:
    """Remove uma instância cliente após CONNECTION_UPDATE desconectado."""
    name = str(instance_name or "").strip()
    normalized_state = str(state or "").strip().lower()
    if not name or name == _central_instance() or normalized_state not in ORPHAN_STATUSES:
        return False
    if str(os.getenv("EVOLUTION_AUTO_DELETE_DISCONNECTED", "true")).strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    try:
        response = requests.delete(f"{_base_url()}/instance/delete/{quote(name, safe='')}", headers=_headers(), timeout=20)
        if 200 <= response.status_code < 300:
            logger.info("Instância desconectada removida name_suffix=%s state=%s", _suffix(name), normalized_state)
            return True
        logger.warning("Não foi possível remover instância name_suffix=%s http=%s", _suffix(name), response.status_code)
    except requests.RequestException:
        logger.exception("Erro ao remover instância desconectada name_suffix=%s", _suffix(name))
    return False
