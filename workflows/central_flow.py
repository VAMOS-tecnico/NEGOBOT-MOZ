import re
import time
import logging
from datetime import datetime, timedelta, timezone
from config import Config
import extensions
from database.chat_repo import (
    get_chat_history, 
    save_chat_history
)
from services.groq_service import chamar_groq_rest
from services.evolution_service import (
    send_whatsapp, 
    criar_e_configurar_instancia_automatica, 
    gerar_e_enviar_qrcode_central
)

logger = logging.getLogger(__name__)

def checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
    """Verifica se o tempo limite de espera por atendimento humano expirou."""
    if conversa_dados and conversa_dados.get("status_atendimento") == "humano":
        ultima_interacao = conversa_dados.get("ultima_interacao")
        ultima_msg_por = conversa_dados.get("ultima_mensagem_por")
        
        if ultima_msg_por == "cliente_final" and ultima_interacao:
            if ultima_interacao.tzinfo is None:
                ultima_interacao = ultima_interacao.replace(tzinfo=timezone.utc)
            
            minutos_decorridos = (agora - ultima_interacao).total_seconds() / 60.0
            if minutos_decorridos >= Config.TIMEOUT_HUMANO_MINUTOS:
                conversa_ref.set({
                    "status_atendimento": "bot",
                    "ultima_interacao": agora
                }, merge=True)
                return True
    return False

