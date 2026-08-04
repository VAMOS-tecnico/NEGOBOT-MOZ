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
    send_media, 
    criar_e_configurar_instancia_automatica, 
    gerar_e_enviar_qrcode_central
)
from services.payment_service import validar_e_ativar_pagamento_mpesa
from services.image_generator_service import gerar_imagem_publicitaria

logger = logging.getLogger(__name__)


def checar_timeout_atendimento_humano(conversa_ref, conversa_dados: dict, agora: datetime) -> bool:
    """
    Verifica se o tempo limite de espera por atendimento humano expirou.
    Retorna True se o timeout ocorreu e o atendimento voltou ao bot, caso contrário False.
    """
    if conversa_dados and conversa_dados.get("status_atendimento") == "humano":
        ultima_interacao = conversa_dados.get("ultima_interacao")
        ultima_msg_por = conversa_dados.get("ultima_mensagem_por")
        
        if ultima_msg_por == "cliente_final" and ultima_interacao:
            if ultima_interacao.tzinfo is None:
                ultima_interacao = ultima_interacao.replace(tzinfo=timezone.utc)
            
            timeout_min = getattr(Config, 'TIMEOUT_HUMANO_MINUTOS', 15)
            minutos_decorridos = (agora - ultima_interacao).total_seconds() / 60.0
            
            if minutos_decorridos >= timeout_min:
                conversa_ref.set({
                    "status_atendimento": "bot",
                    "ultima_interacao": agora
                }, merge=True)
                logger.info(f"Timeout humano atingido ({minutos_decorridos:.1f} min). Bot reassumiu.")
                return True
    return False


