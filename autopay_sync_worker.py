"""Sincroniza transacoes_sucesso do AutoPay Android com os tenants NEGOBOT.

O worker nunca considera a resposta do Groq suficiente para confirmar um pagamento:
o estado pago, o ID, o valor, o destinatário, o pagador e a operação idempotente
Firestore são obrigatórios.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

import extensions
from firebase_admin import firestore

from services.evolution_service import send_whatsapp
from services.payment_service import identificar_plano_por_valor
from services.service_config import enforce_profile

LOGGER = logging.getLogger("autopay-sync")
COLLECTION = os.getenv("AUTOPAY_COLLECTION", "transacoes_sucesso")
RECEIVER_PHONE = re.sub(r"\D", "", os.getenv("MPESA_RECEIVER_PHONE", "855000929"))
GROQ_ENABLED = os.getenv("AUTOPAY_GROQ_ENABLED", "false").lower() == "true"


def _now():
    return datetime.now(timezone.utc)


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _amount(value: Any) -> float:
    text = str(value or "").strip().replace(" MT", "").replace("MT", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def normalize(snapshot) -> dict[str, Any]:
    data = snapshot.to_dict() or {}
    return {
        "ref": snapshot.reference,
        "id": str(data.get("id") or snapshot.id).upper(),
        "amount": _amount(data.get("amount")),
        "body": str(data.get("body") or ""),
        "processed_at": data.get("processed_at"),
        "sender_name": str(data.get("sender_name") or "Cliente"),
        "sender_phone": _digits(data.get("sender_phone")),
        "status": str(data.get("status") or "").lower(),
        "platform_status": str(data.get("platform_status") or "").lower(),
        "tenant_id": data.get("tenant_id"),
        "raw": data,
    }


def groq_compare(event: dict[str, Any], proof: str = "") -> dict[str, Any]:
    """Extrai dados sem permitir que o modelo confirme sozinho."""
    if not GROQ_ENABLED:
        return {"enabled": False, "matches_proof": None, "confidence": None}
    from services.groq_service import chamar_groq_rest

    prompt = (
        "Responde apenas JSON válido com as chaves transaction_id, amount, "
        "sender_phone, receiver_phone, matches_proof e confidence. "
        "Não inventes valores; usa null quando faltar informação."
    )
    text = f"SMS AutoPay: {event['body']}\nComprovativo: {proof}"
    raw = chamar_groq_rest([{"role": "user", "content": text}], system_prompt=prompt)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Groq não devolveu JSON")
        parsed = json.loads(raw[start : end + 1])
        return {
            "enabled": True,
            "matches_proof": parsed.get("matches_proof"),
            "confidence": parsed.get("confidence"),
            "transaction_id": str(parsed.get("transaction_id") or "").upper(),
            "amount": _amount(parsed.get("amount")),
            "sender_phone": _digits(parsed.get("sender_phone")),
            "receiver_phone": _digits(parsed.get("receiver_phone")),
        }
    except Exception as exc:
        LOGGER.warning("Groq não devolveu uma comparação estruturada: %s", type(exc).__name__)
        return {"enabled": True, "matches_proof": None, "confidence": None}


def _plan_for_event(event: dict[str, Any]):
    return identificar_plano_por_valor(event["amount"])


def _resolve_tenant(event: dict[str, Any]) -> str:
    explicit = str(event.get("tenant_id") or "").strip()
    if explicit:
        return explicit
    sender = event.get("sender_phone")
    if not sender or not extensions.db:
        return ""
    try:
        # Primeiro tenta o vínculo já persistido no tenant. Só aceita um
        # único resultado para evitar ativar a conta errada em caso de duplicação.
        phone_variants = {sender, sender[-9:], f"258{sender[-9:]}"}
        direct_tenants = set()
        for collection_name in ("tenants", "clientes_bot"):
            for variant in phone_variants:
                matches = extensions.db.collection(collection_name).where("telefone_proprietario", "==", variant).limit(5).stream()
                for match in matches:
                    direct_tenants.add(match.id)
        if len(direct_tenants) == 1:
            return next(iter(direct_tenants))
        if len(direct_tenants) > 1:
            LOGGER.warning("Pagamento AutoPay não associado: telefone corresponde a vários tenants")
            return ""

        intents = extensions.db.collection("payment_intents").where("status", "==", "pending").limit(50).stream()
        candidates = []
        for intent in intents:
            data = intent.to_dict() or {}
            if _digits(data.get("client_phone"))[-9:] == sender[-9:]:
                candidates.append((data.get("created_at"), intent.reference, data))
        if not candidates:
            return ""
        candidates.sort(key=lambda item: str(item[0] or ""), reverse=True)
        _, intent_ref, data = candidates[0]
        intent_ref.set({"status": "matched", "transaction_id": event["id"], "matched_at": firestore.SERVER_TIMESTAMP}, merge=True)
        return str(data.get("tenant_id") or "").strip()
    except Exception:
        LOGGER.exception("Não foi possível resolver a intenção de pagamento")
        return ""


def _confirm_transaction(event: dict[str, Any], plan: dict[str, Any], tenant_id: str):
    """Marca o pagamento e o tenant numa única transação Firestore."""
    transaction = firestore.client().transaction()
    payment_ref = event["ref"]
    tenant_ref = extensions.db.collection("tenants").document(tenant_id)
    client_ref = extensions.db.collection("clientes_bot").document(tenant_id)

    @firestore.transactional
    def commit(tx):
        payment_snapshot = payment_ref.get(transaction=tx)
        payment = payment_snapshot.to_dict() or {}
        if payment.get("platform_status") == "confirmed" or payment.get("usado") is True:
            return "already_confirmed"
        tx.update(payment_ref, {
            "platform_status": "confirmed",
            "usado": True,
            "used_by_tenant": tenant_id,
            "confirmed_at": firestore.SERVER_TIMESTAMP,
        })
        values = {
            "plano": plan["id"],
            "nome_plano": plan["nome"],
            "status_plano": "ativo",
            "disparo_liberado": plan["disparo_liberado"],
            "limite_conversas": plan["limite_conversas"],
            "ultimo_tx_id": event["id"],
            "metodo_pagamento": "M-Pesa AutoPay",
            "data_ativacao": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        tx.set(client_ref, values, merge=True)
        tx.set(tenant_ref, {
            **values,
            "plan": plan["id"],
            "plan_name": plan["nome"],
            "status": "ativo",
            "mass_broadcast": plan["disparo_liberado"],
            "tenant_id": tenant_id,
        }, merge=True)
        return "confirmed"

    return commit(transaction)


def _notify_activation(event: dict[str, Any], plan: dict[str, Any], tenant_id: str) -> bool:
    phone = event.get("sender_phone")
    if not phone:
        return False
    try:
        tenant = extensions.db.collection("tenants").document(tenant_id).get().to_dict() or {}
        instance_name = tenant.get("instance_name")
        text = (
            f"✅ O pagamento foi confirmado automaticamente.\\n\\n"
            f"Plano ativado: {plan['nome']}\\n"
            "Agora pode abrir a plataforma para ligar o seu WhatsApp e ler o QR Code."
        )
        sent = send_whatsapp(phone, text, instance_name=instance_name)
        event["ref"].set({
            "notification_status": "sent" if sent else "pending",
            "notification_at": firestore.SERVER_TIMESTAMP if sent else None,
        }, merge=True)
        return bool(sent)
    except Exception:
        LOGGER.exception("Falha ao notificar o cliente após ativação")
        return False


def process_event(snapshot):
    event = normalize(snapshot)
    if event["status"] not in {"pago", "paid", "confirmado", "confirmed"}:
        return "ignored_status"
    if event["platform_status"] in {"confirmed", "rejected"}:
        return "already_processed"
    plan = _plan_for_event(event)
    if not plan:
        snapshot.reference.set({"platform_status": "rejected", "reject_reason": "amount_below_plan", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        return "rejected_amount"
    if RECEIVER_PHONE and event["raw"].get("receiver_phone") and _digits(event["raw"].get("receiver_phone"))[-9:] != RECEIVER_PHONE[-9:]:
        snapshot.reference.set({"platform_status": "rejected", "reject_reason": "wrong_receiver", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        return "rejected_receiver"
    proof = str(event["raw"].get("proof_text") or event["raw"].get("comprovativo") or "")
    groq_result = groq_compare(event, proof) if (GROQ_ENABLED and proof) else {"enabled": False}
    if groq_result.get("enabled"):
        snapshot.reference.set({
            "groq_checked": True,
            "groq_matches_proof": groq_result.get("matches_proof"),
            "groq_confidence": groq_result.get("confidence"),
            "groq_checked_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)
        if groq_result.get("matches_proof") is False:
            snapshot.reference.set({"platform_status": "rejected", "reject_reason": "groq_mismatch", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            return "rejected_groq"
        if groq_result.get("transaction_id") and groq_result["transaction_id"] != event["id"]:
            snapshot.reference.set({"platform_status": "rejected", "reject_reason": "groq_transaction_mismatch", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            return "rejected_groq_transaction"
        if groq_result.get("amount") and abs(groq_result["amount"] - event["amount"]) > 0.01:
            snapshot.reference.set({"platform_status": "rejected", "reject_reason": "groq_amount_mismatch", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            return "rejected_groq_amount"
    tenant_id = _resolve_tenant(event)
    if not tenant_id:
        snapshot.reference.set({"platform_status": "pending_tenant", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        return "pending_tenant"
    event["tenant_id"] = tenant_id
    result = _confirm_transaction(event, plan, tenant_id)
    if result == "confirmed":
        _notify_activation(event, plan, tenant_id)
    LOGGER.info("AutoPay transação processada: estado=%s plano=%s", result, plan["id"])
    return result


def _on_snapshot(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name not in {"ADDED", "MODIFIED"}:
            continue
        try:
            process_event(change.document)
        except Exception:
            LOGGER.exception("Erro ao processar evento AutoPay sem imprimir conteúdo sensível")


def run_forever():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    enforce_profile("billing")
    extensions.init_extensions()
    LOGGER.info("AutoPay Sync Worker iniciado; coleção=%s", COLLECTION)
    while True:
        watch = None
        try:
            watch = extensions.db.collection(COLLECTION).on_snapshot(_on_snapshot)
            while True:
                time.sleep(60)
        except Exception:
            LOGGER.exception("Listener AutoPay interrompido; reconexão em 10 segundos")
            if watch:
                watch.unsubscribe()
            time.sleep(10)


if __name__ == "__main__":
    run_forever()
