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
    agora = datetime.now(timezone.utc).timestamp()
    with processados_lock:
        chaves_para_remover = [
            msg_id for msg_id, ts in PROCESSADOS.items() if agora - ts > 600
        ]
        for msg_id in chaves_para_remover:
            del PROCESSADOS[msg_id]

@webhook_bp.route('/webhook-global', methods=['POST'])
@webhook_bp.route('/webhook-cliente', methods=['POST'])
@webhook_bp.route('/webhook', methods=['POST'])
def universal_webhook():
    data = request.json
    if not data:
        return 'OK', 200

    # Responde 200 OK imediatamente para a Evolution API para não dar timeout
    # e processa toda a lógica da IA/fluxo em uma thread separada
    threading.Thread(target=processar_webhook_background, args=(data,)).start()
    return 'OK', 200

def processar_webhook_background(data):
    try:
        limpar_historico_processados()

        event_name = data.get('event', '').lower()

        # Filtra apenas eventos válidos de mensagens
        if event_name not in ["messages.upsert", "messages_upsert"]:
            return

        data_payload = data.get('data', {})
        if not data_payload:
            return

        key = data_payload.get('key', {})
        
        # Ignora mensagens enviadas pelo próprio bot para evitar loops infinitos
        if key.get('fromMe', False):
            return

        msg_id = key.get('id')
        if msg_id:
            with processados_lock:
                if msg_id in PROCESSADOS:
                    logger.info(f"Mensagem duplicada ignorada: {msg_id}")
                    return
                PROCESSADOS[msg_id] = datetime.now(timezone.utc).timestamp()

        # Identifica qual instância recebeu a mensagem
        instance_name = data.get('instance', Config.EVOLUTION_INSTANCE_NAME)

        # Se for a instância do Negobot central, roda o fluxo comercial SaaS.
        # Caso contrário, roda o fluxo do cliente subscritor.
        if instance_name == Config.EVOLUTION_INSTANCE_NAME:
            process_central_flow(data)
        else:
            process_client_flow(data)

    except Exception as e:
        logger.error(f"Erro ao processar webhook em background: {str(e)}", exc_info=True)
        try:
            notificar_erro_admin(f"Erro no Webhook: {str(e)}")
        except Exception:
            pass
