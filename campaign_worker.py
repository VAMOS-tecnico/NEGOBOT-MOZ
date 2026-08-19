"""Worker persistente para campanhas WhatsApp multi-tenant.

O processo é deliberadamente separado do webhook e do servidor HTTP. A fila Redis
contém apenas IDs de campanha; todos os destinatários são relidos no Firestore,
sempre filtrados por tenant e revalidados imediatamente antes do envio.
"""
from __future__ import annotations

import logging
import os
import random
import re
import time
from datetime import datetime, time as clock_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from firebase_admin import firestore

import extensions
from services.evolution_service import send_whatsapp
from services.group_automation_service import authorized_group_jids
from services.n8n_service import dispatch_campaign_event
from services.plan_service import entitlements_for_tenant
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-campaign-worker")

CAMPAIGN_QUEUE = "negobot:campaigns"
SCHEDULED_QUEUE = "negobot:campaigns:scheduled"
CONTROL_PREFIX = "negobot:campaign:"
MAX_ATTEMPTS = 3
DEFAULT_DAILY_LIMIT = 200
DEFAULT_MIN_DELAY = 5.0
DEFAULT_MAX_DELAY = 12.0
DEFAULT_SILENCE_START = "22:00"
DEFAULT_SILENCE_END = "08:00"
DEFAULT_TIMEZONE = "Africa/Maputo"
OPT_OUT_WORDS = {"parar", "stop", "sair", "unsubscribe", "cancelar", "cancel"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clean_phone(value: Any) -> str:
    raw = str(value or "").strip()
    if "@g.us" in raw:
        return raw
    return re.sub(r"\D", "", raw.split("@")[0])


def _timezone(name: Any) -> ZoneInfo:
    try:
        return ZoneInfo(str(name or DEFAULT_TIMEZONE))
    except Exception:
        logger.warning("Timezone inválido %r; a usar %s", name, DEFAULT_TIMEZONE)
        return ZoneInfo(DEFAULT_TIMEZONE)


def parse_datetime(value: Any, timezone_name: Any = DEFAULT_TIMEZONE) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_timezone(timezone_name))
    return parsed.astimezone(timezone.utc)


def _clock(value: Any, fallback: str) -> clock_time:
    try:
        text = str(value or fallback).strip()
        hour, minute = [int(part) for part in text.split(":", 1)]
        return clock_time(hour=hour, minute=minute)
    except (TypeError, ValueError):
        hour, minute = [int(part) for part in fallback.split(":", 1)]
        return clock_time(hour=hour, minute=minute)


def in_silence_window(moment: datetime, tenant: dict[str, Any]) -> bool:
    settings = tenant.get("campaign_settings") if isinstance(tenant.get("campaign_settings"), dict) else {}
    timezone_name = settings.get("timezone") or tenant.get("campaign_timezone") or DEFAULT_TIMEZONE
    local = moment.astimezone(_timezone(timezone_name))
    start = _clock(settings.get("silence_start") or tenant.get("campaign_silence_start"), DEFAULT_SILENCE_START)
    end = _clock(settings.get("silence_end") or tenant.get("campaign_silence_end"), DEFAULT_SILENCE_END)
    current = local.time()
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def next_allowed_time(moment: datetime, tenant: dict[str, Any]) -> datetime:
    settings = tenant.get("campaign_settings") if isinstance(tenant.get("campaign_settings"), dict) else {}
    timezone_name = settings.get("timezone") or tenant.get("campaign_timezone") or DEFAULT_TIMEZONE
    tz = _timezone(timezone_name)
    local = moment.astimezone(tz)
    end = _clock(settings.get("silence_end") or tenant.get("campaign_silence_end"), DEFAULT_SILENCE_END)
    candidate = datetime.combine(local.date(), end, tzinfo=tz)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def _scheduled_at(campaign: dict[str, Any], tenant: dict[str, Any]) -> datetime | None:
    settings = tenant.get("campaign_settings") if isinstance(tenant.get("campaign_settings"), dict) else {}
    timezone_name = campaign.get("timezone") or settings.get("timezone") or tenant.get("campaign_timezone") or DEFAULT_TIMEZONE
    return parse_datetime(campaign.get("scheduled_at"), timezone_name)


