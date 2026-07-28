import requests
import tempfile
import os
import base64
import logging
from services.config import GROQ_API_KEY, GROQ_MODEL, GROQ_VISION_MODEL, GROQ_WHISPER_MODEL

logger = logging.getLogger(__name__)

def chamar_groq_rest(contents_payload, system_instruction="", temperature=0.1, max_tokens=600):
    """Chama a API Groq para gerar resposta."""
    if not GROQ_API_KEY:
        logger.warning("❌ GROQ_API_KEY não encontrada nas variáveis de ambiente.")
        return ""

    if not contents_payload:
        logger.warning("❌ contents_payload vazio")
        return ""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    for item in contents_payload:
        role = item.get("role", "user")
        if role in ["model", "assistant", "atendente"]:
            role = "assistant"
        
        parts = item.get("parts", [])
        texto_msg = "".join([p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p])
        
        if texto_msg:
            messages.append({"role": role, "content": texto_msg})

    if not messages:
        logger.warning("❌ Nenhuma mensagem válida para enviar para Groq")
        return ""

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens)
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        data = response.json()
        
        if response.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"❌ Erro na API Groq (Status {response.status_code}): {data}")
    except Exception as e:
        logger.error(f"❌ Exceção ao chamar Groq API: {e}")

    return "Desculpe, estamos a receber muitas mensagens ao mesmo tempo. Por favor, tente novamente dentro de alguns segundos!"

def transcrever_audio_groq(url_audio_whatsapp):
    """Transcreve áudio para texto usando Groq Whisper."""
    if not GROQ_API_KEY:
        return ""
    
    tmp_path = None
    try:
        headers_evo = {"apikey": os.getenv('EVOLUTION_API_KEY')}
        res = requests.get(url_audio_whatsapp, headers=headers_evo, timeout=25)
        if res.status_code != 200:
            res = requests.get(url_audio_whatsapp, timeout=25)
            
        if res.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
                temp_audio.write(res.content)
                tmp_path = temp_audio.name

            headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            url_whisper = "https://api.groq.com/openai/v1/audio/transcriptions"
            
            with open(tmp_path, "rb") as audio_file:
                files = {
                    "file": (tmp_path, audio_file, "audio/ogg"),
                    "model": (None, GROQ_WHISPER_MODEL)
                }
                response = requests.post(url_whisper, headers=headers_groq, files=files, timeout=30)
                
            if response.status_code == 200:
                texto = response.json().get("text", "")
                logger.info(f"🎙️ Áudio Transcrito: {texto}")
                return texto
    except Exception as e:
        logger.error(f"❌ Erro ao transcrever áudio: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass
    
    return ""

def analisar_imagem_groq(url_imagem, instrucao="Analise e extraia todas as informações relevantes desta imagem ou comprovativo:"):
    """Analisa imagem usando Groq Vision."""
    if not GROQ_API_KEY:
        return ""
    
    try:
        headers_evo = {"apikey": os.getenv('EVOLUTION_API_KEY')}
        res = requests.get(url_imagem, headers=headers_evo, timeout=25)
        if res.status_code != 200:
            res = requests.get(url_imagem, timeout=25)
            
        if res.status_code == 200:
            image_base64 = base64.b64encode(res.content).decode('utf-8')
            
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": GROQ_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instrucao},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            }
            
            resp = requests.post(url, headers=headers, json=payload, timeout=25)
            data = resp.json()
            if resp.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
                resultado = data["choices"][0]["message"]["content"].strip()
                logger.info("👁️ Imagem Analisada com sucesso!")
                return resultado
            else:
                logger.error(f"❌ Erro resposta Groq Vision: {data}")
    except Exception as e:
        logger.error(f"❌ Erro ao analisar imagem no Groq Vision: {e}")
    
    return ""

def criar_prompt_profissional_groq(pedido_utilizador):
    """Cria prompt profissional para geração de imagens."""
    try:
        sys_instruction = (
            "Você é um especialista em Engenharia de Prompts para geração de imagens publicitárias. "
            "Converta o pedido do utilizador num prompt altamente detalhado em INGLÊS. "
            "Adicione detalhes de qualidade visual e contexto corporativo moçambicano como: "
            "'professional marketing banner, microfinance Mozambique context, bright clean lighting, photorealistic, 8k'. "
            "Responda APENAS com o prompt em inglês, sem saudações."
        )
        contents = [{"parts": [{"text": pedido_utilizador}]}]
        resultado = chamar_groq_rest(contents, system_instruction=sys_instruction, temperature=0.7)
        return resultado if resultado else pedido_utilizador
    except Exception as e:
        logger.error(f"❌ Erro ao otimizar prompt no Groq: {e}")
        return pedido_utilizador
