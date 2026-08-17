import threading
import logging
import re
import time
from datetime import datetime, timezone
from flask import Blueprint, request
from config import Config
import extensions
from services.evolution_service import notificar_erro_admin, send_whatsapp, transcrever_audio_mensagem
from services.incoming_queue import enqueue_incoming_event
from services.trial_service import ACTIVE_STATUS, PENDING_STATUS, active_fields, is_paid_plan
from workflows.central_flow import process_central_flow
from workflows.client_flow import process_client_flow

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook_bp', __name__)

PROCESSADOS = {}
processados_lock = threading.Lock()

def limpar_historico_processados():
    agora_ts = datetime.now(timezone.utc).timestamp()
    with processados_lock:
        chaves_para_remover = [
            msg_id for msg_id, ts in PROCESSADOS.items() if agora_ts - ts > 600
        ]
        for msg_id in chaves_para_remover:
            del PROCESSADOS[msg_id]

def extrair_texto_mensagem(data_payload):
    if not isinstance(data_payload, dict):
        return ""
    
    message = data_payload.get('message', {})
    if not isinstance(message, dict):
        return ""

    if 'conversation' in message and message['conversation']:
        return message['conversation']
    
    if 'extendedTextMessage' in message and isinstance(message['extendedTextMessage'], dict):
        return message['extendedTextMessage'].get('text', '')
        
    if 'imageMessage' in message and isinstance(message['imageMessage'], dict):
        return message['imageMessage'].get('caption', '')
        
    if 'videoMessage' in message and isinstance(message['videoMessage'], dict):
        return message['videoMessage'].get('caption', '')
        
    if 'documentMessage' in message and isinstance(message['documentMessage'], dict):
        return message['documentMessage'].get('caption', '')

    if 'audioMessage' in message:
        return "[Áudio gravado]"

    return data_payload.get('body', '') or ""

@webhook_bp.route('/webhook-global', methods=['POST'])
@webhook_bp.route('/webhook-cliente', methods=['POST'])
@webhook_bp.route('/webhook', methods=['POST'])
def universal_webhook():
    data = request.get_json(silent=True)
    if not data:
        return 'OK', 200
    logger.info("Webhook recebido: event=%s instance=%s", data.get("event"), data.get("instance"))
    try:
        result = enqueue_incoming_event(data)
        logger.info("Webhook enfileirado event_id=%s queue=%s", result["event_id"], result["queue"])
    except Exception:
        # Compatibilidade de disponibilidade: se o Redis estiver temporariamente
        # indisponível, não bloqueamos a Evolution; o processamento legado em
        # thread evita perda imediata até o worker/Redis recuperar.
        logger.exception("Redis indisponível; fallback temporário para thread")
        threading.Thread(target=processar_webhook_background, args=(data,), daemon=True).start()
    return 'OK', 200

def _connection_instance_name(data: dict) -> str:
    payload = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
    return str(data.get("instance") or payload.get("instance") or data.get("instanceId") or payload.get("instanceId") or "").strip()


def _connection_state(data: dict) -> str:
    payload = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
    nested = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    return str(payload.get("state") or payload.get("status") or nested.get("state") or data.get("state") or "").strip().lower()


def _mark_trial_connection_open(instance_name: str, data: dict) -> None:
    """Inicia a demonstração somente após a Evolution confirmar a ligação."""
    if not instance_name or instance_name == str(Config.EVOLUTION_INSTANCE_NAME).strip():
        return
    if extensions.db is None:
        extensions.init_extensions()
    if extensions.db is None:
        raise RuntimeError("Firestore indisponível para CONNECTION_UPDATE")

    digits = re.sub(r"\D", "", instance_name)
    canonical_ref = extensions.db.collection("clientes_bot").document(instance_name)
    canonical_doc = canonical_ref.get()
    canonical_data = canonical_doc.to_dict() if canonical_doc.exists else {}
    legacy_ref = extensions.db.collection("clientes_bot").document(f"cliente_{digits}") if digits else None
    legacy_doc = legacy_ref.get() if legacy_ref is not None else None
    legacy_data = legacy_doc.to_dict() if legacy_doc is not None and legacy_doc.exists else {}
    current = {**legacy_data, **canonical_data}

    tenants = extensions.db.collection("tenants")
    tenant_refs = []
    try:
        tenant_refs.extend(list(tenants.where("instance_name", "==", instance_name).limit(10).stream()))
    except Exception:
        logger.debug("Não foi possível procurar tenant por instance_name", exc_info=True)
    if not tenant_refs and digits:
        try:
            tenant_refs.extend(list(tenants.where("telefone_proprietario", "==", digits).limit(10).stream()))
        except Exception:
            logger.debug("Não foi possível procurar tenant por telefone", exc_info=True)
    if not current and not tenant_refs:
        logger.info("CONNECTION_UPDATE ignorado para instância desconhecida=%s", instance_name)
        return

    if is_paid_plan(current):
        fields = {"evolution_state": "open", "instance_name": instance_name}
    elif current.get("trial_connected_at") or current.get("trial_connection_confirmed") is True:
        fields = {"evolution_state": "open", "trial_status": ACTIVE_STATUS}
    else:
        fields = active_fields(digits or instance_name)

    canonical_ref.set(fields, merge=True)
    if legacy_ref is not None and legacy_ref.path != canonical_ref.path:
        legacy_ref.set(fields, merge=True)
    if digits:
        extensions.db.collection("clientes").document(digits).set({
            "status": "trial" if not is_paid_plan(current) else "active",
            "trial_status": fields.get("trial_status", current.get("trial_status")),
            **{key: fields[key] for key in ("trial_connected_at", "trial_expires_at", "data_ativacao", "data_expiracao") if key in fields},
        }, merge=True)

    tenant_fields = {
        "instance_name": instance_name,
        "telefone_proprietario": digits or instance_name,
        "evolution_state": "open",
        **{key: fields[key] for key in ("trial_status", "trial_connected_at", "trial_expires_at", "data_ativacao", "data_expiracao", "trial_connection_confirmed") if key in fields},
    }
    for tenant_ref in tenant_refs:
        tenant_ref.set(tenant_fields, merge=True)
    logger.info("Ligação WhatsApp confirmada instance=%s trial_status=%s", instance_name, fields.get("trial_status", current.get("trial_status")))