def _requeue_at(queue: Any, campaign_id: str, when: datetime) -> None:
    queue.zadd(SCHEDULED_QUEUE, {campaign_id: when.timestamp()})


def promote_scheduled(queue: Any) -> None:
    due = queue.zrangebyscore(SCHEDULED_QUEUE, 0, now_utc().timestamp(), start=0, num=50)
    for campaign_id in due:
        removed = queue.zrem(SCHEDULED_QUEUE, campaign_id)
        if removed:
            queue.rpush(CAMPAIGN_QUEUE, campaign_id)


def control_value(queue: Any, campaign_id: str) -> str:
    return str(queue.get(f"{CONTROL_PREFIX}{campaign_id}:control") or "").strip().lower()


def _tenant_and_campaign(campaign_id: str) -> tuple[Any, str, dict[str, Any], dict[str, Any]] | None:
    db = extensions.db
    document = db.collection("campaigns").document(campaign_id).get()
    if not document.exists:
        logger.warning("Campanha inexistente: %s", campaign_id)
        return None
    campaign = document.to_dict() or {}
    tenant_id = str(campaign.get("tenant_id") or "").strip()
    if not tenant_id:
        logger.error("Campanha %s sem tenant_id; rejeitada", campaign_id)
        return None
    tenant_document = db.collection("tenants").document(tenant_id).get()
    if not tenant_document.exists:
        logger.error("Tenant %s não encontrado para campanha %s", tenant_id, campaign_id)
        return None
    return document.reference, tenant_id, campaign, tenant_document.to_dict() or {}


def _delivery_delays(tenant: dict[str, Any]) -> tuple[float, float]:
    settings = tenant.get("campaign_settings") if isinstance(tenant.get("campaign_settings"), dict) else {}
    try:
        minimum = max(5.0, min(120.0, float(settings.get("min_delay_seconds") or DEFAULT_MIN_DELAY)))
        maximum = max(minimum, min(120.0, float(settings.get("max_delay_seconds") or DEFAULT_MAX_DELAY)))
        return minimum, maximum
    except (TypeError, ValueError):
        return DEFAULT_MIN_DELAY, DEFAULT_MAX_DELAY


def _campaign_daily_limit(tenant: dict[str, Any], campaign: dict[str, Any]) -> int:
    settings = tenant.get("campaign_settings") if isinstance(tenant.get("campaign_settings"), dict) else {}
    raw = campaign.get("daily_limit") or settings.get("daily_limit") or tenant.get("campaign_daily_limit") or DEFAULT_DAILY_LIMIT
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_DAILY_LIMIT


def _daily_key(tenant_id: str, moment: datetime) -> str:
    return f"negobot:campaign:daily:{tenant_id}:{moment.date().isoformat()}"


def _claim_daily_slot(queue: Any, tenant_id: str, limit: int, moment: datetime) -> bool:
    key = _daily_key(tenant_id, moment)
    count = int(queue.incr(key))
    if count == 1:
        queue.expire(key, 172800)
    if count <= limit:
        return True
    queue.decr(key)
    return False


def _mark_counter(campaign_ref: Any, field: str, amount: int = 1) -> None:
    campaign_ref.set({field: firestore.Increment(amount), "updated_at": now_utc()}, merge=True)


def _recipient_allowed(contact: dict[str, Any]) -> bool:
    return bool(contact.get("opt_in") is True and not contact.get("do_not_contact"))


def _group_recipient_allowed(data: dict[str, Any], tenant_id: str, instance_name: str) -> bool:
    if str(data.get("recipient_type") or "").lower() != "group":
        return False
    group_jid = clean_phone(data.get("group_jid") or data.get("phone"))
    if not group_jid.endswith("@g.us") or data.get("group_authorized") is not True:
        return False
    return group_jid in set(authorized_group_jids(tenant_id, instance_name))


def _contact_for_recipient(db: Any, data: dict[str, Any]) -> dict[str, Any]:
    contact_id = str(data.get("contact_id") or "").strip()
    if not contact_id:
        return {}
    ref = db.collection("contacts").document(contact_id)
    document = ref.get()
    return document.to_dict() or {} if document.exists else {}


