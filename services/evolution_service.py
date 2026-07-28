import re
import time
import requests
import logging
from urllib.parse import quote
from config import Config

logger = logging.getLogger(__name__)

def _get_clean_instance(instance_name=None):
    """Sanitiza e codifica o nome da instância para evitar erros de URL (ex: espaços)."""
    target = instance_name or getattr(Config, 'EVOLUTION_INSTANCE_NAME', '')
    return quote(str(target).strip())

def notificar_erro_admin(erro_msg):
    """Envia um alerta ao número do administrador em caso de falha grave."""
    admin_num = getattr(Config, 'ADMIN_NUMBER', None)
    if admin_num:
        try:
            central_instance = _get_clean_instance()
            headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
            url = f"{Config.EVOLUTION_API_URL}/message/sendText/{central_instance}"
            
            to_number = admin_num if "@" in str(admin_num) else f"{admin_num}@s.whatsapp.net"
            payload = {
                "number": to_number,
                "text": f"⚠️ *[ALERTA CRÍTICO - NEGOBOT]*\n\nOcorreu uma falha no servidor:\n❌ `{erro_msg}`\n\n*Verifique os logs.*"
            }
            requests.post(url, headers=headers, json=payload, timeout=45)
        except Exception as e:
            logger.error(f"Falha ao enviar notificação de erro ao admin: {e}")

def send_whatsapp(to, text, instance_name=None):
    """Envia uma mensagem de texto via Evolution API com timeouts expandidos contra Cold Starts."""
    if not text or not str(text).strip():
        return False

    clean_instance = _get_clean_instance(instance_name)
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    
    # 1. Envio de presença (composing) com tratamento isolado
    try:
        url_presence = f"{Config.EVOLUTION_API_URL}/chat/sendPresence/{clean_instance}"
        requests.post(url_presence, headers=headers, json={"number": str(to), "presence": "composing"}, timeout=15)
        time.sleep(1)
    except Exception as p_err:
        logger.warning(f"Não foi possível enviar indicação de presença: {p_err}")

    # 2. Envio da mensagem principal
    try:
        url = f"{Config.EVOLUTION_API_URL}/message/sendText/{clean_instance}"
        payload = {
            "number": str(to),
            "text": str(text),
            "options": {
                "delay": 1200,
                "presence": "composing",
                "linkPreview": True
            }
        }
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        res.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"ERRO ao enviar mensagem via Evolution API ({url}): {e}")
        return False

def criar_e_configurar_instancia_automatica(phone_number):
    """Cria e configura o webhook para uma nova instância de utilizador."""
    try:
        client_instance_raw = re.sub(r'\D', '', str(phone_number))
        client_instance = quote(client_instance_raw)
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        
        # Limpeza preventiva de instâncias anteriores
        try:
            requests.delete(f"{Config.EVOLUTION_API_URL}/instance/logout/{client_instance}", headers=headers, timeout=30)
            requests.delete(f"{Config.EVOLUTION_API_URL}/instance/delete/{client_instance}", headers=headers, timeout=30)
        except Exception:
            pass
        
        time.sleep(2)
        
        url_create = f"{Config.EVOLUTION_API_URL}/instance/create"
        payload_create = {
            "instanceName": client_instance_raw, 
            "qrcode": True, 
            "integration": "WHATSAPP-BAILEYS"
        }
        res_create = requests.post(url_create, headers=headers, json=payload_create, timeout=45)
        res_create.raise_for_status()
        
        webhook_target_url = getattr(Config, 'WEBHOOK_URL', None)
        if webhook_target_url:
            url_webhook = f"{Config.EVOLUTION_API_URL}/webhook/set/{client_instance}"
            payload_webhook = {
                "url": webhook_target_url,
                "enabled": True,
                "events": ["MESSAGES_UPSERT"]
            }
            requests.post(url_webhook, headers=headers, json=payload_webhook, timeout=45)

        return True
    except Exception as e:
        erro_msg = f"Erro ao automatizar criação/webhook para {phone_number}: {e}"
        logger.error(erro_msg)
        notificar_erro_admin(erro_msg)
        return False

def gerar_e_enviar_qrcode_central(phone_number):
    """Solicita a ligação da instância e envia a imagem do QR Code ao utilizador."""
    try:
        client_instance_raw = re.sub(r'\D', '', str(phone_number))
        client_instance = quote(client_instance_raw)
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        
        url_connect = f"{Config.EVOLUTION_API_URL}/instance/connect/{client_instance}"
        response_connect = requests.get(url_connect, headers=headers, timeout=45)
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

        central_instance = _get_clean_instance()
        url_send_media = f"{Config.EVOLUTION_API_URL}/message/sendMedia/{central_instance}"
        
        caption_text = (
            "🤖 *Aqui está o seu QR Code do Negobot Moz!* 🚀\n\n"
            "1️⃣ Abra o WhatsApp que vai atender os seus clientes.\n"
            "2️⃣ Vá a *Aparelhos Conectados* -> *Conectar um aparelho*.\n"
            "3️⃣ Aponte a câmara e escaneie *imediatamente* este QR Code.\n\n"
            "Se expirar, digite *#qrcode* aqui para gerar um novo!"
        )
        
        payload_media = {
            "number": str(phone_number),
            "caption": caption_text,
            "media": base64_qrcode,
            "mediatype": "image",
            "fileName": "qrcode.png"
        }
        requests.post(url_send_media, headers=headers, json=payload_media, timeout=60)
        return True
    except Exception as e:
        logger.error(f"Erro ao gerar QR Code para {phone_number}: {e}")
        return False
