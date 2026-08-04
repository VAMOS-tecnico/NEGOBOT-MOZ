import re
import time
import random
import threading
import requests
import logging
from urllib.parse import quote
from config import Config

logger = logging.getLogger(__name__)


def _get_clean_instance(instance_name=None):
    """Sanitiza e codifica o nome da instância para evitar erros de URL."""
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
            requests.post(url, headers=headers, json=payload, timeout=30)
        except Exception as e:
            logger.error(f"Falha ao enviar notificação de erro ao admin: {e}")


def send_whatsapp(to, text, instance_name=None):
    """Envia uma mensagem de texto via Evolution API para números ou grupos (@g.us)."""
    if not text or not str(text).strip():
        return False

    is_group = str(to).endswith('@g.us')
    clean_target = str(to).strip() if is_group else _limpar_numero(to)
    
    if not clean_target:
        logger.error(f"Destino inválido fornecido para envio: '{to}'")
        return False

    clean_instance = _get_clean_instance(instance_name)
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    url = f"{Config.EVOLUTION_API_URL}/message/sendText/{clean_instance}"
    
    payload_v2 = {
        "number": clean_target,
        "text": str(text).strip(),
        "delay": 1200
    }

    try:
        res = requests.post(url, headers=headers, json=payload_v2, timeout=45)
        
        if res.status_code == 400:
            logger.warning(f"Tentativa v2 retornou 400. Tentando payload v1 para {clean_target}...")
            payload_v1 = {
                "number": clean_target,
                "options": {"delay": 1200},
                "textMessage": {"text": str(text).strip()}
            }
            res = requests.post(url, headers=headers, json=payload_v1, timeout=45)

        res.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"ERRO ao enviar mensagem via Evolution API ({url}): {e}")
        return False


def send_media(to, media, caption="", mediatype="image", filename="media.png", instance_name=None):
    """Função de atalho compatível para envio de mídias exigida pelo central_flow."""
    try:
        is_group = str(to).endswith('@g.us')
        clean_target = str(to).strip() if is_group else _limpar_numero(to)
        clean_instance = _get_clean_instance(instance_name)
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        
        if media and "," in str(media):
            media = str(media).split(",")[1]

        url_send_media = f"{Config.EVOLUTION_API_URL}/message/sendMedia/{clean_instance}"
        payload = {
            "number": clean_target,
            "caption": caption,
            "media": media,
            "mediatype": mediatype,
            "fileName": filename,
            "delay": 1200
        }
        res = requests.post(url_send_media, headers=headers, json=payload, timeout=45)
        res.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Erro em send_media: {e}")
        return False


def criar_e_configurar_instancia_automatica(phone_number):
    """Cria e configura o webhook + definições de instância."""
    try:
        client_instance_raw = _limpar_numero(phone_number)
        client_instance = quote(client_instance_raw)
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        
        try:
            requests.delete(f"{Config.EVOLUTION_API_URL}/instance/logout/{client_instance}", headers=headers, timeout=15)
            requests.delete(f"{Config.EVOLUTION_API_URL}/instance/delete/{client_instance}", headers=headers, timeout=15)
        except Exception:
            pass
        
        time.sleep(2)
        
        url_create = f"{Config.EVOLUTION_API_URL}/instance/create"
        payload_create = {
            "instanceName": client_instance_raw, 
            "qrcode": True, 
            "integration": "WHATSAPP-BAILEYS"
        }
        res_create = requests.post(url_create, headers=headers, json=payload_create, timeout=30)
        res_create.raise_for_status()
        
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
            requests.post(url_settings, headers=headers, json=payload_settings, timeout=20)
        except Exception as set_err:
            logger.warning(f"Não foi possível aplicar definições na instância: {set_err}")

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
            res_wh = requests.post(url_webhook, headers=headers, json=payload_webhook, timeout=30)
            logger.info(f"Webhook configurado para {client_instance}: {res_wh.status_code}")

        return True
    except Exception as e:
        erro_msg = f"Erro ao automatizar criação/webhook para {phone_number}: {e}"
        logger.error(erro_msg)
        notificar_erro_admin(erro_msg)
        return False