def dispatch_non_whatsapp_channels(campaign_id: str, campaign: dict[str, Any]) -> dict[str, Any] | None:
    channels = {str(item).strip().lower() for item in (campaign.get("channels") or ["whatsapp"]) if str(item).strip()}
    non_whatsapp = sorted(channels - {"whatsapp"})
    if not non_whatsapp:
        return None
    return dispatch_campaign_event("campaign.dispatch", {
        "campaign_id": campaign_id,
        "tenant_id": campaign.get("tenant_id"),
        "channels": non_whatsapp,
        "message": campaign.get("message", ""),
        "offer": campaign.get("offer", ""),
        "language": campaign.get("language", "pt-MZ"),
        "tone": campaign.get("tone", "profissional"),
        "scheduled_at": campaign.get("scheduled_at"),
    }, request_id=campaign_id)


def _send_with_retries(instance_name: str, phone: str, message: str) -> bool:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if send_whatsapp(phone, message, instance_name=instance_name):
            return True
        if attempt < MAX_ATTEMPTS:
            time.sleep(min(2 ** attempt, 8))
    return False


def process_campaign(campaign_id: str, queue: Any) -> None:
    resolved = _tenant_and_campaign(campaign_id)
    if not resolved:
        return
    campaign_ref, tenant_id, campaign, tenant = resolved
    status = str(campaign.get("status") or "queued").lower()
    if status in {"cancelled", "completed", "failed"}:
        return

    entitlements = entitlements_for_tenant(tenant)
    if not entitlements.get("mass_broadcast"):
        campaign_ref.set({"status": "blocked", "error": "mass_broadcast não permitido pelo plano", "updated_at": now_utc()}, merge=True)
        return

    instance_name = str(campaign.get("instance_name") or tenant.get("instance_name") or "").strip()
    if not instance_name or str(tenant.get("evolution_state") or "").lower() != "open":
        campaign_ref.set({"status": "waiting_connection", "error": "WhatsApp do tenant não está ligado", "updated_at": now_utc()}, merge=True)
        _requeue_at(queue, campaign_id, now_utc() + timedelta(minutes=5))
        return

    scheduled = _scheduled_at(campaign, tenant)
    if scheduled and scheduled > now_utc():
        campaign_ref.set({"status": "scheduled", "updated_at": now_utc()}, merge=True)
        _requeue_at(queue, campaign_id, scheduled)
        return

    moment = now_utc()
    if in_silence_window(moment, tenant):
        next_time = next_allowed_time(moment, tenant)
        campaign_ref.set({"status": "scheduled", "resume_at": next_time, "updated_at": moment}, merge=True)
        _requeue_at(queue, campaign_id, next_time)
        return

    control = control_value(queue, campaign_id)
    if control == "cancel" or status == "cancelled":
        campaign_ref.set({"status": "cancelled", "finished_at": moment, "updated_at": moment}, merge=True)
        return
    if control == "pause" or status == "paused":
        campaign_ref.set({"status": "paused", "updated_at": moment}, merge=True)
        return

    orchestration = dispatch_non_whatsapp_channels(campaign_id, campaign)
    orchestration_fields = {"status": "running", "started_at": campaign.get("started_at") or moment, "updated_at": moment}
    if orchestration is not None:
        orchestration_fields["orchestration_status"] = "sent" if orchestration.get("sent") else ("not_configured" if not orchestration.get("configured") else "failed")
        orchestration_fields["orchestration_request_id"] = orchestration.get("request_id")
        if orchestration.get("error"):
            orchestration_fields["orchestration_error"] = str(orchestration["error"])[:500]
    campaign_ref.set(orchestration_fields, merge=True)
    db = extensions.db
    recipient_documents = db.collection("campaign_recipients").where("tenant_id", "==", tenant_id).where("campaign_id", "==", campaign_id).stream()
    processed = 0
    daily_limit = _campaign_daily_limit(tenant, campaign)
    for recipient_document in recipient_documents:
        data = recipient_document.to_dict() or {}
        recipient_id = recipient_document.id
        current_status = str(data.get("status") or "queued").lower()
        attempts = int(data.get("attempts") or 0)
        if current_status in {"sent", "skipped_opt_out", "skipped_group_not_authorized", "cancelled"} or attempts >= MAX_ATTEMPTS:
            continue
        lock_key = f"{CONTROL_PREFIX}{campaign_id}:recipient:{recipient_id}:lock"
        if not queue.set(lock_key, "1", nx=True, ex=180):
            continue
        try:
            control = control_value(queue, campaign_id)
            if control == "cancel":
                campaign_ref.set({"status": "cancelled", "updated_at": now_utc()}, merge=True)
                return
            if control == "pause":
                campaign_ref.set({"status": "paused", "updated_at": now_utc()}, merge=True)
                return
            is_group = str(data.get("recipient_type") or "").lower() == "group"
            if is_group:
                if not _group_recipient_allowed(data, tenant_id, instance_name):
                    recipient_document.reference.set({"status": "skipped_group_not_authorized", "skipped_at": now_utc(), "reason": "grupo deixou de ser verificado como próprio/admin"}, merge=True)
                    _mark_counter(campaign_ref, "skipped", 1)
                    continue
                contact = {}
            else:
                contact = _contact_for_recipient(db, data)
                if not _recipient_allowed(contact):
                    recipient_document.reference.set({"status": "skipped_opt_out", "skipped_at": now_utc(), "reason": "opt_in ausente ou revogado"}, merge=True)
                    _mark_counter(campaign_ref, "skipped", 1)
                    continue
            phone = clean_phone(data.get("phone") or data.get("group_jid") or contact.get("phone"))
            if len(phone) < 8:
                recipient_document.reference.set({"status": "failed", "attempts": attempts + 1, "error": "telefone inválido", "updated_at": now_utc()}, merge=True)
                _mark_counter(campaign_ref, "failed", 1)
                continue
            if not _claim_daily_slot(queue, tenant_id, daily_limit, now_utc()):
                next_time = next_allowed_time(now_utc(), tenant)
                campaign_ref.set({"status": "scheduled", "resume_at": next_time, "daily_limit_reached": True, "updated_at": now_utc()}, merge=True)
                _requeue_at(queue, campaign_id, next_time)
                return
            attempt = attempts + 1
            recipient_document.reference.set({"status": "sending", "attempts": attempt, "last_attempt_at": now_utc()}, merge=True)
            ok = _send_with_retries(instance_name, phone, str(campaign.get("message") or ""))
            if ok:
                recipient_document.reference.set({"status": "sent", "sent_at": now_utc(), "error": None}, merge=True)
                _mark_counter(campaign_ref, "sent", 1)
            else:
                final_status = "failed" if attempt >= MAX_ATTEMPTS else "queued"
                recipient_document.reference.set({"status": final_status, "attempts": attempt, "error": "Evolution API não confirmou o envio", "updated_at": now_utc()}, merge=True)
                if final_status == "failed":
                    _mark_counter(campaign_ref, "failed", 1)
            processed += 1
            time.sleep(random.uniform(*_delivery_delays(tenant)))
        finally:
            queue.delete(lock_key)

    remaining = [doc for doc in db.collection("campaign_recipients").where("tenant_id", "==", tenant_id).where("campaign_id", "==", campaign_id).stream() if str((doc.to_dict() or {}).get("status") or "").lower() in {"queued", "sending"}]
    if remaining:
        campaign_ref.set({"status": "queued", "updated_at": now_utc()}, merge=True)
        queue.rpush(CAMPAIGN_QUEUE, campaign_id)
    else:
        campaign_ref.set({"status": "completed", "finished_at": now_utc(), "updated_at": now_utc()}, merge=True)
        queue.delete(f"{CONTROL_PREFIX}{campaign_id}:control")
    logger.info("Campanha %s processada: %s destinatários avaliados", campaign_id, processed)


def main() -> None:
    import redis

    enforce_profile("campaign")
    extensions.init_extensions()
    queue = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/1"), decode_responses=True)
    logger.info("Worker de campanhas iniciado; fila=%s", CAMPAIGN_QUEUE)
    while True:
        try:
            promote_scheduled(queue)
            job = queue.blpop(CAMPAIGN_QUEUE, timeout=15)
            if not job:
                continue
            process_campaign(str(job[1]), queue)
        except Exception:
            logger.exception("Erro no worker de campanhas; a retomar após 5 segundos")
            time.sleep(5)


if __name__ == "__main__":
    main()
