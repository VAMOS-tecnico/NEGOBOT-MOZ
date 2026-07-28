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

def process_client_flow(
    nome_instancia_atual, 
    phone_number, 
    message_text="", 
    msg_clean="", 
    document_message=None, 
    is_from_me=False, 
    agora=None,
    **kwargs
):
    """
    Workflow dos bots dos clientes (tenants) da Negobot Moz.
    Gerencia o atendimento aos clientes finais, consulta diretrizes e absorve PDFs/Excels.
    """
    try:
        if agora is None:
            agora = datetime.now(timezone.utc)

        if not phone_number:
            return

        client_doc_ref = extensions.db.collection('clientes_bot').document(str(nome_instancia_atual))
        conversa_ref = client_doc_ref.collection('conversas').document(str(phone_number))
        historico_ref = conversa_ref.collection('historico')

        # 1. Registo de mensagem enviada pelo próprio atendente humano da empresa
        if is_from_me:
            conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
            historico_ref.add({"role": "atendente", "text": message_text, "timestamp": agora})
            return

        # 2. Regra Comercial Padrão (Sem catálogo cadastrado ainda)
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

        # 3. Verificação de expiração do plano de demonstração
        status_plano = dados_cliente.get("status_plano", "demonstracao")
        data_expiracao = dados_cliente.get("data_expiracao")
        if data_expiracao and data_expiracao.tzinfo is None:
            data_expiracao = data_expiracao.replace(tzinfo=timezone.utc)

        if status_plano == "demonstracao" and data_expiracao and agora > data_expiracao:
            send_whatsapp(phone_number, "⚠️ O período de teste deste assistente virtual expirou.", instance_name=nome_instancia_atual)
            return

        # 4. Comando Especial: /criar-arte
        if msg_clean.startswith("/criar-arte"):
            pedido = message_text.replace("/criar-arte", "").strip()
            if not pedido:
                send_whatsapp(phone_number, "✍️ Exemplo: `/criar-arte Banner de oferta de promoção`", instance_name=nome_instancia_atual)
                return
            send_whatsapp(phone_number, "🎨 A criar a sua imagem...", instance_name=nome_instancia_atual)
            prompt_ingles = criar_prompt_profissional_groq(pedido)
            link_imagem = gerar_url_imagem_pollinations(prompt_ingles)
            
            payload = {
                "number": str(phone_number), 
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

        # 5. Leitura Automática de Excel e PDF enviados para a instância
        if document_message and str(phone_number).split('@')[0] in str(nome_instancia_atual):
            url_doc = document_message.get('url')
            file_name = document_message.get('fileName', '').lower()

            if file_name.endswith(('.xlsx', '.xls')):
                send_whatsapp(phone_number, "📊 A processar documento Excel...", instance_name=nome_instancia_atual)
                texto_excel = extrair_texto_excel_url(url_doc)
                if texto_excel:
                    novas_diretrizes = f"{dados_cliente.get('diretrizes_corporativas', '')}\n\n=== EXCEL ===\n{texto_excel}"
                    client_doc_ref.set({"diretrizes_corporativas": novas_diretrizes}, merge=True)
                    send_whatsapp(phone_number, "✅ *Excel Carregado!* Tabela assimilada com sucesso.", instance_name=nome_instancia_atual)
                return

            elif file_name.endswith('.pdf') or not file_name:
                send_whatsapp(phone_number, "📄 A ler arquivo PDF...", instance_name=nome_instancia_atual)
                texto_pdf = extrair_texto_pdf_url(url_doc)
                if texto_pdf:
                    novas_diretrizes = f"{dados_cliente.get('diretrizes_corporativas', '')}\n\n=== PDF ===\n{texto_pdf}"
                    client_doc_ref.set({"diretrizes_corporativas": novas_diretrizes}, merge=True)
                    send_whatsapp(phone_number, "✅ *PDF Carregado!* Conteúdo incorporado às diretrizes do bot.", instance_name=nome_instancia_atual)
                return

        # 6. Verificação do modo de Atendimento Humano
        conversa_doc = conversa_ref.get()
        conversa_dados = conversa_doc.to_dict() if conversa_doc.exists else {}
        status_atendimento = conversa_dados.get("status_atendimento", "bot")

        if status_atendimento == "humano":
            if checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
                status_atendimento = "bot"
            else:
                if msg_clean in ["/bot", "/reset", "continuar", "bot", "bom dia", "boa tarde", "boa noite", "ola", "olá", "oy", "oi"]:
                    conversa_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                    status_atendimento = "bot"
                else:
                    conversa_ref.set({"ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                    historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                    return

        # 7. Gatilhos de transferência para Atendente Humano
        gatilhos_humano = ["falar com atendente", "suporte humano", "atendente", "humano", "#suporte"]
        if any(g in msg_clean for g in gatilhos_humano):
            conversa_ref.set({
                "status_atendimento": "humano",
                "ultima_mensagem_por": "cliente_final",
                "ultima_interacao": agora
            }, merge=True)
            historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
            send_whatsapp(
                phone_number, 
                f"🔔 *Atendimento Transferido:* A mensagem foi enviada para o nosso operador. Se não houver resposta em {Config.TIMEOUT_HUMANO_MINUTOS} minutos, o assistente retomará o atendimento.", 
                instance_name=nome_instancia_atual
            )
            return

        # 8. Recuperação e Formatação do Histórico para a Groq (OpenAI Schema)
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
            contents.append({"role": "user", "content": str(message_text)})

        diretrizes = dados_cliente.get("diretrizes_corporativas") or default_rules
        sys_instruction = f"""Você é o assistente virtual oficial de atendimento desta empresa.
Português de Moçambique, tom profissional, atencioso e conciso.

DIRETRIZES DA EMPRESA:
{diretrizes}

REGRA DE REATIVAÇÃO E FLUXO:
- Nunca ignore novas saudações (como 'Bom dia', 'Boa tarde', 'Boa noite', 'Olá', 'Oi', 'Oy'). Retome a conversa de forma ativa.
- NUNCA use a tag [TRANSICAO_HUMANO] em saudações simples.
- Apenas inclua a tag [TRANSICAO_HUMANO] se o cliente exigir expressamente um atendente humano e você não tiver a resposta."""

        # 9. Geração da Resposta na Groq
        response_text = chamar_groq_rest(contents, system_prompt=sys_instruction)
        historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})

        e_saudacao = any(s in msg_clean for s in ["bom dia", "boa tarde", "boa noite", "olá", "ola", "oi", "oy"])
        
        if response_text and "[TRANSICAO_HUMANO]" in response_text and not e_saudacao:
            response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
            conversa_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
            
            if response_text:
                send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
            else:
                send_whatsapp(phone_number, "🔔 *Atendimento Transferido:* A sua mensagem foi encaminhada para a equipa humana. Aguarde por favor.", instance_name=nome_instancia_atual)
            
            historico_ref.add({"role": "assistant", "text": response_text, "timestamp": agora})
            return

        if response_text:
            response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
            send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
            historico_ref.add({"role": "assistant", "text": response_text, "timestamp": agora})
            conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

    except Exception as e:
        logger.error(f"Erro no process_client_flow para {nome_instancia_atual} / {phone_number}: {e}", exc_info=True)
