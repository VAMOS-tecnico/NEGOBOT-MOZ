import threading
import logging
from datetime import datetime, timezone
from flask import Blueprint, request
from config import Config
from services.evolution_service import notificar_erro_admin, send_whatsapp, transcrever_audio_mensagem
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
    data = request.json
    if data:
        logger.warning("Webhook recebido: event=%s instance=%s", data.get("event"), data.get("instance"))
    if not data:
        return 'OK', 200

    # Processa em background sem travar o retorno do webhook
    threading.Thread(target=processar_webhook_background, args=(data,)).start()
    return 'OK', 200

def processar_webhook_background(data):
    try:
        limpar_historico_processados()

        event_name = data.get('event', '').lower()

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
