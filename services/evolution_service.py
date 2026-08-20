import re
import base64
import json
import logging
import os
import random
import shutil
import subprocess
import tempfile
import threading
import time

import requests
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


MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_AUDIO_DURATION_SECONDS = 300


def _normalizar_audio_para_whisper(media_bytes):
    """Valida e converte áudio para WAV PCM mono 16 kHz sem enviar bytes inválidos ao Groq."""
    if not isinstance(media_bytes, (bytes, bytearray)):
        return b""
    if not media_bytes or len(media_bytes) > MAX_AUDIO_BYTES:
        logger.warning("Áudio rejeitado antes do FFmpeg: tamanho inválido (%s bytes).", len(media_bytes or b""))
        return b""

    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        logger.error("FFmpeg/ffprobe não estão instalados no backend.")
        return b""

    try:
        with tempfile.TemporaryDirectory(prefix="negobot-audio-") as temp_dir:
            source_path = os.path.join(temp_dir, "input.bin")
            output_path = os.path.join(temp_dir, "output.wav")
            with open(source_path, "wb") as source_file:
                source_file.write(media_bytes)

            probe = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=codec_type,codec_name,sample_rate,channels:format=duration",
                    "-of", "json",
                    source_path,
                ],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if probe.returncode != 0:
                logger.warning("Áudio rejeitado pelo ffprobe: %s", probe.stderr[:300])
                return b""

            metadata = json.loads(probe.stdout or "{}")
            streams = metadata.get("streams") or []
            if not streams or streams[0].get("codec_type") != "audio":
                logger.warning("Áudio rejeitado: nenhuma stream de áudio válida foi detetada.")
                return b""

            duration_raw = (metadata.get("format") or {}).get("duration")
            if duration_raw not in (None, "N/A") and float(duration_raw) > MAX_AUDIO_DURATION_SECONDS:
                logger.warning("Áudio rejeitado: duração acima de %s segundos.", MAX_AUDIO_DURATION_SECONDS)
                return b""

            converted = subprocess.run(
                [
                    ffmpeg,
                    "-nostdin",
                    "-v", "error",
                    "-xerror",
                    "-i", source_path,
                    "-map", "0:a:0",
                    "-map_metadata", "-1",
                    "-ac", "1",
                    "-ar", "16000",
                    "-c:a", "pcm_s16le",
                    "-f", "wav",
                    output_path,
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if converted.returncode != 0 or not os.path.exists(output_path):
                logger.warning("Conversão de áudio falhou: %s", converted.stderr[:300])
                return b""

            with open(output_path, "rb") as normalized_file:
                normalized = normalized_file.read()
            if not normalized or len(normalized) > MAX_AUDIO_BYTES:
                logger.warning("Áudio normalizado rejeitado: tamanho inválido (%s bytes).", len(normalized))
                return b""
            if normalized[:4] != b"RIFF" or normalized[8:12] != b"WAVE":
                logger.warning("FFmpeg não produziu um WAV válido.")
                return b""
            return normalized
    except (ValueError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        logger.warning("Falha segura na validação/conversão do áudio: %s", exc)
        return b""


def transcrever_audio_mensagem(data_payload, instance_name=None):
    """Obtém um áudio recebido pela Evolution, normaliza-o e transcreve-o com o Whisper da Groq."""
    try:
        from services.ai_queue_service import request_ai_transcription

        if not isinstance(data_payload, dict):
            return ""
        message = data_payload.get("message") or {}
        audio = message.get("audioMessage") or {}
        if not isinstance(audio, dict):
            return ""

        media_bytes = b""
        media_url = audio.get("url") or audio.get("mediaUrl")
        webhook_base64 = audio.get("base64") or message.get("base64") or data_payload.get("base64")
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        clean_instance = _get_clean_instance(instance_name)
        message_key = data_payload.get("key") or {}
        message_id = str(message_key.get("id") or "")

        if webhook_base64:
            encoded = str(webhook_base64)
            if "," in encoded:
                encoded = encoded.split(",", 1)[1]
            media_bytes = base64.b64decode(encoded, validate=False)
            logger.warning("Áudio obtido diretamente do webhook: bytes=%s", len(media_bytes))
        elif media_url:
            response = requests.get(str(media_url), headers=headers, timeout=45)
            response.raise_for_status()
            media_bytes = response.content
        else:
            request_payload = {
                "message": {
                    "key": {
                        "id": message_key.get("id")
                    }
                },
                "convertToMp4": True
            }
            endpoint = f"{Config.EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{clean_instance}"
            response = requests.post(endpoint, headers=headers, json=request_payload, timeout=45)
            response.raise_for_status()
            result = response.json() or {}
            encoded = result.get("base64") or result.get("data", {}).get("base64")
            if not encoded:
                logger.error("A Evolution não devolveu base64 para o áudio recebido.")
                return ""
            if "," in str(encoded):
                encoded = str(encoded).split(",", 1)[1]
            media_bytes = base64.b64decode(encoded, validate=False)

        normalized_audio = _normalizar_audio_para_whisper(media_bytes)
        if not normalized_audio:
            logger.warning("Áudio inválido ou não recuperável; não enviado ao Groq.")
            return ""
        media_bytes = normalized_audio

        logger.warning("Áudio preparado para Whisper: bytes=%s magic=%s mimetype=%s", len(media_bytes), media_bytes[:12].hex(), "audio/wav")
        transcript_result = request_ai_transcription(
            tenant_id=f"whatsapp_instance:{clean_instance}",
            audio_bytes=media_bytes,
            filename="audio.wav",
            request_id=f"audio:{message_id}" if message_id else None,
        )
        return str(transcript_result.get("text") or "").strip()
    except Exception as exc:
        logger.error("Erro ao obter/transcrever áudio da Evolution: %s", exc)
        return ""


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


def _webhook_payload(webhook_target_url):
    """Constrói o payload compatível com Evolution API v2."""
    return {
        "webhook": {
            "url": webhook_target_url,
            "enabled": True,
            "byEvents": False,
            "base64": False,
            "webhookByEvents": False,
            "events": [
                "MESSAGES_UPSERT",
                "CHATS_UPSERT",
                "CONNECTION_UPDATE",
                "GROUPS_UPSERT",
                "GROUPS_UPDATE",
                "GROUP_PARTICIPANTS_UPDATE"
            ],
            "groupsIgnore": False
        }
    }


def ensure_group_webhook(instance_name):
    """Activa eventos de grupos na instância existente sem recriar a sessão."""
    webhook_target_url = getattr(Config, "WEBHOOK_URL", None)
    if not webhook_target_url:
        return False
    try:
        url = f"{str(Config.EVOLUTION_API_URL).rstrip('/')}/webhook/set/{quote(str(instance_name).strip())}"
        response = requests.post(url, headers={"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}, json=_webhook_payload(webhook_target_url), timeout=30)
        response.raise_for_status()
        logger.info("Webhook de grupos configurado para %s", instance_name)
        return True
    except Exception:
        logger.exception("Não foi possível configurar webhook de grupos para %s", instance_name)
        return False


def criar_e_configurar_instancia_automatica(phone_number):
    """Garante uma instância configurada sem destruir uma sessão existente.

    O endpoint é chamado por pedidos de QR e por confirmações de pagamento, por
    isso deve ser idempotente. A sessão só é criada quando a API devolve 404;
    nunca fazemos logout/delete como parte do fluxo normal do cliente.
    """
    try:
        client_instance_raw = _limpar_numero(phone_number)
        if not client_instance_raw:
            raise ValueError("Número de WhatsApp inválido")
        client_instance = quote(client_instance_raw)
        headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
        base_url = Config.EVOLUTION_API_URL

        state_url = f"{base_url}/instance/connectionState/{client_instance}"
        try:
            state_response = requests.get(state_url, headers=headers, timeout=10)
            instance_exists = state_response.status_code != 404
        except requests.RequestException as state_err:
            logger.warning(f"Não foi possível consultar a instância {client_instance_raw}: {state_err}")
            instance_exists = False

        webhook_target_url = getattr(Config, "WEBHOOK_URL", None)
        webhook_payload = _webhook_payload(webhook_target_url) if webhook_target_url else None

        if not instance_exists:
            # Na Evolution v2.3.7, incluir o bloco webhook no POST de criação
            # pode deixar o endpoint pendurado durante o arranque Baileys.
            # Criamos com o payload mínimo e configuramos o webhook abaixo,
            # numa chamada separada e idempotente.
            payload_create = {
                "instanceName": client_instance_raw,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS"
            }
            res_create = requests.post(
                f"{base_url}/instance/create",
                headers=headers,
                json=payload_create,
                timeout=30,
            )
            res_create.raise_for_status()
            logger.info(f"Instância criada: {client_instance_raw}")
        else:
            logger.info(f"Instância existente reutilizada: {client_instance_raw}")

        try:
            url_settings = f"{base_url}/instance/setSettings/{client_instance}"
            payload_settings = {
                "reject_call": True,
                "msg_call": "",
                "groups_ignore": False,
                "always_online": False,
                "read_messages": True,
                "read_status": False,
                "sync_full_history": False
            }
            requests.post(url_settings, headers=headers, json=payload_settings, timeout=20)
        except Exception as set_err:
            logger.warning(f"Não foi possível aplicar definições na instância: {set_err}")

        if webhook_payload:
            url_webhook = f"{base_url}/webhook/set/{client_instance}"
            res_wh = requests.post(url_webhook, headers=headers, json=webhook_payload, timeout=30)
            res_wh.raise_for_status()
            logger.info(f"Webhook configurado para {client_instance}: {res_wh.status_code}")

        return True
    except Exception as e:
        erro_msg = f"Erro ao automatizar criação/webhook para {phone_number}: {e}"
        logger.error(erro_msg)
        notificar_erro_admin(erro_msg)
        return False


def obter_qrcode_instancia(phone_number):
    """Obtém estado/QR e aguarda a geração assíncrona por alguns segundos."""
    client_instance_raw = _limpar_numero(phone_number)
    if not client_instance_raw:
        raise ValueError("Número de WhatsApp inválido")
    client_instance = quote(client_instance_raw)
    headers = {"apikey": Config.EVOLUTION_API_KEY, "Content-Type": "application/json"}
    url_connect = f"{Config.EVOLUTION_API_URL}/instance/connect/{client_instance}"
    dados_resposta = {}
    for tentativa in range(6):
        response_connect = requests.get(url_connect, headers=headers, timeout=20)
        response_connect.raise_for_status()
        dados_resposta = response_connect.json() or {}
        qrcode_data = dados_resposta.get("qrcode") or {}
        state = dados_resposta.get("instance", {}).get("state") or dados_resposta.get("state") or "connecting"
        base64_qrcode = (
            dados_resposta.get("base64")
            or qrcode_data.get("base64")
            or qrcode_data.get("base64Code")
        )
        if state == "open" or base64_qrcode:
            break
        if tentativa < 5:
            time.sleep(1.5)

    state = dados_resposta.get("instance", {}).get("state") or dados_resposta.get("state") or "connecting"
    qrcode_data = dados_resposta.get("qrcode") or {}
    base64_qrcode = (
        dados_resposta.get("base64")
        or qrcode_data.get("base64")
        or qrcode_data.get("base64Code")
    )
    return {
        "state": state,
        "instance_name": client_instance_raw,
        "base64": base64_qrcode,
        "qrcode_count": qrcode_data.get("count", 0),
    }


def gerar_e_enviar_qrcode_central(phone_number):
    """Solicita a ligação da instância e envia o QR Code ao utilizador."""
    try:
        dados_resposta = obter_qrcode_instancia(phone_number)
        client_instance_raw = dados_resposta["instance_name"]
        if dados_resposta["state"] == "open":
            send_whatsapp(phone_number, "✅ O seu assistente virtual já se encontra ativo e operacional!")
            return True

        base64_qrcode = dados_resposta.get("base64")
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
    """Compatibilidade histórica sem importar participantes para marketing."""
    logger.info("Importação de membros de grupos bloqueada tenant=%s instance=%s", tenant_id, instance_name)
    return "ℹ️ A importação de membros de grupos está desactivada por segurança. Sincroniza apenas os teus Grupos Próprios no painel."


def sincronizar_grupos_destino(tenant_id, instance_name):
    """Compatibilidade histórica: sincroniza apenas grupos próprios verificados."""
    try:
        from services.group_automation_service import sync_groups_for_tenant
        result = sync_groups_for_tenant(tenant_id, instance_name)
        return f"✅ Grupos próprios verificados: {result.get('verified', 0)} de {result.get('total', 0)}. Nenhum membro foi importado."
    except Exception as exc:
        logger.error("Erro ao sincronizar grupos próprios tenant=%s: %s", tenant_id, exc, exc_info=True)
        return "❌ Não foi possível verificar os grupos próprios."


def extrair_e_salvar_contactos_auto(tenant_id, instance_name):
    """Sincroniza conversas privadas e grupos próprios, sem importar participantes."""
    extrair_contactos_conversas(tenant_id, instance_name)
    group_result = sincronizar_grupos_destino(tenant_id, instance_name)
    return f"✅ *Sincronização concluída!*\n\n{group_result}\n\nOs membros dos grupos não são usados como contactos privados."


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
    """Worker legado que publica somente em grupos próprios verificados."""
    import extensions
    from services.group_automation_service import authorized_group_jids
    clean_instance = _get_clean_instance(instance_name)
    grupos = authorized_group_jids(tenant_id, clean_instance)
    sucessos = 0
    falhas = 0

    for group_jid in grupos:
        if send_whatsapp(group_jid, mensagem, instance_name=clean_instance):
            sucessos += 1
        else:
            falhas += 1
        time.sleep(random.uniform(5.0, 10.0))

    relatorio = (
        f"🚀 *Disparo em Grupos Finalizado!*\n\n"
        f"✅ Publicado em: *{sucessos} grupos próprios*\n"
        f"❌ Falhas: *{falhas}*"
    )
    send_whatsapp(tenant_id, relatorio, instance_name=clean_instance)


def enviar_disparo_grupos(tenant_id, instance_name, mensagem):
    if not mensagem or not mensagem.strip():
        return "⚠️ Escreva a mensagem que deseja publicar nos grupos. Exemplo:\n`#disparo_grupos Olá a todos!`"

    thread = threading.Thread(target=_worker_disparo_grupos, args=(tenant_id, instance_name, mensagem))
    thread.start()

    return "⏳ *Disparo em Grupos Iniciado!*\n\nAs publicações estão a ser efetuadas com intervalos de segurança em segundo plano."
