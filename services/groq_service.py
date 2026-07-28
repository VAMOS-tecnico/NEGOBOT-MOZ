import os
import base64
import logging
from groq import Groq
from config import Config

logger = logging.getLogger(__name__)

# Inicializa o cliente Groq
client = Groq(api_key=Config.GROQ_API_KEY)

def transcrever_audio_groq(audio_bytes, filename="audio.mp3"):
    """Transcreve áudio do WhatsApp usando Whisper no Groq."""
    try:
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3-turbo",
            response_format="text"
        )
        return transcription
    except Exception as e:
        logger.error(f"Erro na transcrição de áudio Groq: {e}")
        return ""

def analisar_imagem(image_bytes_or_base64, prompt="Analise esta imagem em detalhes"):
    """Analisa comprovativos/fotos usando visão computacional (Qwen Vision)."""
    try:
        if isinstance(image_bytes_or_base64, bytes):
            base64_image = base64.b64encode(image_bytes_or_base64).decode('utf-8')
        else:
            base64_image = image_bytes_or_base64

        model_vision = getattr(Config, 'GROQ_VISION_MODEL', 'qwen-2.5-32b')

        response = client.chat.completions.create(
            model=model_vision,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": str(prompt)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Erro na análise de imagem Groq: {e}")
        return "Não foi possível analisar a imagem enviada."

def normalizar_mensagens(prompt_ou_mensagens, system_prompt=""):
    """Converte qualquer tipo de entrada (string, dict ou lista) no formato exigido pela Groq."""
    formatted = []
    if system_prompt:
        formatted.append({"role": "system", "content": str(system_prompt)})

    if isinstance(prompt_ou_mensagens, str):
        formatted.append({"role": "user", "content": prompt_ou_mensagens})
    elif isinstance(prompt_ou_mensagens, dict):
        role = prompt_ou_mensagens.get("role", "user")
        content = prompt_ou_mensagens.get("content", str(prompt_ou_mensagens))
        formatted.append({"role": role, "content": str(content)})
    elif isinstance(prompt_ou_mensagens, list):
        for item in prompt_ou_mensagens:
            if isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", item.get("texto", ""))
                if isinstance(content, (dict, list)):
                    content = str(content)
                formatted.append({"role": role, "content": str(content)})
            else:
                formatted.append({"role": "user", "content": str(item)})
    else:
        formatted.append({"role": "user", "content": str(prompt_ou_mensagens)})

    return formatted

def gerar_resposta_groq(messages, system_prompt=""):
    """Gera respostas de texto usando Llama 3.3 70B com tratamento seguro de tipos."""
    try:
        formatted_messages = normalizar_mensagens(messages, system_prompt)
        model_text = getattr(Config, 'GROQ_MODEL', 'llama-3.3-70b-versatile')

        response = client.chat.completions.create(
            model=model_text,
            messages=formatted_messages
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Erro ao gerar resposta Groq: {e}")
        return "Desculpe, ocorreu um erro temporário no meu sistema de IA."

def chamar_groq_rest(prompt_ou_mensagens, system_prompt=""):
    """Função universal de compatibilidade para os workflows."""
    return gerar_resposta_groq(prompt_ou_mensagens, system_prompt)