def gerar_e_enviar_qrcode_central(phone_number):
    """Solicita a ligação da instância e envia o QR Code ao utilizador."""
    try:
        client_instance_raw = _limpar_numero(phone_number)
        client_instance = quote(client_instance_raw)
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        
        url_connect = f"{Config.EVOLUTION_API_URL}/instance/connect/{client_instance}"
        response_connect = requests.get(url_connect, headers=headers, timeout=35)
        response_connect.raise_for_status()
        
        dados_resposta = response_connect.json()
        if dados_resposta.get("instance", {}).get("state") == "open":
            send_whatsapp(phone_number, "✅ O seu assistente virtual já se encontra ativo e operacional!")
            return True
            
        base64_qrcode = dados_resposta.get("base64") or dados_resposta.get("qrcode", {}).get("base64")
        if not base64_qrcode:
            logger.error(f"Nenhum QR Code retornado para a instância {client_instance_raw}")
            return False

        caption_text = (
            "🤖 *Aqui está o seu QR Code do Negobot Moz!* 🚀\n\n"
            "1️⃣ Abra o WhatsApp que vai atender os seus clientes.\n"
            "2️⃣ Vá a *Aparelhos Conectados* -> *Conectar um aparelho*.\n"
            "3️⃣ Aponte a câmara e escaneie *imediatamente* este QR Code.\n\n"
            "Se expirar, digite *#qrcode* aqui para gerar um novo!"
        )
        
        send_media(
            to=phone_number,
            media=base64_qrcode,
            caption=caption_text,
            mediatype="image",
            filename="qrcode.png",
            instance_name=_get_clean_instance()
        )
        return True
    except Exception as e:
        logger.error(f"Erro ao gerar QR Code para {phone_number}: {e}")
        return False


# ==========================================================
# 🟢 SINCRONIZAÇÃO E EXTRAÇÃO DE CONTATOS/GRUPOS
# ==========================================================

def extrair_contactos_conversas(tenant_id, instance_name):
    import extensions
    clean_instance = _get_clean_instance(instance_name)
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    base_url = Config.EVOLUTION_API_URL.rstrip('/')
    
    novos_contactos = 0
    tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
    contactos_col = tenant_ref.collection('base_contactos')

    try:
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
                                "origem": "chat_direto",
                                "atualizado_em": time.time()
                            }, merge=True)
                            novos_contactos += 1

        return (
            f"✅ *Conversas Privadas Sincronizadas!*\n\n"
            f"• Total de contactos de conversas guardados: *{novos_contactos}*\n\n"
            f"Já pode enviar a sua campanha privada enviando:\n`#disparo <sua mensagem>`"
        )
    except Exception as e:
        logger.error(f"Erro ao extrair conversas para tenant {tenant_id}: {e}", exc_info=True)
        return f"❌ Erro ao sincronizar conversas: {str(e)}"


def extrair_contactos_grupos(tenant_id, instance_name):
    import extensions
    clean_instance = _get_clean_instance(instance_name)
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    base_url = Config.EVOLUTION_API_URL.rstrip('/')
    
    novos_contactos = 0
    tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
    contactos_col = tenant_ref.collection('base_contactos')

    try:
        url_groups = f"{base_url}/group/fetchAllGroups/{clean_instance}?getParticipants=true"
        res_groups = requests.get(url_groups, headers=headers, timeout=25)

        if res_groups.status_code == 200:
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
                                    "origem": f"grupo_{grupo_nome}",
                                    "atualizado_em": time.time()
                                }, merge=True)
                                novos_contactos += 1

        return (
            f"✅ *Membros dos Grupos Sincronizados!*\n\n"
            f"• Total de membros de grupos guardados: *{novos_contactos}*\n\n"
            f"Já pode enviar a sua campanha privada enviando:\n`#disparo <sua mensagem>`"
        )
    except Exception as e:
        logger.error(f"Erro ao extrair grupos para tenant {tenant_id}: {e}", exc_info=True)
        return f"❌ Erro ao sincronizar membros de grupos: {str(e)}"


def sincronizar_grupos_destino(tenant_id, instance_name):
    import extensions
    clean_instance = _get_clean_instance(instance_name)
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    base_url = Config.EVOLUTION_API_URL.rstrip('/')
    
    tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
    grupos_col = tenant_ref.collection('base_grupos')

    try:
        url_groups = f"{base_url}/group/fetchAllGroups/{clean_instance}?getParticipants=false"
        res_groups = requests.get(url_groups, headers=headers, timeout=25)

        total_grupos = 0
        if res_groups.status_code == 200:
            grupos = res_groups.json()
            if isinstance(grupos, list):
                for grupo in grupos:
                    group_jid = grupo.get("id") or grupo.get("jid", "")
                    group_nome = grupo.get("subject", "Grupo Sem Nome")
                    
                    if group_jid and group_jid.endswith("@g.us"):
                        doc_id = group_jid.replace('@', '_').replace('.', '_')
                        grupos_col.document(doc_id).set({
                            "jid": group_jid,
                            "nome": group_nome,
                            "atualizado_em": time.time()
                        }, merge=True)
                        total_grupos += 1

        return (
            f"✅ *Grupos Mapeados com Sucesso!*\n\n"
            f"• Total de grupos prontos para receber mensagens: *{total_grupos}*\n\n"
            f"Para enviar uma mensagem direta nestes grupos, use:\n"
            f"`#disparo_grupos <sua mensagem>`"
        )
    except Exception as e:
        logger.error(f"Erro ao mapear grupos para tenant {tenant_id}: {e}", exc_info=True)
        return f"❌ Erro ao mapear grupos: {str(e)}"


