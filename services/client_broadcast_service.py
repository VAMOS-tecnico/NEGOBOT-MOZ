import time
import logging
import extensions
from services.evolution_service import send_whatsapp

logger = logging.getLogger(__name__)

def processar_disparo_cliente(tenant_id, client_phone, message_text, instance_name):
    """
    Processa o comando de disparo em massa enviado pelo dono da empresa (cliente).
    Valida se o cliente está no Plano Premium (1.500 MT) antes de executar.
    """
    try:import time
import re
import logging
import threading
import extensions
from services.evolution_service import send_whatsapp

logger = logging.getLogger(__name__)

def _worker_executar_disparos(destinatarios, grupos, mensagem_campanha, instance_name, client_phone, total_alvos):
    """
    Função executada em segundo plano para enviar as mensagens sem bloquear o servidor.
    """
    sucessos = 0
    
    # 1. Envio para os contactos individuais
    for dest in destinatarios:
        try:
            # Sanitiza o número garantindo apenas dígitos
            clean_dest = re.sub(r'\D', '', str(dest))
            if clean_dest:
                send_whatsapp(clean_dest, mensagem_campanha, instance_name=instance_name)
                sucessos += 1
                time.sleep(4)
        except Exception as e:
            logger.error(f"Erro ao enviar disparo para contacto {dest}: {e}")

    # 2. Envio para os grupos
    for grupo in grupos:
        try:
            send_whatsapp(grupo, mensagem_campanha, instance_name=instance_name)
            sucessos += 1
            time.sleep(5)
        except Exception as e:
            logger.error(f"Erro ao enviar disparo para grupo {grupo}: {e}")

    # 3. Notifica o dono da empresa diretamente no WhatsApp após finalizar
    relatorio = (
        f"✅ *Campanha Concluída com Sucesso!*\n\n"
        f"Mensagem enviada para *{sucessos} de {total_alvos}* destinatários (contactos e grupos)."
    )
    try:
        send_whatsapp(client_phone, relatorio, instance_name=instance_name)
    except Exception as e:
        logger.error(f"Erro ao enviar relatório de término para {client_phone}: {e}")


