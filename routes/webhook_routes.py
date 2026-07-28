import time
import threading
from datetime import datetime, timezone
from flask import Blueprint, request
from config import Config
from services.groq_service import transcrever_audio_groq, analisar_imagem_groq
from services.evolution_service import send_whatsapp, notificar_erro_admin
from workflows.central_flow import process_central_flow
from workflows.client_flow import process_client_flow

webhook_bp = Blueprint('webhook_bp', __name__)

PROCESSADOS = {}
processados_lock = threading.Lock()

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
        event_name = data.get('event', '').lower()
        if event_name not in ["messages.upsert", "messages_upsert"] or "data" not in data:
            return

        msg_data = data['data']
        key = msg_data.get('key', {})
        msg_id = key.get('id')
        
        if msg_id:
            with processados_lock:
                agora_tempo = time.time()
                for k in [k for k, v in PROCESSADOS.items() if agora_tempo - v > 60]:
                    del PROCESSADOS[k]
                if msg_id in PROCESSADOS:
                    return
                PROCESSADOS[msg_id] = agora_tempo

        nome_instancia_atual = data.get('instance')
        central_instance = Config.EVOLUTION_INSTANCE_NAME
        if not nome_instancia_atual:
            return

        phone_number = key.get('remoteJid', '')
        if not phone_number or '@g.us' in phone_number or (Config.NUMERO_ASSISTANTE and Config.NUMERO_ASSISTANTE in phone_number):
            return

        message = msg_data.get('message', {})
        
        audio_message = message.get('audioMessage')
        document_message = message.get('documentMessage') or message.get('documentWithCaptionMessage', {}).get('message', {}).get('documentMessage')
        image_message = message.get('imageMessage') or message.get('extendedTextMessage', {}).get('contextInfo', {}).get('quotedMessage', {}).get('imageMessage')

        message_text = message.get('conversation') or message.get('extendedTextMessage', {}).get('text', '')

        if audio_message:
            url_audio = audio_message.get('url')
            if url_audio:
                send_whatsapp(phone_number, "🎙️ *A ouvir o seu áudio...*", instance_name=nome_instancia_atual)
                message_text = transcrever_audio_groq(url_audio)

        if image_message and not message_text.startswith('/criar-arte'):
            url_imagem = image_message.get('url')
            caption = image_message.get('caption', '')
            if url_imagem:
                send_whatsapp(phone_number, "👁️ *A analisar o documento/imagem...*", instance_name=nome_instancia_atual)
                instrucao = caption if caption else "Analise e extraia todas as informações deste comprovativo ou imagem."
                analise_foto = analisar_imagem_groq(url_imagem, instrucao=instrucao)
                if analise_foto:
                    message_text = f"[ANÁLISE DA IMAGEM/DOCUMENTO: {analise_foto}]\nTexto do cliente: {caption}"

        if not message_text and not document_message:
            return

        msg_clean = message_text.lower().strip()
        agora = datetime.now(timezone.utc)
        is_from_me = key.get('fromMe') is True or str(key.get('fromMe')).lower() == 'true'

        if nome_instancia_atual == central_instance:
            process_central_flow(phone_number, message_text, msg_clean, is_from_me, agora)
        else:
            process_client_flow(nome_instancia_atual, phone_number, message_text, msg_clean, document_message, is_from_me, agora)

    except Exception as e:
        erro_completo = f"Erro Webhook (Instância: {data.get('instance')}): {e}"
        print(f"❌ {erro_completo}")
        notificar_erro_admin(erro_completo)