def process_central_flow(phone_number_or_data=None, message_text: str = "", msg_clean: str = "", is_from_me: bool = False, agora: datetime = None, data: dict = None, **kwargs):
    """
    Workflow central do Negobot Moz focado na apresentação, conversão, 
    validação de pagamentos M-Pesa, geração de artes publicitárias e atendimento a clientes.
    """
    try:
        if agora is None:
            agora = datetime.now(timezone.utc)

        # Compatibilidade de payload
        payload = data if data is not None else phone_number_or_data

        # 1. Extração do identificador da conversa (JID)
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

        # 🚫 TRAVA DE SEGURANÇA MÁXIMA: Ignora grupos de WhatsApp (@g.us)
        if "@g.us" in raw_jid_str or (isinstance(payload, dict) and payload.get('data', {}).get('key', {}).get('participant')):
            logger.info(f"🚫 Mensagem de grupo ignorada: {raw_jid_str}")
            return

        # Sanitização do número individual do cliente (ex: 25884xxxxxxx)
        clean_phone = re.sub(r'\D', '', raw_jid_str.split('@')[0])
        if not clean_phone:
            logger.warning("Número de telefone inválido ou ausente no process_central_flow.")
            return

        central_instance = getattr(Config, 'EVOLUTION_INSTANCE_NAME', 'central')

        # Extração do texto caso venha do payload
        if not message_text and isinstance(payload, dict):
            data_payload = payload.get('data', {}) if isinstance(payload.get('data'), dict) else payload
            msg_obj = data_payload.get('message', {}) if isinstance(data_payload, dict) else {}
            message_text = msg_obj.get('conversation') or msg_obj.get('extendedTextMessage', {}).get('text') or ""

        if not isinstance(msg_clean, str) or not msg_clean:
            msg_clean = message_text.lower().strip()
        else:
            msg_clean = msg_clean.lower().strip()

        # ⚠️ Se o atendente responder manualmente via interface/WhatsApp, assume o modo "humano"
        if is_from_me:
            chat_ref = extensions.db.collection('chats').document(clean_phone)
            chat_ref.set({
                "status_atendimento": "humano",
                "ultima_mensagem_por": "atendente", 
                "ultima_interacao": agora
            }, merge=True)
            return

        # 💳 1. VALIDAÇÃO DE COMPROVATIVO M-PESA ENVIADO
        eh_comprovativo_mpesa = (
            msg_clean.startswith('#pago') 
            or msg_clean.startswith('#comprovativo')
            or "transferiste" in msg_clean 
            or "confirmado" in msg_clean
            or (bool(re.search(r'\b(3g|4g|5g|[a-z0-9]{10})\b', message_text.lower())) and "m-pesa" in message_text.lower())
        )

        if eh_comprovativo_mpesa:
            tenant_id = f"cliente_{clean_phone}"
            resposta_pagamento = validar_e_ativar_pagamento_mpesa(
                tenant_id=tenant_id,
                client_phone=clean_phone,
                message_text=message_text
            )
            if any(termo in resposta_pagamento for termo in ["PAGAMENTO CONFIRMADO", "Aguarde", "Insuficiente", "Já Utilizado", "Não Identificado"]):
                send_whatsapp(clean_phone, resposta_pagamento, instance_name=central_instance)
                return

        # 💳 2. INTERCEÇÃO DETERMINÍSTICA: DÚVIDAS DE COMO PAGAR (EVITA ALUCINAÇÃO DA IA)
        palavras_duvida_pagamento = [
            "como pago", "como pagar", "fazer o pagamento", "fazer pagamento", 
            "dados de pagamento", "dados para pagamento", "qual e o mpesa", 
            "qual e o m-pesa", "numero do mpesa", "numero de mpesa", 
            "onde pago", "onde transferir", "metodo de pagamento", "metodos de pagamento"
        ]
        
        eh_duvida_pagamento = any(termo in msg_clean for termo in palavras_duvida_pagamento)

        if eh_duvida_pagamento:
            resposta_instrucao_pagamento = (
                "💳 *Como efetuar o pagamento do Negobot Moz:*\n\n"
                "1️⃣ Faça a transferência do valor do plano escolhido via **M-Pesa** para o número oficial:\n"
                "📱 *855000929* (Negobot Moz)\n\n"
                "2️⃣ Cole aqui no chat a mensagem/SMS de confirmação recebida do M-Pesa (ou envie com **#pago** no início).\n\n"
                "⚡ A sua conta e plano serão ativados automaticamente assim que o comprovativo for enviado!"
            )
            save_chat_history(clean_phone, "user", message_text)
            save_chat_history(clean_phone, "assistant", resposta_instrucao_pagamento)
            send_whatsapp(clean_phone, resposta_instrucao_pagamento, instance_name=central_instance)
            return

        # 🎨 3. GERAÇÃO AUTOMÁTICA DE IMAGENS / ARTES PUBLICITÁRIAS
        gatilhos_imagem = ["#imagem", "gerar imagem", "cria uma arte", "criar imagem", "faz um cartaz", "gerar arte", "criar cartaz"]
        if any(termo in msg_clean for termo in gatilhos_imagem):
            send_whatsapp(clean_phone, "🎨 *A processar e a gerar a sua arte publicitária...* Por favor, aguarde alguns segundos. 🚀", instance_name=central_instance)
            
            url_imagem = gerar_imagem_publicitaria(message_text)
            if url_imagem:
                send_media(
                    phone_number=clean_phone,
                    media_url=url_imagem,
                    caption="✨ *Aqui está a sua arte publicitária criada pelo Negobot Moz!*",
                    instance_name=central_instance
                )
                save_chat_history(clean_phone, "user", message_text)
                save_chat_history(clean_phone, "assistant", "[Arte publicitária gerada e enviada]")
            else:
                send_whatsapp(clean_phone, "❌ *Não foi possível gerar a imagem no momento.* Tente novamente detalhando melhor o seu pedido.", instance_name=central_instance)
            return

        # 🛡️ FILTRO DE SEGURANÇA: Links de redes sociais sem texto complementar
        if ("youtube.com" in msg_clean or "youtu.be" in msg_clean or "tiktok.com" in msg_clean) and len(msg_clean.split()) <= 2:
            send_whatsapp(
                clean_phone,
                "Olá! 👋 Sou o assistente oficial do **Negobot Moz**. Automatizamos o WhatsApp de empresas e negócios em Moçambique.\n\nEscreva **TESTE** para experimentar a nossa plataforma grátis por 2 dias!",
                instance_name=central_instance
            )
            return

        # 4. Consulta de estado no Firestore
        chat_ref = extensions.db.collection('chats').document(clean_phone)
        chat_doc = chat_ref.get()
        chat_dados = chat_doc.to_dict() if chat_doc.exists else {}

        cliente_doc_ref = extensions.db.collection('clientes').document(clean_phone)
        cliente_doc = cliente_doc_ref.get()
        cliente_data = cliente_doc.to_dict() if cliente_doc.exists else {}
        status_cliente = cliente_data.get('status', 'prospect')

        if not cliente_doc.exists:
            cliente_doc_ref.set({
                "phone_number": clean_phone,
                "data_registro": agora,
                "status": "prospect"
            }, merge=True)

        # 5. Comando explícito de regeração de QR Code (#qrcode)
        if msg_clean == "#qrcode":
            send_whatsapp(clean_phone, "🔄 *A gerar o seu novo QR Code do Negobot Moz...* Por favor, aguarde alguns segundos.", instance_name=central_instance)
            criar_e_configurar_instancia_automatica(clean_phone)
            time.sleep(2)
            gerar_e_enviar_qrcode_central(clean_phone)
            return

        # 6. Gatilhos de Teste Grátis
        gatilhos_teste = [r'\bteste\b', r'\btestar\b', r'quero o bot', r'\bcomeçar\b', r'criar bot', r'\bdemo\b']
        if any(re.search(pattern, msg_clean) for pattern in gatilhos_teste) and not eh_duvida_pagamento:
            send_whatsapp(clean_phone, "⏳ *A preparar o seu teste grátis de 2 dias do Negobot Moz...* 🚀", instance_name=central_instance)
            
            cliente_doc_ref.set({
                "phone_number": clean_phone,
                "trial_start": agora,
                "status": "trial"
            }, merge=True)

            tenant_id = f"cliente_{clean_phone}"
            extensions.db.collection('clientes_bot').document(tenant_id).set({
                "status_plano": "demonstracao", 
                "data_ativacao": agora, 
                "data_expiracao": agora + timedelta(days=2),
                "telefone_proprietario": clean_phone
            }, merge=True)

            criar_e_configurar_instancia_automatica(clean_phone)
            time.sleep(2)
            gerar_e_enviar_qrcode_central(clean_phone)
            return

        # 7. Modo de Atendimento Humano
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
                    save_chat_history(clean_phone, "user", message_text)
                    return

        # 8. Transferência Manual para Atendimento Humano
        gatilhos_humano = [r'falar com atendente', r'suporte humano', r'\batendente\b', r'\bhumano\b', r'#suporte', r'falar com pessoa']
        if any(re.search(pattern, msg_clean) for pattern in gatilhos_humano):
            timeout_min = getattr(Config, 'TIMEOUT_HUMANO_MINUTOS', 15)
            chat_ref.set({
                "status_atendimento": "humano",
                "ultima_mensagem_por": "cliente_final",
                "ultima_interacao": agora
            }, merge=True)
            send_whatsapp(
                clean_phone,
                f"🔔 *Atendimento Encaminhado:* A nossa equipa foi notificada. Se não houver resposta imediata, o Negobot Moz voltará a responder automaticamente em {timeout_min} minutos.",
                instance_name=central_instance
            )
            return

        # 9. Resposta Inteligente via Groq REST API (Fallback de Conversação)
        chat_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
        save_chat_history(clean_phone, "user", message_text)

        raw_history = get_chat_history(clean_phone)[-10:]
        contents = []
        for msg in raw_history:
            if isinstance(msg, dict):
                role = "assistant" if msg.get('role') in ["assistant", "model", "atendente"] else "user"
                txt = msg.get('content') or msg.get('text') or ""
                if txt:
                    contents.append({"role": role, "content": str(txt)})

        if status_cliente == 'trial':
            sys_instruction_central = """Você é o assistente oficial da NEGOBOT MOZ.

ATENÇÃO - REGRAS DE ATENDIMENTO (CLIENTE EM TESTE GRÁTIS):
- O cliente está no período de teste grátis ou acabou de solicitar o QR Code.
- Responda de forma clara, direta e objetiva às perguntas do cliente (preços, dúvidas de uso, ajuda, suporte).

🎨 CRIAÇÃO DE ARTES / PUBLICIDADE:
- Se o cliente solicitar a criação de cartazes ou artes para publicidade, informe que pode digitar #imagem seguido da descrição do que deseja (ex: #imagem cartaz para loja de roupas promoção de fim de semana).

💳 INSTRUÇÕES DE PAGAMENTO (SE PERGUNTADO):
- Se o cliente perguntar como pagar: explique que o pagamento é feito via M-Pesa para o número 855000929 (Negobot Moz).
- Após a transferência, basta colar o SMS de confirmação do M-Pesa aqui no chat ou enviar com #pago no início.
- 🚫 PROIBIÇÃO MÁXIMA: NUNCA peça para digitar #qrcode quando o cliente perguntar sobre pagamentos ou métodos de pagamento!

- Apenas oriente a digitar #qrcode se o cliente perguntar explicitamente como conectar o WhatsApp, se relatar falha de conexão, ou pedir novo código.
- Linguagem: Português de Moçambique, tom atencioso, curto e profissional.
"""
        else:
            sys_instruction_central = """Você é o assistente comercial oficial da NEGOBOT MOZ.

🎯 SUA MISSÃO PRINCIPAL:
Apresentar a Negobot Moz de forma breve (automação de WhatsApp para empresas em Moçambique), esclarecer dúvidas de pagamento e convidar o cliente a testar grátis por 2 dias.

💳 INSTRUÇÕES OFICIAIS DE PAGAMENTO:
Quando o cliente perguntar COMO FAZER O PAGAMENTO, forneça as instruções exatas:
1. Transferir o valor do plano escolhido via M-Pesa para o número oficial: 855000929.
2. Enviar a mensagem/SMS de confirmação do M-Pesa aqui neste WhatsApp (ou digitar #pago seguido do código).
3. A ativação é 100% automática assim que o comprovativo for enviado.
🚫 PROIBIÇÃO MÁXIMA: NUNCA diga para o cliente digitar #qrcode para fazer pagamentos. O #qrcode serve APENAS para conectar o WhatsApp.

📌 TABELA OFICIAL DE PLANOS E PREÇOS:
Quando o cliente perguntar sobre valores, preços, custos ou como funciona o pagamento, explica que o pagamento é feito apenas após os 2 dias de teste gratuito e apresenta IMEDIATAMENTE os 3 planos de forma simples e direta:

1. Plano Básico — 500 MT / mês
Perfeito para pequenos negócios que querem parar de responder sempre às mesmas perguntas básicas.
• Atendimento: Respostas automáticas iniciais para perguntas frequentes (FAQ), horário de funcionamento, localização e catálogo em texto.
• Limite: Até 1.500 conversas por mês.
• Conexão: 1 número de WhatsApp.
• Suporte: Suporte técnico básico respondido em até 24h.
• ❌ Nota: Não processa documentos (PDF/Excel), fotos, áudios nem disparos em massa.

2. Plano Médio — 1.000 MT / mês
Ideal para empresas em crescimento que recebem muitos clientes ao mesmo tempo e precisam de interatividade.
• Atendimento: Tudo do Plano Básico + Conversas ILIMITADAS.
• Multimédia: Processamento de Fotos e leitura básica de tabelas Excel.
• Recursos: Menu Interativo de navegação e relatórios de uso mensais.
• Suporte: Suporte prioritário respondido em até 12h.

3. Plano Premium — 1.500 MT / mês
Para empresas que querem uma verdadeira central inteligente, com IA avançada, artes publicitárias e campanhas de vendas.
• Atendimento: Tudo do Plano Médio + Automação Avançada com IA Total.
• Multimédia e Treino: Leitura completa de PDFs e documentos extensos (catálogos, manutenções, manuais), interpretação de Áudios e Geração de Artes Publicitárias (#imagem).
• Campanhas: Direito a ferramentas de Disparos em Massa no WhatsApp e Campanhas de Marketing de forma segura para a base de contactos e grupos.
• Suporte: Suporte dedicado e acompanhamento inicial de configuração por um assistente humano.

Finalize sempre reforçando que o cliente não paga nada agora e pode testar qualquer um destes planos durante 2 dias sem compromisso, bastando digitar "TESTE".

📌 REGRAS DE COMPORTAMENTO OBRIGATÓRIAS:
- NUNCA comente sobre conteúdos de vídeos, links de YouTube ou mensagens fora do escopo comercial.
- Se o cliente enviar um link ou mensagem confusa, convide-o diretamente a digitar "TESTE" para testar a nossa plataforma.
- NUNCA mencione "stock", "produtos de entrega imediata" ou assuntos que não pertençam à Negobot Moz.
- LINGUAGEM: Português de Moçambique, tom profissional, curto e direto.
"""

        response_text = chamar_groq_rest(contents, system_prompt=sys_instruction_central)
        
        if response_text:
            save_chat_history(clean_phone, "assistant", response_text)
            send_whatsapp(clean_phone, response_text, instance_name=central_instance)
            chat_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

    except Exception as e:
        logger.error(f"Erro no process_central_flow para {phone_number_or_data}: {e}", exc_info=True)
