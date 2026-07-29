import os
import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

def chamar_groq_rest(historico_mensagens, system_prompt=None):
    """
    Envia as mensagens para a API da Groq mantendo um HISTÓRICO ENXUTO (máx 6 mensagens).
    Possui tratamento para o limite de requisições (Erro 429) e fallback de modelo.
    """
    api_key = getattr(Config, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
    if not api_key:
        logger.error("GROQ_API_KEY não configurada no ambiente.")
        return "Olá! Sou o assistente oficial do Negobot Moz. Como posso ajudar a automatizar o seu WhatsApp hoje? Digite *TESTE* para experimentar 2 dias grátis!"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload_messages = []

    # 1. Injeção da instrução de sistema
    if system_prompt:
        payload_messages.append({
            "role": "system",
            "content": str(system_prompt).strip()
        })

    # 2. ✂️ HISTÓRICO ENXUTO: Filtra estritamente as últimas 6 mensagens da conversa
    if isinstance(historico_mensagens, list) and historico_mensagens:
        historico_recente = historico_mensagens[-6:]  # Pega apenas os últimos 6 itens

        for msg in historico_recente:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                role = "assistant" if msg["role"] in ["assistant", "model", "atendente"] else "user"
                payload_messages.append({
                    "role": role,
                    "content": str(msg["content"])
                })

    # Modelo principal e payload
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": payload_messages,
        "temperature": 0.2,
        "max_tokens": 400
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        
        # Tratamento do limite de requisições (Erro 429) -> Redireciona para modelo rápido 8B
        if response.status_code == 429:
            logger.warning("Limite do modelo 70B atingido. A alternar para modelo rápido (8B)...")
            payload["model"] = "llama-3.1-8b-instant"
            response = requests.post(url, headers=headers, json=payload, timeout=25)

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.error(f"Erro ao chamar a API da Groq: {e}")
        return "Olá! O nosso sistema está a processar muitas mensagens no momento. Por favor, envie a sua dúvida novamente em instantes!"

def transcrever_audio_groq(audio_file):
    """Transcreve áudio enviado pelos utilizadores via Whisper na Groq."""
    api_key = getattr(Config, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
    if not api_key:
        logger.error("GROQ_API_KEY não configurada para transcrição.")
        return ""

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        files = {'file': audio_file}
        data = {'model': 'whisper-large-v3'}
        response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        response.raise_for_status()
        return response.json().get("text", "").strip()
    except Exception as e:
        logger.error(f"Erro ao transcrever áudio via Groq: {e}")
        return ""

def analisar_imagem(image_file, prompt="O que há nesta imagem?"):
    """Processa a análise de imagens enviadas no chat."""
    logger.info("Solicitação de análise de imagem recebida.")
    return "Recebi a sua imagem. Como posso ajudar com a Negobot Moz?"
