import logging
from services.evolution_service import (
    send_whatsapp, 
    send_media, 
    gerar_e_enviar_qrcode_central, 
    extrair_e_salvar_contactos_auto, 
    enviar_disparo_privado, 
    enviar_disparo_grupos
)

logger = logging.getLogger(__name__)

def process_central_flow(data):
    """
    Função principal chamada pelas rotas de webhook para processar 
    as mensagens recebidas da Evolution API e gerir os comandos do Negobot Moz.
    """
    try:
        # 1. Validar se o evento recebido é do tipo messages.upsert
        event = data.get("event")
        if event != "messages.upsert":
            return {"status": "ignored", "reason": "event_not_supported"}

        data_body = data.get("data", {})
        key = data_body.get("key", {})
        
        # Ignorar mensagens enviadas pelo próprio bot para evitar loops
        if key.get("fromMe", False):
            return {"status": "ignored", "reason": "message_from_me"}

        remote_jid = key.get("remoteJid", "")
        
        # Identificar se é grupo ou chat privado
        is_group = remote_jid.endswith("@g.us")
        sender_phone = remote_jid.split("@")[0] if not is_group else remote_jid

        if not sender_phone:
            return {"status": "ignored", "reason": "invalid_sender"}

        # 2. Extrair o texto da mensagem
        message_content = data_body.get("message", {})
        text_msg = (
            message_content.get("conversation") or 
            message_content.get("extendedTextMessage", {}).get("text") or 
            ""
        ).strip()

        if not text_msg:
            return {"status": "ignored", "reason": "empty_text"}

        logger.info(f"Mensagem processada de {sender_phone} (Grupo: {is_group}): {text_msg}")

        # O tenant_id para o Firestore utiliza o número de telefone
        tenant_id = sender_phone 

        # 3. Processamento de Comandos do Bot
        if text_msg.startswith("#qrcode"):
            gerar_e_enviar_qrcode_central(sender_phone)
            return {"status": "success", "command": "qrcode"}

        elif text_msg.startswith("#sincronizar"):
            resposta_sinc = extrair_e_salvar_contactos_auto(tenant_id, sender_phone)
            send_whatsapp(sender_phone, resposta_sinc)
            return {"status": "success", "command": "sincronizar"}

        elif text_msg.startswith("#disparo "):
            conteudo_disparo = text_msg.replace("#disparo", "", 1).strip()
            resposta_disp = enviar_disparo_privado(tenant_id, sender_phone, conteudo_disparo)
            send_whatsapp(sender_phone, resposta_disp)
            return {"status": "success", "command": "disparo_privado"}

        elif text_msg.startswith("#disparo_grupos "):
            conteudo_grupos = text_msg.replace("#disparo_grupos", "", 1).strip()
            resposta_grup = enviar_disparo_grupos(tenant_id, sender_phone, conteudo_grupos)
            send_whatsapp(sender_phone, resposta_grup)
            return {"status": "success", "command": "disparo_grupos"}

        else:
            # Resposta de ajuda automática para mensagens diretas sem comandos
            if not is_group:
                ajuda_txt = (
                    "🤖 *Assistente Virtual - Negobot Moz*\n\n"
                    "Comandos disponíveis:\n"
                    "• `#qrcode` - Gera o QR Code de ligação\n"
                    "• `#sincronizar` - Atualiza contactos e grupos\n"
                    "• `#disparo <msg>` - Faz campanha privada\n"
                    "• `#disparo_grupos <msg>` - Publica em massa nos grupos"
                )
                send_whatsapp(sender_phone, ajuda_txt)

        return {"status": "success", "processed": True}

    except Exception as e:
        logger.error(f"Erro crítico no process_central_flow: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500
