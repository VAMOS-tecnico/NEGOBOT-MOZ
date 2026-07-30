import time
import re
import logging
import threading
import extensions
from services.evolution_service import send_whatsapp

logger = logging.getLogger(__name__)

# Configuração dos tempos de pausa (segurança anti-bloqueio)
PAUSA_CONTATO_SEG = 4
PAUSA_GRUPO_SEG = 5

def _worker_executar_disparos(destinatarios, grupos, mensagem_campanha, instance_name, client_phone, total_alvos):
    """
    Função executada em segundo plano (background thread) para enviar as mensagens.
    Garante que o servidor não sofra timeout HTTP enquanto processa a fila.
    """
    sucessos = 0
    
    # 1. Envio para contactos individuais
    for dest in destinatarios:
        try:
            clean_dest = re.sub(r'\D', '', str(dest))
            if clean_dest:
                send_whatsapp(clean_dest, mensagem_campanha, instance_name=instance_name)
                sucessos += 1
                time.sleep(PAUSA_CONTATO_SEG)
        except Exception as e:
            logger.error(f"Erro ao enviar disparo para contacto {dest}: {e}")

    # 2. Envio para grupos
    for grupo in grupos:
        try:
            send_whatsapp(grupo, mensagem_campanha, instance_name=instance_name)
            sucessos += 1
            time.sleep(PAUSA_GRUPO_SEG)
        except Exception as e:
            logger.error(f"Erro ao enviar disparo para grupo {grupo}: {e}")

    # 3. Notificação e relatório final ao cliente
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
    Valida o plano do cliente no Firestore e inicia a execução em background.
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

        # 3. Extrair a mensagem após o comando (ex: "#disparo Promoção de hoje...")
        partes = message_text.split(maxsplit=1)
        if len(partes) < 2:
            return (
                "⚠️ *Uso incorreto do comando.*\n\n"
                "Para fazer um disparo, escreva o comando seguido da mensagem que deseja enviar.\n"
                "Exemplo: `#disparo Olá! Temos novidades e descontos imperdíveis esta semana na nossa loja.`"
            )
            
        mensagem_campanha = partes[1].strip()

        # 4. Buscar contactos e grupos guardados no Firestore
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

        # Resposta imediata de confirmação
        return (
            f"🚀 *Campanha iniciada com sucesso!*\n\n"
            f"A processar o envio para *{len(destinatarios)} contactos* e *{len(grupos)} grupos* em segundo plano.\n"
            f"Receberá uma notificação aqui assim que a campanha for concluída."
        )

    except Exception as e:
        logger.error(f"Erro crítico no processar_disparo_cliente para {tenant_id}: {e}", exc_info=True)
        return "❌ Ocorreu um erro interno ao processar a sua campanha de disparos."
