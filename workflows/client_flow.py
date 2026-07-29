import re
import requests
import logging
from datetime import datetime, timedelta, timezone
from firebase_admin import firestore
from config import Config
import extensions
from services.groq_service import chamar_groq_rest
from services.evolution_service import send_whatsapp
from services.media_service import (
    extrair_texto_pdf_url, 
    extrair_texto_excel_url, 
    criar_prompt_profissional_groq, 
    gerar_url_imagem_pollinations
)

logger = logging.getLogger(__name__)

def checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
    """Verifica se o tempo limite (2 minutos) de espera por atendimento humano expirou."""
    if conversa_dados and conversa_dados.get("status_atendimento") == "humano":
        ultima_interacao = conversa_dados.get("ultima_interacao")
        
        if ultima_interacao:
            if hasattr(ultima_interacao, 'tzinfo') and ultima_interacao.tzinfo is None:
                ultima_interacao = ultima_interacao.replace(tzinfo=timezone.utc)
            
            # Ajustado para 2 minutos como padrão
            timeout_min = getattr(Config, 'TIMEOUT_HUMANO_MINUTOS', 2)
            minutos_decorridos = (agora - ultima_interacao).total_seconds() / 60.0
            
            if minutos_decorridos >= timeout_min:
                conversa_ref.set({
                    "status_atendimento": "bot",
                    "ultima_interacao": agora
                }, merge=True)
                return True
    return False

