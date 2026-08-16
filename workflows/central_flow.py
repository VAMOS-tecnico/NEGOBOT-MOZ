import re
import logging
import time
from datetime import datetime, timezone

from config import Config
import extensions
from services.evolution_service import (
    send_whatsapp, 
    criar_e_configurar_instancia_automatica, 
    gerar_e_enviar_qrcode_central
)
from services.flow_handlers import (
    checar_timeout_atendimento_humano,
    processar_pagamento,
    processar_duvida_pagamento,
    processar_geracao_imagem,
    processar_teste_gratis,
    processar_suporte_humano,
    processar_resposta_ia
)

logger = logging.getLogger(__name__)


def process_central_flow(phone_number_or_data=None, message_text: str = "", msg_clean: str = "", is_from_me: bool = False, agora: datetime = None, data: dict = None, **kwargs):
    """
    Router principal do Negobot Moz: valida o payload, segurança e direciona para os handlers específicos.
    """
    try:
        if agora is None:
            agora = datetime.now(timezone.utc)

        payload = data if data is not None else phone_number_or_data

        # 1. Extração do identificador (JID)
        raw_jid = ""
        if isinstance(payload, dict):
            data_payload = payload.get('data', {}) if isinstance(payload.get('data'), dict) else payload
            key = data_payload.get('key', {}) if isinstance(data_payload, dict) else {}
            if isinstance(key, dict):
                raw_jid = key.get('remoteJid') or key.get('participant') or key.get('id') or ''
            else:
                raw_jid = str(key)
        else:
            raw_jid = str(payload or '')

        raw_jid_str = str(raw_jid).strip().lower()

        # 🚫 Bloqueio de Grupos
        if "@g.us" in raw_jid_str or (isinstance(payload, dict) and payload.get('data', {}).get('key', {}).get('participant')):
            return

        clean_phone = re.sub(r'\D', '', raw_jid_str.split('@')[0])
        if not clean_phone:
            return

        central_instance = getattr(Config, 'EVOLUTION_INSTANCE_NAME', 'central')

        # Extração de texto
        if not message_text and isinstance(payload, dict):
            data_payload = payload.get('data', {}) if isinstance(payload.get('data'), dict) else payload
            msg_obj = data_payload.get('message', {}) if isinstance(data_payload, dict) else {}
            message_text = msg_obj.get('conversation') or msg_obj.get('extendedTextMessage', {}).get('text') or ""

        msg_clean = (msg_clean if msg_clean else message_text).lower().strip()

        # ⚠️ Atendente humano via interface
        if is_from_me:
            chat_ref = extensions.db.collection('chats').document(clean_phone)
            chat_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
            return

        # 💳 1. Comprovativo M-Pesa
        eh_comprovativo = (
            msg_clean.startswith('#pago') or msg_clean.startswith('#comprovativo') or
            "transferiste" in msg_clean or "confirmado" in msg_clean or
            (bool(re.search(r'\b(3g|4g|5g|[a-z0-9]{10})\b', message_text.lower())) and "m-pesa" in message_text.lower())
        )
        if eh_comprovativo:
            if processar_pagamento(clean_phone, message_text, central_instance):
                return

        # 💳 2. Dúvida de Pagamento
        palavras_duvida = ["como pago", "como pagar", "fazer o pagamento", "dados de pagamento", "qual e o mpesa", "numero do mpesa", "onde pago"]
        if any(termo in msg_clean for termo in palavras_duvida):
            processar_duvida_pagamento(clean_phone, message_text, central_instance)
            return

        # 🎨 3. Geração de Imagem
        gatilhos_imagem = ["#imagem", "gerar imagem", "cria uma arte", "criar imagem", "faz um cartaz", "gerar arte"]
        if any(termo in msg_clean for termo in gatilhos_imagem):
            processar_geracao_imagem(clean_phone, message_text, central_instance)
            return

        # 🛡️ Filtro de links isolados
        if ("youtube.com" in msg_clean or "youtu.be" in msg_clean or "tiktok.com" in msg_clean) and len(msg_clean.split()) <= 2:
            send_whatsapp(clean_phone, "Olá! 👋 Sou o assistente oficial do **Negobot Moz**. Escreva **TESTE** para experimentar grátis!", instance_name=central_instance)
            return

        # Estados do Firestore
        chat_ref = extensions.db.collection('chats').document(clean_phone)
        chat_doc = chat_ref.get()
        chat_dados = chat_doc.to_dict() if chat_doc.exists else {}

        cliente_doc_ref = extensions.db.collection('clientes').document(clean_phone)
        cliente_doc = cliente_doc_ref.get()
        cliente_data = cliente_doc.to_dict() if cliente_doc.exists else {}
        status_cliente = cliente_data.get('status', 'prospect')

        if not cliente_doc.exists:
            cliente_doc_ref.set({"phone_number": clean_phone, "data_registro": agora, "status": "prospect"}, merge=True)

        # Comando #qrcode
        if msg_clean in {"#qrcode", "qrcode", "qr code"}:
            send_whatsapp(clean_phone, "🔄 *A gerar o seu novo QR Code...*\n\nSe o código anterior expirou, aguarda alguns segundos e lê o novo código no WhatsApp.", instance_name=central_instance)
            criar_e_configurar_instancia_automatica(clean_phone)
            time.sleep(2)
            gerar_e_enviar_qrcode_central(clean_phone)
            return

        # Gatilhos de Teste Grátis
        gatilhos_teste = [r'\bteste\b', r'\btestar\b', r'quero o bot', r'\bcomeçar\b', r'criar bot', r'\bdemo\b']
        if any(re.search(pattern, msg_clean) for pattern in gatilhos_teste):
            processar_teste_gratis(clean_phone, agora, central_instance)
            return

        # Atendimento Humano
        status_atendimento = chat_dados.get("status_atendimento", "bot")
        if status_atendimento == "humano":
            if checar_timeout_atendimento_humano(chat_ref, chat_dados, agora):
                status_atendimento = "bot"
            else:
                if msg_clean in ["/bot", "/reset", "continuar", "bot", "voltar"]:
                    chat_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                    status_atendimento = "bot"
                else:
                    chat_ref.set({"ultima_interacao": agora, "ultima_mensagem_por": "cliente_final"}, merge=True)
                    return

        # Pedido de Atendimento Humano
        gatilhos_humano = [r'falar com atendente', r'suporte humano', r'\batendente\b', r'\bhumano\b', r'#suporte', r'falar com pessoa']
        if any(re.search(pattern, msg_clean) for pattern in gatilhos_humano):
            processar_suporte_humano(clean_phone, chat_ref, agora, central_instance)
            return

        # Resposta da IA (Fallback)
        processar_resposta_ia(clean_phone, message_text, status_cliente, agora, central_instance, chat_ref)

    except Exception as e:
        logger.error(f"Erro no process_central_flow: {e}", exc_info=True)
