import re
import os
import time
import random
import logging
import threading
from datetime import datetime, timedelta, timezone
from firebase_admin import firestore
from config import Config
import extensions
from services.groq_service import chamar_groq_rest
from services.evolution_service import send_whatsapp
from services.trial_service import PENDING_STATUS, is_expired as trial_is_expired
from services.plan_service import entitlements_for_tenant
from services.media_service import (
    extrair_texto_pdf_url, 
    extrair_texto_excel_url
)

logger = logging.getLogger(__name__)

# Limite máximo de caracteres para a base extraída de documentos (proteção de tokens na Groq)
MAX_KNOWLEDGE_CHARS = 12000

# ------------------------------------------------------------------------------
# FUNÇÕES AUXILIARES ANTI-BLOQUEIO E SPINTAX
# ------------------------------------------------------------------------------
def processar_spintax(texto: str) -> str:
    """Converte variações {Opção 1|Opção 2} em texto aleatório único."""
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(texto)
        if not match:
            break
        opcoes = match.group(1).split('|')
        texto = texto[:match.start()] + random.choice(opcoes) + texto[match.end():]
    return texto

def processar_disparo_em_massa(instance_name: str, numeros: list, mensagem_base: str, delay_base: int = 7):
    """Executa o loop de disparo seguro em segundo plano."""
    sucessos = 0
    falhas = 0
    total = len(numeros)

    logger.info(f"🛡️ [DISPARO INICIADO] Instância: {instance_name} | Total: {total} contactos")

    for index, numero in enumerate(numeros, start=1):
        numero_limpo = re.sub(r'\D', '', str(numero))
        
        # Auto-correção para o formato de Moçambique se o utilizador não colocar o 258
        if len(numero_limpo) == 9 and numero_limpo.startswith(('84', '85', '86', '87')):
            numero_limpo = '258' + numero_limpo

        if not numero_limpo or len(numero_limpo) < 8:
            logger.warning(f"[{index}/{total}] ⚠️ Número inválido ignorado: {numero}")
            continue

        mensagem_variada = processar_spintax(mensagem_base)
        
        try:
            send_whatsapp(numero_limpo, mensagem_variada, instance_name=instance_name)
            sucessos += 1
            logger.info(f"[{index}/{total}] ✅ Enviado para: {numero_limpo}")
        except Exception as err:
            falhas += 1
            logger.error(f"[{index}/{total}] ❌ Falha ao enviar para {numero_limpo}: {err}")

        if index == total:
            break

        # Pausa por lote (a cada 12 envios, pausa entre 60 a 120 segundos)
        if index % 12 == 0:
            pausa_lote = random.uniform(60, 120)
            logger.info(f"☕ Pausa de segurança por lote ({index}/{total}). Aguardando {int(pausa_lote)}s...")
            time.sleep(pausa_lote)
        else:
            # Pausa dinâmica entre mensagens individuais (jitter)
            pausa = random.uniform(delay_base, delay_base + 6)
            time.sleep(pausa)

    logger.info(f"🏁 [DISPARO CONCLUÍDO] Sucessos: {sucessos} | Falhas: {falhas} | Total: {total}")

def contem_palavra_exata(texto, lista_palavras):
    """Verifica se alguma palavra da lista existe como palavra inteira no texto."""
    texto_lower = (texto or "").lower()
    for palavra in lista_palavras:
        pattern = r'(?:\b|^)' + re.escape(palavra.lower()) + r'(?:\b|$)'
        if re.search(pattern, texto_lower):
            return True
    return False

def checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
    """Verifica se o tempo limite de atendimento humano expirou."""
    if conversa_dados and conversa_dados.get("status_atendimento") == "humano":
        ultima_interacao = conversa_dados.get("ultima_interacao")
        
        if ultima_interacao:
            if hasattr(ultima_interacao, 'tzinfo') and ultima_interacao.tzinfo is None:
                ultima_interacao = ultima_interacao.replace(tzinfo=timezone.utc)
            
            timeout_min = getattr(Config, 'TIMEOUT_HUMANO_MINUTOS', 15)
            minutos_decorridos = (agora - ultima_interacao).total_seconds() / 60.0
            
            if minutos_decorridos >= timeout_min:
                conversa_ref.set({
                    "status_atendimento": "bot",
                    "ultima_interacao": agora
                }, merge=True)
                return True
    return False

