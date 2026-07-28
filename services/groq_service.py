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
                        {"type": "text", "text": prompt},
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

def gerar_resposta_groq(messages, system_prompt=""):
    """Gera respostas de texto usando Llama 3.3 70B."""
    try:
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        model_text = getattr(Config, 'GROQ_MODEL', 'llama-3.3-70b-versatile')

        response = client.chat.completions.create(
            model=model_text,
            messages=formatted_messages
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Erro ao gerar resposta Groq: {e}")
        return "Desculpe, ocorreu um erro temporário no meu sistema de IA."