def process_client_flow(
    nome_instancia_atual, 
    phone_number="", 
    message_text="", 
    msg_clean="", 
    document_message=None, 
    is_from_me=False, 
    agora=None,
    **kwargs
):
    """
    Workflow dos bots dos clientes (tenants) da Negobot Moz.
    Garante sanitização estrita de tipos, bloqueio absoluto de grupos e envio isolado.
    """
    try:
        if agora is None:
            agora = datetime.now(timezone.utc)

        # 1. TRATAMENTO INTELIGENTE DE PAYLOAD E DETEÇÃO RIGOROSA DE GRUPOS
        remote_jid = ""
        has_participant = False

        if isinstance(nome_instancia_atual, dict):
            payload_data = nome_instancia_atual
            nome_instancia_atual = payload_data.get('instance') or payload_data.get('instanceId') or ''
            
            data_inner = payload_data.get('data', {}) if isinstance(payload_data.get('data'), dict) else payload_data
            key = data_inner.get('key', {}) if isinstance(data_inner, dict) else {}
            
            if isinstance(key, dict):
                remote_jid = str(key.get('remoteJid') or '')
                has_participant = bool(key.get('participant'))
                if not phone_number:
                    phone_number = remote_jid or key.get('participant') or key.get('id') or ''
            
            if not message_text:
                msg_obj = data_inner.get('message', {}) if isinstance(data_inner, dict) else {}
                message_text = msg_obj.get('conversation') or msg_obj.get('extendedTextMessage', {}).get('text') or ""

        # 🚫 TRAVA DE SEGURANÇA MÁXIMA PARA GRUPOS E TRANSMISSÕES
        str_phone_raw = str(phone_number or "").strip()
        str_remote_jid = str(remote_jid or "").strip()

        if (
            "@g.us" in str_phone_raw 
            or "@g.us" in str_remote_jid 
            or "status@broadcast" in str_phone_raw 
            or "status@broadcast" in str_remote_jid 
            or has_participant
            or kwargs.get('isGroup')
        ):
            logger.info(f"🚫 Mensagem de grupo/transmissão ignorada no process_client_flow: phone='{str_phone_raw}', rjid='{str_remote_jid}'")
            return

        # 2. SANITIZAÇÃO RÍGIDA DE TIPOS
        nome_instancia_atual = str(nome_instancia_atual or "").strip()
        clean_user_phone = re.sub(r'\D', '', str_phone_raw.split('@')[0])
        message_text = str(message_text or "").strip()
        
        if not isinstance(msg_clean, str) or not msg_clean:
            msg_clean = message_text.lower().strip()
        else:
            msg_clean = msg_clean.lower().strip()

        if not message_text and not document_message:
            return

        if not nome_instancia_atual or not clean_user_phone or clean_user_phone in ["None", "false", "true", ""]:
            logger.warning(f"Ignorando execução com parâmetros inválidos: instancia='{nome_instancia_atual}', phone='{clean_user_phone}'")
            return

        # Referências no Firestore usando o número limpo
        client_doc_ref = extensions.db.collection('clientes_bot').document(nome_instancia_atual)
        conversa_ref = client_doc_ref.collection('conversas').document(clean_user_phone)
        historico_ref = conversa_ref.collection('historico')

        # 3. Registo de mensagem enviada pelo próprio atendente humano da empresa
        if is_from_me:
            conversa_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
            historico_ref.add({"role": "atendente", "text": message_text, "timestamp": agora})
            return

        # 4. Regra Comercial Padrão (Para clientes sem catálogo configurado)
        default_rules = (
            "- Atenda os clientes finais com cortesia, agilidade e profissionalismo.\n"
            "- NUNCA diga que a loja não tem stock de forma genérica e NUNCA invente preços ou produtos.\n"
            "- Se o cliente perguntar por produtos, catálogo, preços ou disponibilidade, responda educadamente:\n"
            "  'Seja bem-vindo(a)! 🛍️ Para garantir a disponibilidade exata em stock do produto desejado para entrega imediata, vou encaminhar o seu pedido à nossa equipa de vendas. Por favor, escreva aqui qual é o produto ou serviço que procura e um dos nossos atendentes confirmará os detalhes consigo em instantes!'"
        )

        client_doc = client_doc_ref.get()
        if not client_doc.exists:
            dados_cliente = {
                "status_plano": "demonstracao", 
                "data_ativacao": agora, 
                "data_expiracao": agora + timedelta(days=2), 
                "diretrizes_corporativas": default_rules
            }
            client_doc_ref.set(dados_cliente)
        else:
            dados_cliente = client_doc.to_dict() or {}

        # 5. Verificação de expiração do plano de demonstração
        status_plano = dados_cliente.get("status_plano", "demonstracao")
        data_expiracao = dados_cliente.get("data_expiracao")
        if data_expiracao and hasattr(data_expiracao, 'tzinfo') and data_expiracao.tzinfo is None:
            data_expiracao = data_expiracao.replace(tzinfo=timezone.utc)

        if status_plano == "demonstracao" and data_expiracao and agora > data_expiracao:
            send_whatsapp(clean_user_phone, "⚠️ O período de teste deste assistente virtual expirou.", instance_name=nome_instancia_atual)
            return

        # 6. Comando Especial: /criar-arte
        if msg_clean.startswith("/criar-arte"):
            pedido = message_text.replace("/criar-arte", "").strip()
            if not pedido:
                send_whatsapp(clean_user_phone, "✍️ Exemplo: `/criar-arte Banner de oferta de promoção`", instance_name=nome_instancia_atual)
                return
            send_whatsapp(clean_user_phone, "🎨 A criar a sua imagem...", instance_name=nome_instancia_atual)
            prompt_ingles = criar_prompt_profissional_groq(pedido)
            link_imagem = gerar_url_imagem_pollinations(prompt_ingles)
            
            payload = {
                "number": clean_user_phone, 
                "caption": f"✨ *Arte Gerada!*\n🎯 _{pedido}_", 
                "media": link_imagem, 
                "mediatype": "image", 
                "fileName": "arte.jpg"
            }
            requests.post(
                f"{Config.EVOLUTION_API_URL}/message/sendMedia/{nome_instancia_atual}", 
                headers={"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}, 
                json=payload, 
                timeout=25
            )
            return

        # 7. Leitura Automática de Excel e PDF
        if document_message and clean_user_phone in nome_instancia_atual:
            url_doc = document_message.get('url')
            file_name = str(document_message.get('fileName', '')).lower()

            if file_name.endswith(('.xlsx', '.xls')):
                send_whatsapp(clean_user_phone, "📊 A processar documento Excel...", instance_name=nome_instancia_atual)
                texto_excel = extrair_texto_excel_url(url_doc)
                if texto_excel:
                    novas_diretrizes = f"{dados_cliente.get('diretrizes_corporativas', '')}\n\n=== EXCEL ===\n{texto_excel}"
                    client_doc_ref.set({"diretrizes_corporativas": novas_diretrizes}, merge=True)
                    send_whatsapp(clean_user_phone, "✅ *Excel Carregado!* Tabela assimilada com sucesso.", instance_name=nome_instancia_atual)
                return

            elif file_name.endswith('.pdf') or not file_name:
                send_whatsapp(clean_user_phone, "📄 A ler arquivo PDF...", instance_name=nome_instancia_atual)
                texto_pdf = extrair_texto_pdf_url(url_doc)
                if texto_pdf:
                    novas_diretrizes = f"{dados_cliente.get('diretrizes_corporativas', '')}\n\n=== PDF ===\n{texto_pdf}"
                    client_doc_ref.set({"diretrizes_corporativas": novas_diretrizes}, merge=True)
                    send_whatsapp(clean_user_phone, "✅ *PDF Carregado!* Conteúdo incorporado às diretrizes do bot.", instance_name=nome_instancia_atual)
                return

        # 8. VERIFICAÇÃO E DESTRAVAMENTO DO MODO DE ATENDIMENTO HUMANO (TIMEOUT DE 2 MINUTOS)
        conversa_doc = conversa_ref.get()
        conversa_dados = conversa_doc.to_dict() if conversa_doc.exists else {}
        status_atendimento = conversa_dados.get("status_atendimento", "bot")

        gatilhos_reset = ["/bot", "/reset", "continuar", "bot", "bom dia", "boa tarde", "boa noite", "ola", "olá", "oy", "oi"]
        tem_gatilho_reset = any(g in msg_clean for g in gatilhos_reset)

        if status_atendimento == "humano":
            if tem_gatilho_reset:
                logger.info(f"🔄 Cliente {clean_user_phone} enviou saudação ou comando de reset. Retornando para modo bot.")
                conversa_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                status_atendimento = "bot"
            elif checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
                logger.info(f"⏳ Passaram 2 minutos sem resposta humana para {clean_user_phone}. O bot retomou o atendimento automaticamente.")
                status_atendimento = "bot"
            else:
                # Se ainda não passaram 2 minutos e não há gatilho de reset, ignora para o humano responder
                historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                return

        # 9. GATILHOS EXCLUSIVOS DE SOLICITAÇÃO DE ATENDENTE HUMANO
        gatilhos_humano = [
            "falar com atendente", "atendente humano", "falar com humano", 
            "suporte humano", "falar com operador", "quero atendente", 
            "falar com pessoa", "passar para humano", "atendente"
        ]
        if any(g in msg_clean for g in gatilhos_humano):
            timeout_min = getattr(Config, 'TIMEOUT_HUMANO_MINUTOS', 2)
            conversa_ref.set({
                "status_atendimento": "humano",
                "ultima_mensagem_por": "cliente_final",
                "ultima_interacao": agora
            }, merge=True)
            historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
            send_whatsapp(
                clean_user_phone, 
                f"🔔 *Atendimento Transferido:* O seu pedido foi encaminhado para a equipa humana. (Se não houver resposta dentro de {timeout_min} minutos, o assistente virtual voltará a responder-lhe automaticamente).", 
                instance_name=nome_instancia_atual
            )
            return

        # 10. Formatação do Histórico para a Groq (LLaMA 3.3)
        docs_h = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
        lista_m = [d.to_dict() for d in docs_h]
        lista_m.reverse()

        contents = []
        for m in lista_m:
            role_g = "assistant" if m.get('role') in ["assistant", "model", "atendente"] else "user"
            txt = m.get('text') or m.get('content') or ""
            if txt:
                contents.append({"role": role_g, "content": str(txt)})

        if message_text:
            contents.append({"role": "user", "content": message_text})

        diretrizes = dados_cliente.get("diretrizes_corporativas") or default_rules
        sys_instruction = f"""Você é o assistente virtual oficial de atendimento desta empresa.
Português de Moçambique, tom profissional, atencioso e conciso.

DIRETRIZES DA EMPRESA:
{diretrizes}

REGRA DE ATENDIMENTO:
- Responda às dúvidas do cliente com base nas diretrizes da empresa.
- NUNCA tente transferir o atendimento nem mencione mudar de status."""

        # 11. Resposta Inteligente via Groq
        response_text = chamar_groq_rest(contents, system_prompt=sys_instruction)
        historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})

        if response_text:
            response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
            
            send_whatsapp(clean_user_phone, response_text, instance_name=nome_instancia_atual)
            historico_ref.add({"role": "assistant", "text": response_text, "timestamp": agora})
            conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

    except Exception as e:
        logger.error(f"Erro no process_client_flow para {nome_instancia_atual} / {phone_number}: {e}", exc_info=True)