def _handle_connection_update(data: dict) -> None:
    instance_name = _connection_instance_name(data)
    state = _connection_state(data)
    if not instance_name:
        logger.warning("CONNECTION_UPDATE sem nome de instância")
        return
    if state == "open":
        _mark_trial_connection_open(instance_name, data)
    elif state in {"close", "connecting", "qr", "refused"}:
        logger.info("Estado WhatsApp instance=%s state=%s; demonstração permanece pendente/activa", instance_name, state)


def processar_webhook_background(data):
    try:
        queued_at = data.get("_negobot_queue_enqueued_at") if isinstance(data, dict) else None
        if queued_at:
            logger.info("Mensagem iniciou processamento wait_ms=%d", int((time.time() - float(queued_at)) * 1000))
        limpar_historico_processados()

        event_name = data.get('event', '').lower()

        if event_name in {"connection.update", "connection_update"}:
            _handle_connection_update(data)
            return

        # 🚫 1. Filtrar apenas mensagens recebidas/enviadas reais
        if event_name not in ["messages.upsert", "messages_upsert"]:
            return

        data_payload = data.get('data', {}) if isinstance(data.get('data'), dict) else data
        if not data_payload:
            return

        key = data_payload.get('key', {}) if isinstance(data_payload, dict) else {}
        is_from_me = key.get('fromMe', False)

        # 🚫 2. Ignorar mensagens enviadas pelo próprio bot
        if is_from_me:
            return

        remote_jid = key.get('remoteJid', '') or ''

        # 🚫 3. Ignorar Grupos de WhatsApp e Canais (Newsletters)
        if '@g.us' in remote_jid or '@newsletter' in remote_jid or data_payload.get('isGroup') is True:
            return

        # 🚫 4. Trava contra duplicados por ID de mensagem
        msg_id = key.get('id')
        if msg_id:
            with processados_lock:
                if msg_id in PROCESSADOS:
                    logger.info(f"Mensagem duplicada ignorada: {msg_id}")
                    return
                PROCESSADOS[msg_id] = datetime.now(timezone.utc).timestamp()

        # Extração de variáveis cruciais
        message_text = extrair_texto_mensagem(data_payload)
        agora = datetime.now(timezone.utc)

        # 🎯 CAPTURA ROBUSTA DA INSTÂNCIA (Evolution API v1 e v2)
        instance_name = (
            data.get('instance') or 
            data_payload.get('instance') or 
            data.get('instanceId') or 
            Config.EVOLUTION_INSTANCE_NAME
        )
        
        # Se vier o JID completo da instância (ex: 258878244010@s.whatsapp.net), limpa para ficar apenas os dígitos
        if '@' in str(instance_name):
            instance_name = str(instance_name).split('@')[0]

        phone_number = remote_jid or key.get('participant') or key.get('id') or ''

        # Áudio: obter a mídia da Evolution e transcrever com Whisper/Groq antes do fluxo normal.
        if isinstance(data_payload.get('message'), dict) and 'audioMessage' in data_payload.get('message', {}):
            transcript = transcrever_audio_mensagem(data_payload, instance_name=instance_name)
            if transcript:
                message_text = transcript
                logger.warning("Áudio transcrito com sucesso para o fluxo do bot.")
            else:
                send_whatsapp(
                    phone_number,
                    "🎙️ Recebi a sua mensagem de voz, mas não consegui transcrevê-la neste momento. Por favor, tente enviar novamente ou escreva a mensagem.",
                    instance_name=instance_name
                )
                return

        msg_clean = message_text.strip().lower()

        # Anexos se existirem
        message_obj = data_payload.get('message', {}) if isinstance(data_payload, dict) else {}
        document_message = (
            message_obj.get('documentMessage') or 
            message_obj.get('documentWithCaptionMessage', {}).get('message', {}).get('documentMessage')
        )

        # 🚦 ROTEAMENTO DE FLUXO (Central vs Cliente)
        central_name = str(Config.EVOLUTION_INSTANCE_NAME).strip()
        current_name = str(instance_name).strip()

        if current_name == central_name:
            logger.info(f"Roteando para o Fluxo Central [Instância: {current_name}]")
            process_central_flow(
                data=data,
                message_text=message_text,
                msg_clean=msg_clean,
                is_from_me=is_from_me,
                agora=agora
            )
        else:
            logger.info(f"Roteando para o Fluxo do Cliente [Instância: {current_name}]")
            process_client_flow(
                nome_instancia_atual=current_name,
                phone_number=phone_number,
                message_text=message_text,
                msg_clean=msg_clean,
                document_message=document_message,
                is_from_me=is_from_me,
                agora=agora
            )

    except Exception as e:
        logger.error(f"Erro ao processar webhook em background: {str(e)}", exc_info=True)
        try:
            notificar_erro_admin(f"Erro no Webhook: {str(e)}")
        except Exception:
            pass
