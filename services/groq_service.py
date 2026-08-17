import os
import re
import base64
import requests
import logging
import asyncio
import edge_tts
from config import Config

logger = logging.getLogger(__name__)

# Mapeamento de vozes neurais para suporte multilingue no envio de áudio
VOIZES_POR_IDIOMA = {
    "pt": "pt-BR-AntonioNeural",
    "en": "en-US-GuyNeural",
    "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
    "zh": "zh-CN-YunxiNeural"
}

def _limpar_texto_saida(texto):
    """Remove caracteres de controlo invisíveis que podem quebrar o JSON do WhatsApp."""
    if not texto:
        return ""
    texto_limpo = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', str(texto))
    return texto_limpo.strip()

def _detectar_idioma_simples(texto):
    """Identifica o idioma da resposta para selecionar a voz neural adequada."""
    texto_lower = texto.lower()
    if any(w in texto_lower for w in [" the ", " is ", " you ", " hello ", " thanks ", " what ", " how "]):
        return "en"
    if any(w in texto_lower for w in [" hola ", " gracias ", " por favor ", " como ", " qué ", " bien "]):
        return "es"
    if any(w in texto_lower for w in [" bonjour ", " merci ", " oui ", " vous ", " comment "]):
        return "fr"
    if any(w in texto_lower for w in [" hallo ", " danke ", " bitte ", " gut "]):
        return "de"
    return "pt"  # Idioma padrão

def chamar_groq_rest(historico_mensagens, system_prompt=None):
    """
    Envia as mensagens para a API da Groq.
    Garante que o bot deteta e responde rigorosamente no idioma do utilizador.
    """
    api_key = getattr(Config, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
    if not api_key:
        logger.error("GROQ_API_KEY não configurada no ambiente.")
        return "Olá! Sou o assistente oficial do Negobot Moz. Como posso ajudar a automatizar o seu WhatsApp hoje?"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Instrução explícita de multilinguagem
    instrucao_multilingue = "Detect the language used by the user and ALWAYS respond in that exact same language (e.g. English, French, Portuguese, Spanish, etc.)."
    prompt_final = f"{system_prompt}\n\n[INSTRUÇÃO DE IDIOMA]: {instrucao_multilingue}" if system_prompt else instrucao_multilingue

    payload_messages = [{"role": "system", "content": prompt_final}]

    if isinstance(historico_mensagens, list) and historico_mensagens:
        historico_recente = historico_mensagens[-6:]
        for msg in historico_recente:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                role = "assistant" if msg["role"] in ["assistant", "model", "atendente"] else "user"
                payload_messages.append({
                    "role": role,
                    "content": str(msg["content"])
                })

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": payload_messages,
        "temperature": 0.2,
        "max_tokens": 400
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        
        # Fallback de limite de taxa para o modelo 8B
        if response.status_code == 429:
            logger.warning("Limite do modelo 70B atingido. A alternar para modelo rápido (8B)...")
            payload["model"] = "llama-3.1-8b-instant"
            response = requests.post(url, headers=headers, json=payload, timeout=25)

        response.raise_for_status()
        data = response.json()
        
        resposta_raw = data["choices"][0]["message"]["content"]
        return _limpar_texto_saida(resposta_raw)

    except Exception as e:
        logger.error(f"Erro ao chamar a API da Groq: {e}")
        return "O nosso sistema está a processar muitas mensagens no momento. Por favor, tente novamente em instantes."

def transcrever_audio_groq(audio_file):
    """
    Transcreve áudio via Whisper na Groq.
    AUTO-DETETA QUALQUER IDIOMA FALADO no mundo sem restrições.
    """
    api_key = getattr(Config, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
    if not api_key:
        logger.error("GROQ_API_KEY não configurada para transcrição.")
        return ""

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        filename = os.path.basename(getattr(audio_file, "name", "audio.wav")) or "audio.wav"
        mimetype = "audio/wav" if filename.lower().endswith(".wav") else "audio/ogg"
        files = {'file': (filename, audio_file, mimetype)}
        data = {
            'model': 'whisper-large-v3',
            'language': 'pt',
            'response_format': 'json'
        }
        response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        if not response.ok:
            logger.error("Groq Whisper HTTP %s: %s", response.status_code, response.text[:500])
        response.raise_for_status()
        return response.json().get("text", "").strip()
    except Exception as e:
        logger.error(f"Erro ao transcrever áudio via Groq: {e}")
        return ""

def analisar_imagem(image_input, prompt="Describe and extract all details, text, products, and prices from this image in the user's language:"):
    """Análise de imagens multilingue com Llama 3.2 Vision."""
    api_key = getattr(Config, 'GROQ_API_KEY', None) or os.getenv('GROQ_API_KEY')
    if not api_key:
        logger.error("GROQ_API_KEY não configurada para análise de imagem.")
        return "Erro ao analisar a imagem: Chave da API não configurada."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        if isinstance(image_input, str) and os.path.exists(image_input):
            with open(image_input, "rb") as f:
                encoded_image = base64.b64encode(f.read()).decode("utf-8")
        elif hasattr(image_input, "read"):
            image_input.seek(0)
            encoded_image = base64.b64encode(image_input.read()).decode("utf-8")
        elif isinstance(image_input, bytes):
            encoded_image = base64.b64encode(image_input).decode("utf-8")
        else:
            return "Não foi possível ler o arquivo de imagem fornecido."

        payload = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        resposta_raw = data["choices"][0]["message"]["content"]
        return _limpar_texto_saida(resposta_raw)

    except Exception as e:
        logger.error(f"Erro ao analisar imagem via Groq Vision: {e}")
        return "Desculpe, ocorreu uma falha ao ler os dados dessa imagem."

def gerar_audio_resposta(texto, caminho_saida="resposta_voz.mp3", idioma=None):
    """
    Converte o texto da IA em áudio ajustando automaticamente a voz nativa
    ao idioma detetado da resposta.
    """
    try:
        texto_limpo = _limpar_texto_saida(texto)
        if not texto_limpo:
            return None

        if not idioma:
            idioma = _detectar_idioma_simples(texto_limpo)

        # Escolhe a voz nativa correta para a língua detetada
        voz_selecionada = VOIZES_POR_IDIOMA.get(idioma, "pt-BR-AntonioNeural")

        async def _gerar():
            communicate = edge_tts.Communicate(texto_limpo, voz_selecionada)
            await communicate.save(caminho_saida)

        asyncio.run(_gerar())
        return caminho_saida
    except Exception as e:
        logger.error(f"Erro ao gerar áudio de resposta (TTS): {e}")
        return None