# ------------------------------------------------------------------------------
# FLUXO PRINCIPAL DE PROCESSAMENTO
# ------------------------------------------------------------------------------
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
    try:
        if agora is None:
            agora = datetime.now(timezone.utc)

        # 1. TRATAMENTO DE PAYLOAD E DETECÇÃO DE GRUPOS
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
                if is_from_me is False:
                    is_from_me = bool(key.get('fromMe'))
            
            if not message_text:
                msg_obj = data_inner.get('message', {}) if isinstance(data_inner, dict) else {}
                message_text = msg_obj.get('conversation') or msg_obj.get('extendedTextMessage', {}).get('text') or ""

            if not document_message and isinstance(data_inner, dict):
                msg_inner = data_inner.get('message', {})
                document_message = (
                    msg_inner.get('documentMessage') or 
                    msg_inner.get('documentWithCaptionMessage', {}).get('message', {}).get('documentMessage')
                )

        # 🚫 BLOQUEIO RÍGIDO DE GRUPOS E TRANSMISSÕES
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
            return

        # 2. SANITIZAÇÃO DE DADOS
        nome_instancia_atual = str(nome_instancia_atual or "").strip()
        clean_user_phone = re.sub(r'\D', '', str_phone_raw.split('@')[0])
        message_text = str(message_text or "").strip()
        
        if not msg_clean or not isinstance(msg_clean, str):
            msg_clean = message_text.lower().strip()

        if not message_text and not document_message:
            return

        if not nome_instancia_atual or not clean_user_phone or clean_user_phone in ["None", "false", "true", ""]:
            return

        # Referências no Firestore
        client_doc_ref = extensions.db.collection('clientes_bot').document(nome_instancia_atual)
        conversa_ref = client_doc_ref.collection('conversas').document(clean_user_phone)
        historico_ref = conversa_ref.collection('historico')

        # 3. VERIFICAÇÃO DO ESTADO DO PLANO E EXPIRAÇÃO
        client_doc = client_doc_ref.get()
        default_rules = (
            "- Atenda os clientes finais com cortesia, agilidade e profissionalismo.\n"
            "- NUNCA diga que a loja não tem stock de forma genérica e NUNCA invente preços ou produtos.\n"
            "- Se o cliente perguntar por produtos, catálogo ou preços, responda:\n"
            "  'Seja bem-vindo(a)! 🛍️ Para garantir a disponibilidade exata em stock do produto desejado, encaminharei o seu pedido à nossa equipa de vendas. Por favor, escreva o produto que procura e responderemos em instantes!'"
        )

        if not client_doc.exists:
            dados_cliente = {
                "status_plano": "demonstracao",
                "status": "pending_connection",
                "trial_status": PENDING_STATUS,
                "trial_connection_confirmed": False,
                "instance_name": nome_instancia_atual,
                "diretrizes_corporativas": default_rules,
                "disparos_teste_usados": 0
            }
            client_doc_ref.set(dados_cliente, merge=True)
            base_conhecimento_docs = ""
        else:
            dados_cliente = client_doc.to_dict() or {}
            base_conhecimento_docs = dados_cliente.get("base_conhecimento_documentos", "")

        status_plano = dados_cliente.get("status_plano", "demonstracao")

        # Limite mensal de conversas: só conta uma conversa nova, não cada mensagem.
        if not is_from_me and not conversa_ref.get().exists:
            conversation_limit = entitlements_for_tenant(dados_cliente).get("conversation_limit")
            if conversation_limit:
                usage_key = agora.strftime("%Y-%m")
                usage_ref = client_doc_ref.collection("usage").document(usage_key)
                usage_doc = usage_ref.get()
                conversations_used = int((usage_doc.to_dict() or {}).get("conversations", 0)) if usage_doc.exists else 0
                if conversations_used >= int(conversation_limit):
                    send_whatsapp(
                        clean_user_phone,
                        f"⚠️ O limite de {int(conversation_limit):,} conversas deste mês foi atingido. Faz upgrade do plano para continuar a receber novos atendimentos.",
                        instance_name=nome_instancia_atual,
                    )
                    return
                usage_ref.set({"conversations": firestore.Increment(1), "month": usage_key, "updated_at": agora}, merge=True)

        if trial_is_expired(dados_cliente, agora):
            logger.warning(f"⚠️ Instância {nome_instancia_atual} com plano expirado. Atendimento suspenso.")
            if is_from_me or clean_user_phone == dados_cliente.get("telefone_proprietario"):
                send_whatsapp(
                    clean_user_phone,
                    "⚠️ *Aviso Negobot Moz:* O seu período de teste/plano expirou. Efetue o pagamento da mensalidade para reativar o assistente virtual.",
                    instance_name=nome_instancia_atual
                )
            return

        # ----------------------------------------------------------------------
        # 🎯 INTERCEPÇÃO DE COMANDOS DE DISPARO (#disparo, #broadcast, #ajuda_disparo)
        # ----------------------------------------------------------------------
        if msg_clean.startswith("#disparo") or msg_clean.startswith("#broadcast") or msg_clean == "#ajuda_disparo":
            admin_phones_env = os.getenv("ADMIN_PHONES", "")
            admin_list = [re.sub(r'\D', '', p) for p in admin_phones_env.split(",") if p]
            is_admin = clean_user_phone in admin_list

            # Comando de Ajuda
            if msg_clean == "#ajuda_disparo":
                ajuda_txt = (
                    "🛠️ *Comandos de Disparo em Massa Protegido*\n\n"
                    "• `#disparo 258841234567,258857654321 | {Olá|Oi} Sua Mensagem`\n"
                    "• `#ajuda_disparo` -> Mostra este painel de ajuda\n\n"
                    "💡 *Dica:* Use `{opção1|opção2}` na mensagem para variar o texto automaticamente!"
                )
                send_whatsapp(clean_user_phone, ajuda_txt, instance_name=nome_instancia_atual)
                return

            # Validação de Permissão de Plano (Se não for Admin)
            if not is_admin and status_plano not in ["premium", "demonstracao", "ativo"]:
                send_whatsapp(
                    clean_user_phone,
                    "❌ *Recurso Indisponível:* O envio de disparos em massa é exclusivo do *Plano Premium*.",
                    instance_name=nome_instancia_atual
                )
                return

            if not is_admin and status_plano == "demonstracao":
                disparos_usados = dados_cliente.get("disparos_teste_usados", 0)
                if disparos_usados >= 2:
                    send_whatsapp(
                        clean_user_phone,
                        "⚠️ *Limite de Teste Atingido:* No plano de demonstração são permitidos apenas 2 disparos. Assine o Plano Premium para disparar sem limites!",
                        instance_name=nome_instancia_atual
                    )
                    return

            # Extração de Números e Mensagem
            conteudo = message_text.replace("#disparo", "").replace("#broadcast", "").strip()
            if "|" not in conteudo:
                send_whatsapp(
                    clean_user_phone,
                    "❌ *Formato incorreto!* Envie no seguinte formato:\n\n`#disparo 258841234567,258859876543 | {Olá|Oi}! Sua mensagem promocional`",
                    instance_name=nome_instancia_atual
                )
                return

            partes = conteudo.split("|", 1)
            raw_nums = partes[0].split(",")
            mensagem_envio = partes[1].strip()

            numeros_validos = []
            for n in raw_nums:
                num_c = re.sub(r'\D', '', n)
                if len(num_c) == 9 and num_c.startswith(('84', '85', '86', '87')):
                    num_c = '258' + num_c
                if num_c:
                    numeros_validos.append(num_c)

            if not numeros_validos or not mensagem_envio:
                send_whatsapp(
                    clean_user_phone,
                    "❌ *Erro:* Nenhum número de destinatário válido ou mensagem vazia.",
                    instance_name=nome_instancia_atual
                )
                return

            # Incrementa contador de testes
            if not is_admin and status_plano == "demonstracao":
                client_doc_ref.set({"disparos_teste_usados": firestore.Increment(1)}, merge=True)

            # Inicia o disparo em segundo plano sem bloquear a rota
            thread_disparo = threading.Thread(
                target=processar_disparo_em_massa,
                args=(nome_instancia_atual, numeros_validos, mensagem_envio),
                kwargs={"delay_base": 7}
            )
            thread_disparo.daemon = True
            thread_disparo.start()

            confirmacao = (
                f"🛡️ *Disparo Protegido Iniciado!*\n\n"
                f"• *Destinatários:* {len(numeros_validos)}\n"
                f"• *Proteção Anti-Bloqueio:* Ativa (Intervalos dinâmicos e variação de texto)\n"
                f"• *Instância:* `{nome_instancia_atual}`"
            )
            send_whatsapp(clean_user_phone, confirmacao, instance_name=nome_instancia_atual)
            return

        # 4. MENSAGEM DO PRÓPRIO ATENDENTE HUMANO
        if is_from_me:
            conversa_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
            historico_ref.add({"role": "atendente", "text": message_text or "[Documento/Mídia enviada pelo atendente]", "timestamp": agora})
            return

        # 5. REGISTO IMEDIATO DA MENSAGEM DO CLIENTE NO FIRESTORE
        conversa_ref.set({"ultima_interacao": agora, "ultima_mensagem_por": "cliente_final"}, merge=True)
        texto_historico = message_text if message_text else "[Documento Enviado]"
        historico_ref.add({"role": "user", "text": texto_historico, "timestamp": agora})

        # 6. PROCESSAMENTO DE DOCUMENTOS (PDF / EXCEL) PARA BASE DE CONHECIMENTO
        if document_message and isinstance(document_message, dict):
            if status_plano == "basico":
                send_whatsapp(
                    clean_user_phone,
                    "⚠️ O *Plano Básico* não inclui o processamento automático de documentos PDF/Excel. Atualize para o *Plano Médio* ou *Premium* para treinar o assistente com ficheiros.",
                    instance_name=nome_instancia_atual
                )
                return

            media_url = document_message.get('mediaUrl') or document_message.get('url') or document_message.get('fileUrl')
            file_name = document_message.get('fileName', 'documento')
            file_extension = os.path.splitext(file_name)[1].lower()
            
            mimetype = document_message.get('mimetype', '')
            if not file_extension:
                if 'pdf' in mimetype: file_extension = '.pdf'
                elif 'sheet' in mimetype or 'excel' in mimetype: file_extension = '.xlsx'
                elif 'csv' in mimetype: file_extension = '.csv'

            if media_url and file_extension in ['.pdf', '.xlsx', '.xls', '.csv']:
                logger.info(f"📄 A processar documento ({file_name}) para a instância {nome_instancia_atual}...")
                send_whatsapp(clean_user_phone, "📄 A processar o documento da empresa para atualizar a base de conhecimento do assistente...", instance_name=nome_instancia_atual)
                
                texto_extraido = ""
                evolution_apikey = getattr(Config, 'EVOLUTION_GLOBAL_APIKEY', os.getenv("EVOLUTION_GLOBAL_APIKEY", ""))

                try:
                    if file_extension == '.pdf':
                        texto_extraido = extrair_texto_pdf_url(media_url, apikey=evolution_apikey)
                    elif file_extension in ['.xlsx', '.xls', '.csv']:
                        texto_extraido = extrair_texto_excel_url(media_url, apikey=evolution_apikey)
                except Exception as err_doc:
                    logger.error(f"Erro ao extrair texto do documento {file_name}: {err_doc}")

                if texto_extraido:
                    client_doc_ref.set({
                        "base_conhecimento_documentos": texto_extraido,
                        "ultimo_documento": file_name,
                        "atualizado_em": agora
                    }, merge=True)

                    sucesso_msg = f"✅ Documento '{file_name}' processado e integrado com sucesso! O assistente já está treinado com as novas informações da empresa."
                    send_whatsapp(clean_user_phone, sucesso_msg, instance_name=nome_instancia_atual)
                    logger.info(f"✅ Base de conhecimento atualizada via documento para {nome_instancia_atual}")
                    return
                else:
                    erro_msg = "❌ Não foi possível extrair o texto deste documento. Certifique-se de que o ficheiro é válido e legível."
                    send_whatsapp(clean_user_phone, erro_msg, instance_name=nome_instancia_atual)
                    return

        # 7. VERIFICAÇÃO DE MODO HUMANO E TIMEOUT
        conversa_doc = conversa_ref.get()
        conversa_dados = conversa_doc.to_dict() if conversa_doc.exists else {}
        status_atendimento = conversa_dados.get("status_atendimento", "bot")

        gatilhos_reset = ["/bot", "/reset", "voltar para bot", "chamar bot", "modo bot"]
        tem_gatilho_reset = contem_palavra_exata(msg_clean, gatilhos_reset)

        if status_atendimento == "humano":
            if tem_gatilho_reset:
                logger.info(f"🔄 Cliente {clean_user_phone} resetou o atendimento para modo bot.")
                conversa_ref.set({"status_atendimento": "bot"}, merge=True)
                status_atendimento = "bot"
            elif checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
                logger.info(f"⏳ Tempo esgotado. O bot assumiu o atendimento de {clean_user_phone}.")
                status_atendimento = "bot"
            else:
                return

        # 8. PEDIDO EXPLÍCITO DE ATENDIMENTO HUMANO
        gatilhos_humano = [
            "falar com atendente", "atendente humano", "falar com humano", 
            "suporte humano", "falar com operador", "quero atendente", 
            "falar com pessoa", "passar para humano"
        ]
        if contem_palavra_exata(msg_clean, gatilhos_humano):
            timeout_min = getattr(Config, 'TIMEOUT_HUMANO_MINUTOS', 15)
            conversa_ref.set({
                "status_atendimento": "humano",
                "ultima_mensagem_por": "cliente_final",
                "ultima_interacao": agora
            }, merge=True)
            send_whatsapp(
                clean_user_phone, 
                f"🔔 *Atendimento Transferido:* O seu pedido foi encaminhado para a nossa equipa humana. (Se não houver resposta dentro de {timeout_min} minutos, o assistente virtual retomará a conversa).", 
                instance_name=nome_instancia_atual
            )
            return

        # 9. PREPARAÇÃO DO HISTÓRICO PARA A GROQ
        docs_h = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
        lista_m = [d.to_dict() for d in docs_h]
        lista_m.reverse()

        contents = []
        for m in lista_m:
            role_g = "assistant" if m.get('role') in ["assistant", "model", "atendente"] else "user"
            txt = m.get('text') or m.get('content') or ""
            if txt:
                contents.append({"role": role_g, "content": str(txt)})

        diretrizes = dados_cliente.get("diretrizes_corporativas") or default_rules
        socials = dados_cliente.get("redes_sociais") if isinstance(dados_cliente.get("redes_sociais"), dict) else {}
        profile_lines = [
            f"Nome da empresa: {dados_cliente.get('empresa_nome', '')}",
            f"Nicho: {dados_cliente.get('nicho', '')}",
            f"Email corporativo: {dados_cliente.get('email_corporativo', '')}",
        ]
        for social_key, social_label in (("facebook", "Facebook"), ("instagram", "Instagram"), ("twitter_x", "X/Twitter"), ("tiktok", "TikTok"), ("telegram", "Telegram"), ("linkedin", "LinkedIn")):
            if socials.get(social_key):
                profile_lines.append(f"{social_label}: {socials[social_key]}")
        bloco_perfil_empresa = "\n\nPERFIL OFICIAL DA EMPRESA:\n" + "\n".join(profile_lines)
        
        bloco_conhecimento_extra = ""
        if base_conhecimento_docs:
            doc_text_clean = base_conhecimento_docs[:MAX_KNOWLEDGE_CHARS]
            bloco_conhecimento_extra = f"\n\nDOCUMENTAÇÃO E DADOS DA EMPRESA (EXTRAÍDOS DE PDF/EXCEL):\n{doc_text_clean}\n"

        sys_instruction = f"""Você é o assistente virtual oficial de atendimento desta empresa.
Português de Moçambique, tom profissional, atencioso e conciso.

DIRETRIZES DA EMPRESA:
{diretrizes}
{bloco_perfil_empresa}
{bloco_conhecimento_extra}
REGRA DE ATENDIMENTO:
- Responda às dúvidas do cliente com clareza utilizando os dados oficiais fornecidos acima.
- Quando perguntarem pelas redes sociais, divulgue apenas os links presentes no PERFIL OFICIAL DA EMPRESA.
- NUNCA tente transferir o atendimento e NUNCA invente informações que não estejam presentes nos dados da empresa."""

        # 10. RESPOSTA DA GROQ COM FALLBACK DE SEGURANÇA
        response_text = None
        try:
            response_text = chamar_groq_rest(contents, system_prompt=sys_instruction)
        except Exception as err_groq:
            logger.error(f"Erro ao chamar Groq: {err_groq}")

        if not response_text:
            response_text = "Olá! 👋 O nosso sistema está a processar a sua mensagem. Em que posso ser útil neste momento?"

        response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
        
        send_whatsapp(clean_user_phone, response_text, instance_name=nome_instancia_atual)
        historico_ref.add({"role": "assistant", "text": response_text, "timestamp": agora})
        conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

    except Exception as e:
        logger.error(f"Erro no process_client_flow para {nome_instancia_atual} / {phone_number}: {e}", exc_info=True)