def processar_disparo_cliente(tenant_id, client_phone, message_text, instance_name):
    """
    Processa o comando de disparo em massa enviado pelo dono da empresa (cliente).
    Valida o plano e inicia o envio em background.
    """
    try:
        # 1. Verificar o plano do cliente no Firestore
        tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
        tenant_doc = tenant_ref.get()
        
        if not tenant_doc.exists:
            return "❌ Conta não encontrada no sistema Negobot Moz."
            
        tenant_data = tenant_doc.to_dict() or {}
        plano_atual = str(tenant_data.get('plano', tenant_data.get('status_plano', 'basico'))).lower()
        
        # 2. Regra de Bloqueio: Apenas Plano Premium (1.500 MT) ou Demonstração ativa
        is_premium = "premium" in plano_atual or "1500" in plano_atual or "demonstracao" in plano_atual
        
        if not is_premium:
            return (
                "❌ *Ferramenta Bloqueada!*\n\n"
                "Os **Disparos em Massa** para contactos e grupos estão disponíveis exclusivamente no *Plano Premium (1.500 MT)*.\n\n"
                "Digite *UPGRADE* ou entre em contacto com a central para atualizar o seu plano."
            )

        # 3. Extrair a mensagem após o comando (ex: "#disparo Promoção...")
        partes = message_text.split(maxsplit=1)
        if len(partes) < 2:
            return (
                "⚠️ *Uso incorreto do comando.*\n\n"
                "Para fazer um disparo, escreva o comando seguido da mensagem que deseja enviar.\n"
                "Exemplo: `#disparo Olá! Temos novidades e descontos imperdíveis esta semana na nossa loja.`"
            )
            
        mensagem_campanha = partes[1].strip()

        # 4. Buscar contactos e grupos guardados
        contactos_ref = tenant_ref.collection('base_contactos').stream()
        destinatarios = [doc.to_dict().get('phone') for doc in contactos_ref if doc.to_dict().get('phone')]
        
        grupos_ref = tenant_ref.collection('grupos_autorizados').stream()
        grupos = [doc.to_dict().get('group_jid') for doc in grupos_ref if doc.to_dict().get('group_jid')]

        total_alvos = len(destinatarios) + len(grupos)
        if total_alvos == 0:
            return (
                "⚠️ *Nenhum contacto ou grupo encontrado na sua base de dados.*\n"
                "Carregue primeiro a sua lista de contactos para o sistema antes de iniciar a campanha."
            )

        # 5. Iniciar o disparo em Segundo Plano (Thread) para não travar o servidor
        thread_disparo = threading.Thread(
            target=_worker_executar_disparos,
            args=(destinatarios, grupos, mensagem_campanha, instance_name, client_phone, total_alvos),
            daemon=True
        )
        thread_disparo.start()

        # Resposta imediata confirmando o início da operação
        return (
            f"🚀 *Campanha iniciada com sucesso!*\n\n"
            f"A processar o envio para *{len(destinatarios)} contactos* e *{len(grupos)} grupos* em segundo plano.\n"
            f"Receberá uma notificação aqui assim que a campanha for concluída."
        )

    except Exception as e:
        logger.error(f"Erro crítico no processar_disparo_cliente para {tenant_id}: {e}", exc_info=True)
        return "❌ Ocorreu um erro interno ao processar a sua campanha de disparos."
        # 1. Verificar o plano do cliente no Firestore
        tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
        tenant_doc = tenant_ref.get()
        
        if not tenant_doc.exists:
            return "❌ Conta não encontrada no sistema Negobot Moz."
            
        tenant_data = tenant_doc.to_dict()
        plano_atual = str(tenant_data.get('plano', tenant_data.get('status_plano', 'basico'))).lower()
        
        # 2. Regra de Bloqueio: Apenas Plano Premium (1.500 MT) ou Demonstração ativa
        is_premium = "premium" in plano_atual or "1500" in plano_atual or "demonstracao" in plano_atual
        
        if not is_premium:
            return (
                "❌ *Ferramenta Bloqueada!*\n\n"
                "Os **Disparos em Massa** para contactos e grupos estão disponíveis exclusivamente no *Plano Premium (1.500 MT)*.\n\n"
                "Digite *UPGRADE* ou entre em contacto com a central para atualizar o seu plano."
            )

        # 3. Extrair a mensagem após o comando (ex: "#disparo Promoção de hoje...")
        partes = message_text.split(maxsplit=1)
        if len(partes) < 2:
            return (
                "⚠️ *Uso incorreto do comando.*\n\n"
                "Para fazer um disparo, escreva o comando seguido da mensagem que deseja enviar.\n"
                "Exemplo: `#disparo Olá! Temos novidades e descontos imperdíveis esta semana na nossa loja.`"
            )
            
        mensagem_campanha = partes[1].strip()

        # 4. Buscar a lista de contactos e grupos guardados do cliente
        # (Podes adaptar esta parte para puxar de uma subcolecção 'contactos' do tenant no Firestore)
        contactos_ref = extensions.db.collection('clientes_bot').document(tenant_id).collection('base_contactos').stream()
        destinatarios = [doc.to_dict().get('phone') for doc in contactos_ref if doc.to_dict().get('phone')]
        
        # Grupos salvos do cliente (se aplicável)
        grupos_ref = extensions.db.collection('clientes_bot').document(tenant_id).collection('grupos_autorizados').stream()
        grupos = [doc.to_dict().get('group_jid') for doc in grupos_ref if doc.to_dict().get('group_jid')]

        total_alvos = len(destinatarios) + len(grupos)
        if total_alvos == 0:
            return (
                "⚠️ *Nenhum contacto ou grupo encontrado na sua base de dados.*\n"
                "Carregue primeiro a sua lista de contactos para o sistema antes de iniciar a campanha."
            )

        # Resposta imediata a avisar que o processo começou
        send_whatsapp(client_phone, f"🚀 *Campanha iniciada!* A enviar para {len(destinatarios)} contactos e {len(grupos)} grupos de forma segura.", instance_name=instance_name)

        sucessos = 0
        
        # 5. Envio com intervalo de segurança para evitar banimento da Meta (anti-spam)
        # Envia para contactos individuais
        for dest in destinatarios:
            try:
                send_whatsapp(dest, mensagem_campanha, instance_name=instance_name)
                sucessos += 1
                time.sleep(4) # Pausa de 4 segundos entre cada mensagem individual
            except Exception as e:
                logger.error(f"Erro ao enviar para o contacto {dest}: {e}")

        # Envia para grupos
        for grupo in grupos:
            try:
                send_whatsapp(grupo, mensagem_campanha, instance_name=instance_name)
                sucessos += 1
                time.sleep(5) # Pausa de 5 segundos para grupos
            except Exception as e:
                logger.error(f"Erro ao enviar para o grupo {grupo}: {e}")

        return f"✅ *Campanha Concluída com Sucesso!*\n\nMensagem enviada para {sucessos} de {total_alvos} destinatários (contactos e grupos)."

    except Exception as e:
        logger.error(f"Erro crítico no processar_disparo_cliente para {tenant_id}: {e}", exc_info=True)
        return "❌ Ocorreu um erro interno ao processar a sua campanha de disparos."
