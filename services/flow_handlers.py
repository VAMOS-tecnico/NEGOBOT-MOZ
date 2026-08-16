import re
import time
import logging
from datetime import datetime, timedelta, timezone

from config import Config
import extensions
from database.chat_repo import get_chat_history, save_chat_history
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
    """Verifica se o tempo limite de espera por atendimento humano expirou."""
    if conversa_dados and conversa_dados.get("status_atendimento") == "humano":
        ultima_interacao = conversa_dados.get("ultima_interacao")
        ultima_msg_por = conversa_dados.get("ultima_mensagem_por")
        
        if ultima_msg_por == "cliente_final" and ultima_interacao:
            if ultima_interacao.tzinfo is None:
                ultima_interacao = ultima_interacao.replace(tzinfo=timezone.utc)
            
            timeout_min = getattr(Config, 'TIMEOUT_HUMANO_MINUTOS', 15)
            minutos_decorridos = (agora - ultima_interacao).total_seconds() / 60.0
            
            if minutos_decorridos >= timeout_min:
                conversa_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                logger.info(f"Timeout humano atingido ({minutos_decorridos:.1f} min). Bot reassumiu.")
                return True
    return False


def processar_pagamento(clean_phone, message_text, central_instance):
    """Valida comprovativos M-Pesa."""
    tenant_id = f"cliente_{clean_phone}"
    resposta_pagamento = validar_e_ativar_pagamento_mpesa(
        tenant_id=tenant_id,
        client_phone=clean_phone,
        message_text=message_text
    )
    if any(termo in resposta_pagamento for termo in ["PAGAMENTO CONFIRMADO", "Aguarde", "Insuficiente", "Já Utilizado", "Não Identificado"]):
        send_whatsapp(clean_phone, resposta_pagamento, instance_name=central_instance)
        return True
    return False


def processar_duvida_pagamento(clean_phone, message_text, central_instance):
    """Envia instruções detalhadas de pagamento via M-Pesa."""
    resposta_instrucao = (
        "💳 *Como efetuar o pagamento do Negobot Moz:*\n\n"
        "1️⃣ Faça a transferência do valor do plano escolhido via **M-Pesa** para o número oficial:\n"
        "📱 *855000929* (Nome: **Abel Francisco**)\n\n"
        "2️⃣ Cole aqui no chat a mensagem/SMS de confirmação recebida do M-Pesa (ou envie com **#pago** no início).\n\n"
        "⚡ A sua conta e plano serão ativados automaticamente pelo nosso sistema assim que o comprovativo for enviado"
    )
    save_chat_history(clean_phone, "user", message_text)
    save_chat_history(clean_phone, "assistant", resposta_instrucao)
    send_whatsapp(clean_phone, resposta_instrucao, instance_name=central_instance)


def processar_geracao_imagem(clean_phone, message_text, central_instance):
    """Gera e envia arte publicitária."""
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


def processar_teste_gratis(clean_phone, agora, central_instance):
    """Ativa o período de teste de 2 dias e gera QR Code."""
    send_whatsapp(clean_phone, "⏳ *A preparar o seu teste grátis de 2 dias do Negobot Moz...* 🚀", instance_name=central_instance)
    
    cliente_doc_ref = extensions.db.collection('clientes').document(clean_phone)
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


def processar_suporte_humano(clean_phone, chat_ref, agora, central_instance):
    """Encaminha o chat para atendimento humano."""
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


def processar_resposta_ia(clean_phone, message_text, status_cliente, agora, central_instance, chat_ref):
    """Gera resposta baseada na IA da Groq com detalhes completos e dados bancários atualizados."""
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
        sys_instruction = """Você é o assistente oficial da NEGOBOT MOZ.

ATENÇÃO - REGRAS DE ATENDIMENTO (CLIENTE EM TESTE GRÁTIS):
- O cliente está no período de teste grátis ou acabou de solicitar o QR Code.
- Responda de forma clara, direta e objetiva às perguntas do cliente (preços, dúvidas de uso, ajuda, suporte).
- 🚫 PROIBIDO usar frases genéricas de suporte como "Como posso ajudar hoje?".

🎨 CRIAÇÃO DE ARTES / PUBLICIDADE:
- Se o cliente solicitar a criação de cartazes ou artes para publicidade, informe que pode digitar #imagem seguido da descrição do que deseja (ex: #imagem cartaz para loja de roupas promoção de fim de semana).

💳 INSTRUÇÕES DE PAGAMENTO (SE PERGUNTADO):
- Se o cliente perguntar como pagar: explique que o pagamento é feito via M-Pesa para o número 855000929 em nome de Abel Francisco.
- Após a transferência, basta colar o SMS de confirmação do M-Pesa aqui no chat ou enviar com #pago no início.
- 🚫 PROIBIÇÃO MÁXIMA: NUNCA peça para digitar #qrcode quando o cliente perguntar sobre pagamentos!

- Linguagem: Português de Moçambique, tom atencioso, curto e profissional.
"""
    else:
        sys_instruction = """Você é o assistente comercial oficial da NEGOBOT MOZ (plataforma de automação de WhatsApp com Inteligência Artificial para negócios em Moçambique).

🚨 REGRA OBRIGATÓRIA DE SAUDAÇÕES (MUITO IMPORTANTE):
- Se o cliente enviar uma saudação simples (ex: "Boa tarde", "Olá", "Como está?", "Oy", "Bom dia"), responda CORTÊSMENTE e APRESENTE LOGO O NEGOBOT MOZ.
- Exemplo de resposta para saudações:
  "Olá! Estou bem, obrigado por perguntar! Eu sou o assistente do Negobot Moz, uma plataforma de automação de WhatsApp com Inteligência Artificial para negócios em Moçambique. Nossa tecnologia ajuda empresas e empreendedores a automatizarem o atendimento via WhatsApp, permitindo que atendam clientes 24/7 de forma eficiente e personalizada. Se você está interessado em saber mais, basta digitar "TESTE" para experimentar nossa plataforma grátis por 2 dias!"

🚫 PROIBIÇÃO ABSOLUTA:
- NUNCA use frases genéricas de suporte como: "Como posso ajudar hoje?", "O que posso fazer por você hoje?", "É um prazer conversar com você novamente".
- NUNCA invente preços, produtos de terceiros, stock ou serviços fora do escopo da Negobot Moz.

📌 TABELA DETALHADA OFICIAL DE PLANOS E BENEFÍCIOS:
Quando o cliente perguntar sobre valores, preços, custos ou quiser escolher um plano, apresente SEMPRE todos os detalhes e benefícios completos abaixo:

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

💳 INSTRUÇÕES DE PAGAMENTO (SE PERGUNTADO):
- Transferência via M-Pesa para o número oficial: **855000929** em nome de **Abel Francisco**.
- Enviar comprovativo/SMS aqui no chat ou com #pago no início.
- 🚫 NUNCA peça para digitar #qrcode para fazer pagamentos (o #qrcode serve apenas para conectar o WhatsApp).

- LINGUAGEM: Português de Moçambique, tom profissional, comercial, claro e direto.
"""

    response_text = chamar_groq_rest(contents, system_prompt=sys_instruction)
    if response_text:
        save_chat_history(clean_phone, "assistant", response_text)
        send_whatsapp(clean_phone, response_text, instance_name=central_instance)
        chat_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)
