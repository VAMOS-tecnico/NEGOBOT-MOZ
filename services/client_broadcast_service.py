import time
import re
import logging
import threading
from datetime import datetime, timezone
import extensions
from services.evolution_service import send_whatsapp

logger = logging.getLogger(__name__)

# Configuração dos tempos de pausa (segurança anti-bloqueio WhatsApp)
PAUSA_CONTATO_SEG = 4
PAUSA_GRUPO_SEG = 5


def formatar_numero_mocambique(phone_str):
    """Garante que o número de telefone tenha o formato completo com DDI 258."""
    clean = re.sub(r'\D', '', str(phone_str or ''))
    if len(clean) == 9 and clean.startswith(('84', '85', '86', '87')):
        return f"258{clean}"
    return clean


def _worker_executar_disparos(destinatarios, grupos, mensagem_campanha, instance_name, client_phone, total_alvos):
    """
    Função executada em segundo plano (background thread) para enviar as mensagens.
    Garante que o servidor não sofra timeout HTTP enquanto processa a fila.
    """
    sucessos = 0
    falhas = 0
    
    # 1. Envio para contactos individuais
    for dest in destinatarios:
        try:
            clean_dest = formatar_numero_mocambique(dest)
            if clean_dest:
                res = send_whatsapp(clean_dest, mensagem_campanha, instance_name=instance_name)
                # Assume sucesso se não disparar exceção
                sucessos += 1
                time.sleep(PAUSA_CONTATO_SEG)
            else:
                falhas += 1
        except Exception as e:
            falhas += 1
            logger.error(f"Erro ao enviar disparo para contacto {dest}: {e}")

    # 2. Envio para grupos
    for grupo in grupos:
        try:
            if grupo:
                send_whatsapp(grupo, mensagem_campanha, instance_name=instance_name)
                sucessos += 1
                time.sleep(PAUSA_GRUPO_SEG)
            else:
                falhas += 1
        except Exception as e:
            falhas += 1
            logger.error(f"Erro ao enviar disparo para grupo {grupo}: {e}")

    # 3. Notificação e relatório final ao cliente
    relatorio = (
        f"📊 *RELATÓRIO FINAL DA CAMPANHA*\n\n"
        f"• *Total de Alvos:* {total_alvos}\n"
        f"• *Entregues com Sucesso:* ✅ {sucessos}\n"
        f"• *Falhas de Envio:* ❌ {falhas}\n\n"
        f"Campanha concluída com sucesso pelo **Negobot Moz**! 🚀"
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
        agora = datetime.now(timezone.utc)

        # 1. Verificar o plano e estado da licença no Firestore
        tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
        tenant_doc = tenant_ref.get()
        
        if not tenant_doc.exists:
            return "❌ Conta não encontrada no sistema Negobot Moz."
            
        tenant_data = tenant_doc.to_dict() or {}
        
        # 2. Validação Estrita de Licença e Expiração
        disparo_liberado = tenant_data.get('disparo_liberado', False)
        status_plano = str(tenant_data.get('status_plano', '')).lower()
        data_expiracao = tenant_data.get('data_expiracao')

        # Converte timezone para comparação
        if data_expiracao and data_expiracao.tzinfo is None:
            data_expiracao = data_expiracao.replace(tzinfo=timezone.utc)

        # Se a conta estiver expirada, bloqueia imediatamente
        if data_expiracao and agora > data_expiracao:
            return (
                "⚠️ *Sua Licença Expirou!*\n\n"
                "O seu plano atual encontra-se expirado. Para realizar novos disparos em massa, "
                "por favor efetue o pagamento da renovação via M-Pesa."
            )

        # Regra de permissão do recurso
        pode_disparar = disparo_liberado or status_plano == "demonstracao" or "premium" in str(tenant_data.get('plano', '')).lower()

        if not pode_disparar:
            return (
                "❌ *Ferramenta Bloqueada!*\n\n"
                "Os **Disparos em Massa** para contactos e grupos estão disponíveis exclusivamente no *Plano Premium (1.500 MT)*.\n\n"
                "Entre em contacto com a central do Negobot Moz para efetuar o upgrade da sua conta."
            )

        # 3. Extrair a mensagem após o comando (ex: "#disparo Promoção de hoje...")
        partes = message_text.split(maxsplit=1)
        if len(partes) < 2:
            return (
                "⚠️ *Uso incorreto do comando.*\n\n"
                "Para fazer um disparo, escreva o comando seguido da mensagem que deseja enviar.\n\n"
                " Exemplo:\n"
                "`#disparo Olá! Temos novidades e descontos imperdíveis esta semana na nossa loja.`"
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
                "⚠️ *Nenhum contacto ou grupo encontrado na sua base de dados.*\n\n"
                "Carregue primeiro a sua lista de contactos no sistema antes de iniciar a campanha."
            )

        # 5. Iniciar o disparo em Segundo Plano (Thread)
        thread_disparo = threading.Thread(
            target=_worker_executar_disparos,
            args=(destinatarios, grupos, mensagem_campanha, instance_name, client_phone, total_alvos),
            daemon=True
        )
        thread_disparo.start()

        # Resposta imediata de confirmação
        return (
            f"🚀 *Campanha iniciada com sucesso!*\n\n"
            f"• *Contactos:* {len(destinatarios)}\n"
            f"• *Grupos:* {len(grupos)}\n"
            f"• *Total de Envios:* {total_alvos}\n\n"
            f"O envio está a ser feito em segundo plano com pausas de segurança anti-bloqueio.\n"
            f"Receberá o relatório final assim que terminar!"
        )

    except Exception as e:
        logger.error(f"Erro crítico no processar_disparo_cliente para {tenant_id}: {e}", exc_info=True)
        return "❌ Ocorreu um erro interno ao processar a sua campanha de disparos."