def process_central_flow(phone_number_or_data, message_text="", msg_clean="", is_from_me=False, agora=None):
    """Workflow central do Negobot Moz blindado contra erros de tipo e incompatibilidades de IA."""
    try:
        if agora is None:
            agora = datetime.now(timezone.utc)

        # 1. EXTRAÇÃO E SANITIZAÇÃO SEGURA DO NÚMERO DE TELEFONE/JID
        if isinstance(phone_number_or_data, dict):
            data_payload = phone_number_or_data.get('data', {}) if isinstance(phone_number_or_data.get('data'), dict) else phone_number_or_data
            key = data_payload.get('key', {}) if isinstance(data_payload, dict) else {}
            if isinstance(key, dict):
                phone_number = key.get('remoteJid') or key.get('participant') or key.get('id') or 'usuario_desconhecido'
            else:
                phone_number = str(key)
        else:
            phone_number = str(phone_number_or_data)

        phone_number = str(phone_number)
        central_instance = Config.EVOLUTION_INSTANCE_NAME

        # 2. CONSULTA AO FIRESTORE COM NÚMERO SANITIZADO
        chat_ref = extensions.db.collection('chats').document(phone_number)
        chat_doc = chat_ref.get()
        chat_dados = chat_doc.to_dict() if chat_doc.exists else {}

        # Ignora mensagens enviadas pelo atendente humano
        if is_from_me:
            chat_ref.set({"ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
            return

        # Registo de novo contacto (Prospect)
        cliente_doc_ref = extensions.db.collection('clientes').document(phone_number)
        if not cliente_doc_ref.get().exists:
            cliente_doc_ref.set({
                "phone_number": phone_number,
                "data_registro": agora,
                "status": "prospect"
            }, merge=True)

        # 3. COMANDO DE RE-GERAÇÃO DE QR CODE (#qrcode)
        if msg_clean == "#qrcode":
            send_whatsapp(phone_number, "🔄 A gerar QR Code...", instance_name=central_instance)
            criar_e_configurar_instancia_automatica(phone_number)
            time.sleep(2)
            gerar_e_enviar_qrcode_central(phone_number)
            return

        # 4. GATILHOS DE CRIAÇÃO E TESTE GRATUITO
        gatilhos_teste = ["teste", "testar", "quero o bot", "começar", "criar bot"]
        if any(g in msg_clean for g in gatilhos_teste):
            cliente_data_cur = cliente_doc_ref.get().to_dict() or {}
            status_atual = cliente_data_cur.get('status', 'prospect')
            
            if status_atual == 'prospect':
                send_whatsapp(phone_number, "⏳ *A preparar o seu teste de 2 dias...* 🚀", instance_name=central_instance)
                if criar_e_configurar_instancia_automatica(phone_number):
                    cliente_doc_ref.set({
                        "phone_number": phone_number,
                        "data_registro": agora,
                        "trial_start": agora,
                        "status": "trial"
                    }, merge=True)
                    tenant_id = re.sub(r'\D', '', phone_number)
                    extensions.db.collection('clientes_bot').document(tenant_id).set({
                        "status_plano": "demonstracao", 
                        "data_ativacao": agora, 
                        "data_expiracao": agora + timedelta(days=2)
                    })
                    time.sleep(3)
                    gerar_e_enviar_qrcode_central(phone_number)
                return

        # 5. CONTROLO DE ATENDIMENTO HUMANO & RESET DE MODO
        status_atendimento = chat_dados.get("status_atendimento", "bot")
        if status_atendimento == "humano":
            if checar_timeout_atendimento_humano(chat_ref, chat_dados, agora):
                status_atendimento = "bot"
            else:
                if msg_clean in ["/bot", "/reset", "continuar", "bot", "bom dia", "boa tarde", "boa noite", "ola", "olá", "oy", "oi"]:
                    chat_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                    status_atendimento = "bot"
                else:
                    chat_ref.set({"ultima_interacao": agora, "ultima_mensagem_por": "cliente_final"}, merge=True)
                    save_chat_history(phone_number, "user", message_text)
                    return

        # 6. TRANSFERÊNCIA MANUAL PARA ATENDIMENTO HUMANO
        gatilhos_humano = ["falar com atendente", "suporte humano", "atendente", "humano", "#suporte"]
        if any(g in msg_clean for g in gatilhos_humano):
            chat_ref.set({
                "status_atendimento": "humano",
                "ultima_mensagem_por": "cliente_final",
                "ultima_interacao": agora
            }, merge=True)
            send_whatsapp(
                phone_number,
                f"🔔 *Atendimento Transferido:* Encaminhamos para a nossa equipa. Se não houver resposta em {Config.TIMEOUT_HUMANO_MINUTOS} minutos, o assistente responderá automaticamente.",
                instance_name=central_instance
            )
            return

        # 7. RESPOSTA AUTOMÁTICA VIA GROQ (LLaMA 3.3 70B)
        chat_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
        
        # Guarda a nova mensagem enviada pelo utilizador
        save_chat_history(phone_number, "user", message_text)

        # Monta o histórico formatado para a Groq
        raw_history = get_chat_history(phone_number)[-10:]
        contents = []
        for msg in raw_history:
            if isinstance(msg, dict):
                role = "assistant" if msg.get('role') in ["assistant", "model", "atendente"] else "user"
                txt = msg.get('content') or msg.get('text') or ""
                if not txt and 'parts' in msg and isinstance(msg['parts'], list):
                    txt = " ".join([p.get('text', '') for p in msg['parts'] if isinstance(p, dict)])
                if txt:
                    contents.append({"role": role, "content": str(txt)})

        sys_instruction_central = """Você é o assistente comercial e de suporte oficial do Negobot Moz.
Responda sempre com cortesia, clareza e dinamismo em Português de Moçambique.
ATENÇÃO: Nunca ignore novas saudações (como 'Bom dia', 'Boa noite', 'Oy'). Retome a conversa de forma natural, prestativa e ativa, independentemente de despedidas anteriores."""

        # Chamada à API da Groq
        response_text = chamar_groq_rest(contents, system_prompt=sys_instruction_central)
        
        if response_text:
            save_chat_history(phone_number, "assistant", response_text)
            send_whatsapp(phone_number, response_text, instance_name=central_instance)
            chat_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

    except Exception as e:
        logger.error(f"Erro no process_central_flow para {phone_number_or_data}: {e}", exc_info=True)
