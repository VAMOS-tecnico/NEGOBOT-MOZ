import re
import time
import requests
from config import Config

def notificar_erro_admin(erro_msg):
    if Config.ADMIN_NUMBER:
        central_instance = Config.EVOLUTION_INSTANCE_NAME
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        url = f"{Config.EVOLUTION_API_URL}/message/sendText/{central_instance}"
        
        to_number = Config.ADMIN_NUMBER if "@" in Config.ADMIN_NUMBER else f"{Config.ADMIN_NUMBER}@s.whatsapp.net"
        payload = {
            "number": to_number,
            "text": f"⚠️ *[ALERTA CRÍTICO - NEGOBOT]*\n\nOcorreu uma falha no servidor:\n❌ `{erro_msg}`\n\n*Verifique os logs.*"
        }
        try:
            requests.post(url, headers=headers, json=payload, timeout=10)
        except Exception as e:
            print(f"Falha ao enviar notificação de erro ao admin: {e}")

def send_whatsapp(to, text, instance_name=None):
    if not text or not str(text).strip():
        return False

    if not instance_name:
        instance_name = Config.EVOLUTION_INSTANCE_NAME
        
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    
    try:
        url_presence = f"{Config.EVOLUTION_API_URL}/chat/sendPresence/{instance_name}"
        requests.post(url_presence, headers=headers, json={"number": to, "presence": "composing"}, timeout=5)
        time.sleep(1)
        
        url = f"{Config.EVOLUTION_API_URL}/message/sendText/{instance_name}"
        res = requests.post(url, headers=headers, json={"number": to, "text": text}, timeout=10)
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"ERRO ao enviar mensagem: {e}")
        return False

def criar_e_configurar_instancia_automatica(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        
        requests.delete(f"{Config.EVOLUTION_API_URL}/instance/logout/{client_instance}", headers=headers, timeout=5)
        requests.delete(f"{Config.EVOLUTION_API_URL}/instance/delete/{client_instance}", headers=headers, timeout=5)
        time.sleep(2)
        
        url_create = f"{Config.EVOLUTION_API_URL}/instance/create"
        payload_create = {"instanceName": client_instance, "qrcode": True, "integration": "WHATSAPP-BAILEYS"}
        res_create = requests.post(url_create, headers=headers, json=payload_create, timeout=10)
        res_create.raise_for_status()
        
        webhook_target_url = Config.WEBHOOK_URL
        if webhook_target_url:
            url_webhook = f"{Config.EVOLUTION_API_URL}/webhook/set/{client_instance}"
            payload_webhook = {
                "url": webhook_target_url,
                "enabled": True,
                "events": ["MESSAGES_UPSERT"]
            }
            requests.post(url_webhook, headers=headers, json=payload_webhook, timeout=10)

        return True
    except Exception as e:
        erro_msg = f"Erro ao automatizar criação/webhook para {phone_number}: {e}"
        notificar_erro_admin(erro_msg)
        return False

def gerar_e_enviar_qrcode_central(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        
        url_connect = f"{Config.EVOLUTION_API_URL}/instance/connect/{client_instance}"
        response_connect = requests.get(url_connect, headers=headers, timeout=10)
        response_connect.raise_for_status()
        
        dados_resposta = response_connect.json()
        if dados_resposta.get("instance", {}).get("state") == "open":
            send_whatsapp(phone_number, "✅ O seu assistente virtual já se encontra ativo e operacional!")
            return True
            
        base64_qrcode = dados_resposta.get("base64")
        if not base64_qrcode:
            return False

        if "," in base64_qrcode:
            base64_qrcode = base64_qrcode.split(",")[1]

        central_instance = Config.EVOLUTION_INSTANCE_NAME
        url_send_media = f"{Config.EVOLUTION_API_URL}/message/sendMedia/{central_instance}"
        
        caption_text = (
            "🤖 *Aqui está o seu QR Code do Negobot Moz!* 🚀\n\n"
            "1️⃣ Abra o WhatsApp que vai atender os seus clientes.\n"
            "2️⃣ Vá a *Aparelhos Conectados* -> *Conectar um aparelho*.\n"
            "3️⃣ Aponte a câmara e escaneie *imediatamente* este QR Code.\n\n"
            "Se expirar, digite *#qrcode* aqui para gerar um novo!"
        )
        
        payload_media = {
            "number": phone_number,
            "caption": caption_text,
            "media": base64_qrcode,
            "mediatype": "image",
            "fileName": "qrcode.png"
        }
        requests.post(url_send_media, headers=headers, json=payload_media, timeout=15)
        return True
    except Exception as e:
        print(f"Erro ao gerar QR Code: {e}")
        return False
