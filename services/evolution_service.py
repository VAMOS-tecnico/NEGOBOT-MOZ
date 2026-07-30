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


def _limpar_numero(phone_number):
    """Remove @s.whatsapp.net, +, espaços e letras, mantendo apenas dígitos."""
    if not phone_number:
        return ""
    num_str = str(phone_number).split('@')[0]
    return re.sub(r'\D', '', num_str)


def notificar_erro_admin(erro_msg):
    """Envia um alerta ao número do administrador em caso de falha grave."""
    admin_num = getattr(Config, 'ADMIN_NUMBER', None)
    if admin_num:
        try:
            clean_admin_num = _limpar_numero(admin_num)
            central_instance = _get_clean_instance()
            headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
            url = f"{Config.EVOLUTION_API_URL}/message/sendText/{central_instance}"
            
            payload = {
                "number": clean_admin_num,
                "text": f"⚠️ *[ALERTA CRÍTICO - NEGOBOT]*\n\nOcorreu uma falha no servidor:\n❌ `{erro_msg}`\n\n*Verifique os logs.*",
                "delay": 1200
            }
            requests.post(url, headers=headers, json=payload, timeout=45)
        except Exception as e:
            logger.error(f"Falha ao enviar notificação de erro ao admin: {e}")


def send_whatsapp(to, text, instance_name=None):
    """Envia uma mensagem de texto via Evolution API sem conflitos de presença/socket."""
    if not text or not str(text).strip():
        return False

    clean_number = _limpar_numero(to)
    if not clean_number:
        logger.error(f"Número inválido fornecido para envio: '{to}'")
        return False

    clean_instance = _get_clean_instance(instance_name)
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    
    url = f"{Config.EVOLUTION_API_URL}/message/sendText/{clean_instance}"
    
    payload_v2 = {
        "number": clean_number,
        "text": str(text).strip(),
        "delay": 1200
    }

    try:
        res = requests.post(url, headers=headers, json=payload_v2, timeout=60)
        
        # Se retornar 400 Bad Request, tenta o payload legado (v1)
        if res.status_code == 400:
            logger.warning(f"Tentativa v2 retornou 400. Tentando payload v1 para {clean_number}...")
            payload_v1 = {
                "number": clean_number,
                "options": {
                    "delay": 1200
                },
                "textMessage": {
                    "text": str(text).strip()
                }
            }
            res = requests.post(url, headers=headers, json=payload_v1, timeout=60)

        res.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"ERRO ao enviar mensagem via Evolution API ({url}): {e}")
        return False


def criar_e_configurar_instancia_automatica(phone_number):
    """Cria e configura o webhook + definições de instância sem spam de requisições."""
    try:
        client_instance_raw = _limpar_numero(phone_number)
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
        
        # 1. Definições da Instância
        try:
            url_settings = f"{Config.EVOLUTION_API_URL}/instance/setSettings/{client_instance}"
            payload_settings = {
                "reject_call": True,
                "msg_call": "",
                "groups_ignore": True,
                "always_online": False,
                "read_messages": True,
                "read_status": False,
                "sync_full_history": False
            }
            requests.post(url_settings, headers=headers, json=payload_settings, timeout=30)
        except Exception as set_err:
            logger.warning(f"Não foi possível aplicar definições de segurança na instância: {set_err}")

        # 2. Configurar o Webhook Automaticamente
        webhook_target_url = getattr(Config, 'WEBHOOK_URL', None)
        if webhook_target_url:
            url_webhook = f"{Config.EVOLUTION_API_URL}/webhook/set/{client_instance}"
            payload_webhook = {
                "url": webhook_target_url,
                "enabled": True,
                "byEvents": False,
                "base64": False,
                "webhookByEvents": False,
                "events": [
                    "MESSAGES_UPSERT",
                    "CHATS_UPSERT",
                    "CONNECTION_UPDATE"
                ],
                "groupsIgnore": True
            }
            res_wh = requests.post(url_webhook, headers=headers, json=payload_webhook, timeout=45)
            logger.info(f"Webhook configurado automaticamente para {client_instance}: {res_wh.status_code}")

        return True
    except Exception as e:
        erro_msg = f"Erro ao automatizar criação/webhook para {phone_number}: {e}"
        logger.error(erro_msg)
        notificar_erro_admin(erro_msg)
        return False


def gerar_e_enviar_qrcode_central(phone_number):
    """Solicita a ligação da instância e envia a imagem do QR Code ao utilizador."""
    try:
        client_instance_raw = _limpar_numero(phone_number)
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
            "number": client_instance_raw,
            "caption": caption_text,
            "media": base64_qrcode,
            "mediatype": "image",
            "fileName": "qrcode.png",
            "delay": 1200
        }
        requests.post(url_send_media, headers=headers, json=payload_media, timeout=60)
        return True
    except Exception as e:
        logger.error(f"Erro ao gerar QR Code para {phone_number}: {e}")
        return False


