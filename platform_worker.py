import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone

import redis
import requests
from firebase_admin import firestore

import extensions
from config import Config
from services.n8n_service import dispatch_campaign_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-platform-worker")
QUEUE = "negobot:campaigns"


def now():
    return datetime.now(timezone.utc)


def spin(text: str) -> str:
    pattern = re.compile(r"\{([^{}]+)\}")
    while True:
        match = pattern.search(text)
        if not match:
            return text
        choices = match.group(1).split("|")
        text = text[: match.start()] + random.choice(choices) + text[match.end() :]


def clean_phone(value: str) -> str:
    return re.sub(r"\D", "", str(value or "").split("@")[0])


def send_text(instance_name: str, phone: str, text: str) -> bool:
    number = clean_phone(phone)
    if len(number) < 8:
        return False
    url = f"{str(Config.EVOLUTION_API_URL).rstrip('/')}/message/sendText/{instance_name}"
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"number": number, "text": spin(text), "delay": random.randint(1200, 4500), "linkPreview": False}
    for attempt in range(1, 4):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=45)
            if response.status_code in {200, 201}:
                return True
            if response.status_code < 500:
                break
        except requests.RequestException as exc:
            logger.warning("Falha de rede no envio para %s (tentativa %s): %s", number, attempt, exc)
        if attempt < 3:
            time.sleep(min(attempt * 2, 4))
    return False


def dispatch_non_whatsapp_channels(campaign_id: str, campaign: dict[str, object]) -> dict[str, object] | None:
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


def process_campaign(campaign_id: str, queue):
    db = extensions.db
    campaign_ref = db.collection("campaigns").document(campaign_id)
    campaign_doc = campaign_ref.get()
    if not campaign_doc.exists:
        return
    campaign = campaign_doc.to_dict() or {}
    if campaign.get("status") in {"cancelled", "completed"}:
        return
    tenant_id = campaign.get("tenant_id")
    instance_name = campaign.get("instance_name")
    if not instance_name:
        tenant_doc = db.collection("tenants").document(tenant_id).get()
        instance_name = (tenant_doc.to_dict() or {}).get("instance_name") if tenant_doc.exists else None
    instance_name = instance_name or Config.EVOLUTION_INSTANCE_NAME
    orchestration = dispatch_non_whatsapp_channels(campaign_id, campaign)
    orchestration_fields = {"status": "running", "started_at": now()}
    if orchestration is not None:
        orchestration_fields["orchestration_status"] = "sent" if orchestration.get("sent") else ("not_configured" if not orchestration.get("configured") else "failed")
        orchestration_fields["orchestration_request_id"] = orchestration.get("request_id")
        if orchestration.get("error"):
            orchestration_fields["orchestration_error"] = str(orchestration["error"])[:500]
    campaign_ref.set(orchestration_fields, merge=True)
    recipients = db.collection("campaign_recipients").where("campaign_id", "==", campaign_id).where("status", "==", "queued").stream()
    for recipient in recipients:
        control = queue.get(f"negobot:campaign:{campaign_id}:control")
        if control == "pause":
            campaign_ref.set({"status": "paused", "updated_at": now()}, merge=True)
            return
        if control == "cancel":
            campaign_ref.set({"status": "cancelled", "updated_at": now()}, merge=True)
            return
        data = recipient.to_dict() or {}
        phone = clean_phone(data.get("phone"))
        recipient.reference.set({"status": "sending", "attempts": int(data.get("attempts", 0)) + 1}, merge=True)
        ok = send_text(instance_name, phone, campaign.get("message", ""))
        recipient.reference.set({"status": "sent" if ok else "failed", "sent_at": now() if ok else None}, merge=True)
        campaign_ref.set({"sent": firestore.Increment(1) if ok else firestore.Increment(0), "failed": firestore.Increment(0) if ok else firestore.Increment(1)}, merge=True)
        time.sleep(random.uniform(7, 15))
    campaign_ref.set({"status": "completed", "finished_at": now()}, merge=True)
    queue.delete(f"negobot:campaign:{campaign_id}:control")


def main():
    extensions.init_extensions()
    queue = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/1"), decode_responses=True)
    while True:
        job = queue.blpop(QUEUE, timeout=30)
        if not job:
            continue
        try:
            process_campaign(job[1], queue)
        except Exception:
            logger.exception("Erro ao processar campanha %s", job[1])
            extensions.db.collection("campaigns").document(job[1]).set({"status": "failed", "updated_at": now()}, merge=True)


if __name__ == "__main__":
    main()