def extrair_e_salvar_contactos_auto(tenant_id, instance_name):
    """Executa a sincronização completa de conversas, membros de grupos e mapeamento."""
    extrair_contactos_conversas(tenant_id, instance_name)
    extrair_contactos_grupos(tenant_id, instance_name)
    sincronizar_grupos_destino(tenant_id, instance_name)

    return (
        f"✅ *Sincronização Completa Concluída!*\n\n"
        f"• As suas conversas privadas, contactos de grupos e a lista de grupos foram atualizadas.\n\n"
        f"Comandos disponíveis:\n"
        f"• `#disparo <mensagem>` -> Envia no privado.\n"
        f"• `#disparo_grupos <mensagem>` -> Publica nos grupos."
    )


# ==========================================================
# 🟢 DISPAROS EM MASSA (COM ANTI-SPAM E WORKER ASYNC)
# ==========================================================

def _worker_disparo_privado(tenant_id, instance_name, mensagem):
    """Worker executado em thread separada para evitar timeout do HTTP."""
    import extensions
    clean_instance = _get_clean_instance(instance_name)
    tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
    contactos = list(tenant_ref.collection('base_contactos').stream())

    sucessos = 0
    falhas = 0

    for doc in contactos:
        dados = doc.to_dict()
        phone = dados.get("phone")
        if not phone:
            continue

        if send_whatsapp(phone, mensagem, instance_name=clean_instance):
            sucessos += 1
        else:
            falhas += 1

        time.sleep(random.uniform(3.0, 7.0))

    relatorio = (
        f"🚀 *Disparo Privado Finalizado!*\n\n"
        f"✅ Enviado com sucesso: *{sucessos}*\n"
        f"❌ Falhas: *{falhas}*"
    )
    send_whatsapp(tenant_id, relatorio, instance_name=clean_instance)


def enviar_disparo_privado(tenant_id, instance_name, mensagem):
    if not mensagem or not mensagem.strip():
        return "⚠️ Escreva a mensagem que deseja enviar. Exemplo:\n`#disparo Olá! Temos novidades.`"

    thread = threading.Thread(target=_worker_disparo_privado, args=(tenant_id, instance_name, mensagem))
    thread.start()

    return "⏳ *Disparo Privado Iniciado!*\n\nO processo está a decorrer em segundo plano para proteção da conta. Receberá um relatório quando terminar."


def _worker_disparo_grupos(tenant_id, instance_name, mensagem):
    """Worker executado em thread separada para envios em grupo."""
    import extensions
    clean_instance = _get_clean_instance(instance_name)
    tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
    grupos = list(tenant_ref.collection('base_grupos').stream())

    sucessos = 0
    falhas = 0

    for doc in grupos:
        dados = doc.to_dict()
        group_jid = dados.get("jid")
        if not group_jid:
            continue

        if send_whatsapp(group_jid, mensagem, instance_name=clean_instance):
            sucessos += 1
        else:
            falhas += 1

        time.sleep(random.uniform(5.0, 10.0))

    relatorio = (
        f"🚀 *Disparo em Grupos Finalizado!*\n\n"
        f"✅ Publicado em: *{sucessos} grupos*\n"
        f"❌ Falhas: *{falhas}*"
    )
    send_whatsapp(tenant_id, relatorio, instance_name=clean_instance)


def enviar_disparo_grupos(tenant_id, instance_name, mensagem):
    if not mensagem or not mensagem.strip():
        return "⚠️ Escreva a mensagem que deseja publicar nos grupos. Exemplo:\n`#disparo_grupos Olá a todos!`"

    thread = threading.Thread(target=_worker_disparo_grupos, args=(tenant_id, instance_name, mensagem))
    thread.start()

    return "⏳ *Disparo em Grupos Iniciado!*\n\nAs publicações estão a ser efetuadas com intervalos de segurança em segundo plano."