def aplicar_travas_instancia_central():
    """Aplica as definições silenciosas à instância CENTRAL."""
    try:
        central_instance = _get_clean_instance()
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        
        url_settings = f"{Config.EVOLUTION_API_URL}/instance/setSettings/{central_instance}"
        payload_settings = {
            "reject_call": True,
            "msg_call": "",
            "groups_ignore": True,
            "always_online": False,
            "read_messages": True,
            "read_status": False,
            "sync_full_history": False
        }
        requests.post(url_settings, headers=headers, json=payload_settings, timeout=30)

        webhook_target_url = getattr(Config, 'WEBHOOK_URL', None)
        if webhook_target_url:
            url_webhook = f"{Config.EVOLUTION_API_URL}/webhook/set/{central_instance}"
            payload_webhook = {
                "url": webhook_target_url,
                "enabled": True,
                "byEvents": False,
                "base64": False,
                "webhookByEvents": False,
                "events": [
                    "MESSAGES_UPSERT",
                    "CHATS_UPSERT",
                    "CONNECTION_UPDATE"
                ],
                "groupsIgnore": True
            }
            requests.post(url_webhook, headers=headers, json=payload_webhook, timeout=45)
    except Exception as e:
        logger.warning(f"Não foi possível reconfigurar a instância central: {e}")


# ==========================================================
# 🟢 NOVA FUNÇÃO: SINCRONIZAÇÃO AUTOMÁTICA DE CONTACTOS
# ==========================================================
def extrair_e_salvar_contactos_auto(tenant_id, instance_name):
    """
    Varre conversas ativas e participantes dos grupos via Evolution API
    e armazena na subcoleção 'base_contactos' do Firestore no perfil do cliente.
    """
    import extensions

    clean_instance = _get_clean_instance(instance_name)
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    base_url = Config.EVOLUTION_API_URL.rstrip('/')
    
    novos_contactos = 0
    tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
    contactos_col = tenant_ref.collection('base_contactos')

    try:
        # 1. Busca conversas ativas (Chats diretos)
        url_chats = f"{base_url}/chat/findChats/{clean_instance}"
        try:
            res_chats = requests.post(url_chats, headers=headers, json={}, timeout=20)
            if res_chats.status_code != 200:
                res_chats = requests.get(url_chats, headers=headers, timeout=20)
        except Exception:
            res_chats = None

        if res_chats and res_chats.status_code == 200:
            chats = res_chats.json()
            if isinstance(chats, list):
                for chat in chats:
                    jid = chat.get("id") or chat.get("remoteJid", "")
                    if jid and jid.endswith("@s.whatsapp.net"):
                        phone = _limpar_numero(jid)
                        nome = chat.get("name") or chat.get("pushName") or "Cliente"
                        if phone and len(phone) >= 8:
                            contactos_col.document(phone).set({
                                "phone": phone,
                                "nome": nome,
                                "origem": "chat_direto"
                            }, merge=True)
                            novos_contactos += 1

        # 2. Busca participantes de Grupos
        url_groups = f"{base_url}/group/fetchAllGroups/{clean_instance}?getParticipants=true"
        try:
            res_groups = requests.get(url_groups, headers=headers, timeout=20)
        except Exception:
            res_groups = None

        if res_groups and res_groups.status_code == 200:
            grupos = res_groups.json()
            if isinstance(grupos, list):
                for grupo in grupos:
                    participants = grupo.get("participants", [])
                    grupo_nome = grupo.get("subject", "Grupo WhatsApp")
                    for p in participants:
                        p_jid = p.get("id") or p.get("jid", "")
                        if p_jid and p_jid.endswith("@s.whatsapp.net"):
                            phone = _limpar_numero(p_jid)
                            if phone and len(phone) >= 8:
                                contactos_col.document(phone).set({
                                    "phone": phone,
                                    "nome": "Membro de Grupo",
                                    "origem": f"grupo_{grupo_nome}"
                                }, merge=True)
                                novos_contactos += 1

        return (
            f"✅ *Sincronização Concluída!*\n\n"
            f"• Contactos guardados/atualizados: *{novos_contactos}*\n\n"
            f"Agora já pode realizar o seu disparo em massa enviando `#disparo <sua mensagem>` sem precisar digitar números."
        )

    except Exception as e:
        logger.error(f"Erro ao extrair contactos da Evolution API para tenant {tenant_id}: {e}", exc_info=True)
        return f"❌ Erro ao sincronizar contactos: {str(e)}"
