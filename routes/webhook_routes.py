import threading
import logging
from datetime import datetime, timezone
from flask import Blueprint, request
from config import Config
from services.groq_service import transcrever_audio_groq, analisar_imagem
from services.evolution_service import send_whatsapp, notificar_erro_admin
from workflows.central_flow import process_central_flow
from workflows.client_flow import process_client_flow

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook_bp', __name__)

# Controle de mensagens duplicadas em memória
PROCESSADOS = {}
processados_lock = threading.Lock()

def limpar_historico_processados():
    """Limpa IDs antigos do cache em memória para evitar acúmulo."""
    agora_ts = datetime.now(timezone.utc).timestamp()
    with processados_lock:
        chaves_para_remover = [
            msg_id for msg_id, ts in PROCESSADOS.items() if agora_ts - ts > 600
        ]
        for msg_id in chaves_para_remover:
            del PROCESSADOS[msg_id]

def extrair_texto_mensagem(data_payload):
    """Extrai o texto da mensagem a partir do payload da Evolution API."""
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

    return data_payload.get('body', '') or ""

@webhook_bp.route('/webhook-global', methods=['POST'])
@webhook_bp.route('/webhook-cliente', methods=['POST'])
@webhook_bp.route('/webhook', methods=['POST'])
def universal_webhook():
    data = request.json
    if not data:
        return 'OK', 200

    threading.Thread(target=processar_webhook_background, args=(data,)).start()
    return 'OK', 200

def processar_webhook_background(data):
    try:
        limpar_historico_processados()

        event_name = data.get('event', '').lower()

        if event_name not in ["messages.upsert", "messages_upsert"]:
            return

        data_payload = data.get('data', {}) if isinstance(data.get('data'), dict) else data
        if not data_payload:
            return

        key = data_payload.get('key', {}) if isinstance(data_payload, dict) else {}
        is_from_me = key.get('fromMe', False)

        # Ignora mensagens enviadas pelo próprio bot para evitar loops infinitos
        if is_from_me:
            return

        msg_id = key.get('id')
        if msg_id:
            with processados_lock:
                if msg_id in PROCESSADOS:
                    logger.info(f"Mensagem duplicada ignorada: {msg_id}")
                    return
                PROCESSADOS[msg_id] = datetime.now(timezone.utc).timestamp()

        # Extração precisa das variáveis necessárias
        message_text = extrair_texto_mensagem(data_payload)
        msg_clean = message_text.strip().lower()
        agora = datetime.now(timezone.utc)

        instance_name = data.get('instance') or data.get('instanceId') or Config.EVOLUTION_INSTANCE_NAME
        phone_number = key.get('remoteJid') or key.get('participant') or key.get('id') or ''

        # Extração de anexos/documentos
        message_obj = data_payload.get('message', {}) if isinstance(data_payload, dict) else {}
        document_message = (
            message_obj.get('documentMessage') or 
            message_obj.get('documentWithCaptionMessage', {}).get('message', {}).get('documentMessage')
        )

        # Encaminhamento seguro com argumentos nomeados
        if instance_name == Config.EVOLUTION_INSTANCE_NAME:
            process_central_flow(data, message_text, msg_clean, is_from_me, agora)
        else:
            process_client_flow(
                nome_instancia_atual=instance_name,
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
