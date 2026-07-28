import os
import requests
import tempfile
import base64
from config import Config

def chamar_groq_rest(contents_payload, system_instruction="", temperature=0.1):
    if not Config.GROQ_API_KEY:
        print("❌ GROQ_API_KEY não encontrada nas variáveis de ambiente.")
        return ""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {Config.GROQ_API_KEY}",
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

    payload = {
        "model": Config.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 600
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        data = response.json()
        
        if response.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"❌ Erro na API do Groq (Status {response.status_code}): {data}")
    except Exception as e:
        print(f"❌ Exceção ao chamar Groq API: {e}")

    return "Desculpe, estamos a receber muitas mensagens ao mesmo tempo. Por favor, tente novamente dentro de alguns segundos!"

def transcrever_audio_groq(url_audio_whatsapp):
    if not Config.GROQ_API_KEY:
        return ""
    try:
        headers_evo = {"apikey": Config.EVOLUTION_API_KEY}
        res = requests.get(url_audio_whatsapp, headers=headers_evo, timeout=25)
        if res.status_code != 200:
            res = requests.get(url_audio_whatsapp, timeout=25)
            
        if res.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
                temp_audio.write(res.content)
                temp_path = temp_audio.name

            headers_groq = {"Authorization": f"Bearer {Config.GROQ_API_KEY}"}
            url_whisper = "https://api.groq.com/openai/v1/audio/transcriptions"
            
            with open(temp_path, "rb") as audio_file:
                files = {
                    "file": (temp_path, audio_file, "audio/ogg"),
                    "model": (None, "whisper-large-v3")
                }
                response = requests.post(url_whisper, headers=headers_groq, files=files, timeout=30)
                
            os.remove(temp_path)
            if response.status_code == 200:
                texto = response.json().get("text", "")
                print(f"🎙️ Áudio Transcrito: {texto}")
                return texto
    except Exception as e:
        print(f"❌ Erro ao transcrever áudio: {e}")
    return ""

def analisar_imagem_groq(url_imagem, instrucao="Analise e extraia todas as informações relevantes desta imagem ou comprovativo:"):
    if not Config.GROQ_API_KEY:
        return ""
    try:
        headers_evo = {"apikey": Config.EVOLUTION_API_KEY}
        res = requests.get(url_imagem, headers=headers_evo, timeout=25)
        if res.status_code != 200:
            res = requests.get(url_imagem, timeout=25)
            
        if res.status_code == 200:
            image_base64 = base64.b64encode(res.content).decode('utf-8')
            
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": Config.GROQ_VISION_MODEL,
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
                print("👁️ Imagem Analisada com sucesso!")
                return resultado
            else:
                print(f"❌ Erro resposta Groq Vision: {data}")
    except Exception as e:
        print(f"❌ Erro ao analisar imagem no Groq Vision: {e}")
    return ""
