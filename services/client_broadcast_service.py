import time
import re
import logging
import threading
from datetime import datetime, timezone
import extensions
from services.evolution_service import send_whatsapp

logger = logging.getLogger(__name__)

# Pausas de segurança anti-bloqueio WhatsApp
PAUSA_CONTATO_SEG = 4
PAUSA_GRUPO_SEG = 5


def formatar_numero_mocambique(phone_str):
    """Garante que o número de telefone tenha apenas dígitos e o DDI 258."""
    clean = re.sub(r'\D', '', str(phone_str or ''))
    if len(clean) == 9 and clean.startswith(('84', '85', '86', '87')):
        return f"258{clean}"
    return clean


def _worker_executar_disparos(destinatarios, grupos, mensagem_campanha, instance_name, client_phone, total_alvos):
    """
    Função executada em segundo plano (thread daemon) para envio massivo sem bloquear o servidor.
    """
    sucessos = 0
    falhas = 0

    # 1. Envio para contactos individuais (com suporte a {nome})
    for dest in destinatarios:
        try:
            phone_bruto = dest.get("telefone") if isinstance(dest, dict) else dest
            nome_contacto = dest.get("nome", "Cliente") if isinstance(dest, dict) else "Cliente"

            clean_dest = formatar_numero_mocambique(phone_bruto)
            if clean_dest:
                # Substitui {nome} de forma personalizada
                msg_personalizada = mensagem_campanha.replace("{nome}", nome_contacto)
                
                send_whatsapp(clean_dest, msg_personalizada, instance_name=instance_name)
                sucessos += 1
                time.sleep(PAUSA_CONTATO_SEG)
            else:
                falhas += 1
        except Exception as e:
            falhas += 1
            logger.error(f"Erro ao enviar disparo para contacto {dest}: {e}")

    # 2. Envio para grupos autorizados
    for grupo in grupos:
        try:
            if grupo:
                # Nos grupos, substitui {nome} por "Pessoal/Cliente" caso exista no texto
                msg_grupo = mensagem_campanha.replace("{nome}", "Clientes")
                
                send_whatsapp(grupo, msg_grupo, instance_name=instance_name)
                sucessos += 1
                time.sleep(PAUSA_GRUPO_SEG)
            else:
                falhas += 1
        except Exception as e:
            falhas += 1
            logger.error(f"Erro ao enviar disparo para grupo {grupo}: {e}")

    # 3. Notificação final com relatório para o WhatsApp do cliente
    relatorio = (
        f"📊 *RELATÓRIO FINAL DA CAMPANHA*\n\n"
        f"• *Total de Alvos:* {total_alvos}\n"
        f"• *Enviados com Sucesso:* ✅ {sucessos}\n"
        f"• *Falhas de Envio:* ❌ {falhas}\n\n"
        f"Campanha concluída com sucesso pelo **Negobot Moz**! 🚀"
    )
    
    try:
        cliente_clean = formatar_numero_mocambique(client_phone)
        send_whatsapp(cliente_clean, relatorio, instance_name=instance_name)
    except Exception as e:
        logger.error(f"Erro ao enviar relatório final para {client_phone}: {e}")


def processar_disparo_cliente(tenant_id, client_phone, message_text, instance_name):
    """
    Processa o comando de disparo em massa com validações de segurança e execução assíncrona.
    """
    try:
        agora = datetime.now(timezone.utc)

        # 1. Consultar a conta do cliente no Firestore
        tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
        tenant_doc = tenant_ref.get()

        if not tenant_doc.exists:
            return "❌ Conta não encontrada no sistema Negobot Moz."

        tenant_data = tenant_doc.to_dict() or {}

        # 2. Validação Estrita de Plano e Data de Expiração
        disparo_liberado = tenant_data.get('disparo_liberado', False)
        status_plano = str(tenant_data.get('status_plano', '')).lower()
        data_expiracao = tenant_data.get('data_expiracao')

        # Ajuste inteligente para formatos de data
        if data_expiracao:
            if isinstance(data_expiracao, str):
                try:
                    data_expiracao = datetime.fromisoformat(data_expiracao)
                except ValueError:
                    data_expiracao = None
            if hasattr(data_expiracao, 'tzinfo') and data_expiracao.tzinfo is None:
                data_expiracao = data_expiracao.replace(tzinfo=timezone.utc)

        # Bloqueio caso a licença tenha expirado
        if data_expiracao and agora > data_expiracao:
            return (
                "⚠️ *Sua Licença Expirou!*\n\n"
                "O seu plano atual encontra-se expirado. Para realizar novos disparos em massa, "
                "por favor efetue a renovação da sua assinatura via M-Pesa."
            )

        pode_disparar = (
            disparo_liberado or 
            status_plano == "demonstracao" or 
            "premium" in str(tenant_data.get('plano', '')).lower()
        )

        if not pode_disparar:
            return (
                "❌ *Ferramenta Bloqueada!*\n\n"
                "Os **Disparos em Massa** para contactos e grupos estão disponíveis exclusivamente no *Plano Premium (1.500 MT)*.\n\n"
                "Entre em contacto com a central do Negobot Moz para efetuar o upgrade da sua conta."
            )

        # 3. Extração da mensagem da campanha
        partes = message_text.split(maxsplit=1)
        if len(partes) < 2:
            return (
                "⚠️ *Uso incorreto do comando.*\n\n"
                "Para fazer um disparo, escreva o comando seguido da mensagem que deseja enviar.\n\n"
                "Exemplo:\n"
                "`#disparo Olá {nome}! Temos novidades e descontos imperdíveis esta semana na nossa loja.`"
            )

        mensagem_campanha = partes[1].strip()

        # 4. Buscar contactos e grupos registados na base de dados do cliente
        contactos_ref = tenant_ref.collection('base_contactos').stream()
        destinatarios = []
        for doc in contactos_ref:
            c_data = doc.to_dict() or {}
            phone = c_data.get('phone') or c_data.get('telefone')
            nome = c_data.get('nome', 'Cliente')
            if phone:
                destinatarios.append({"telefone": phone, "nome": nome})

        grupos_ref = tenant_ref.collection('grupos_autorizados').stream()
        grupos = [doc.to_dict().get('group_jid') for doc in grupos_ref if doc.to_dict().get('group_jid')]

        total_alvos = len(destinatarios) + len(grupos)
        if total_alvos == 0:
            return (
                "⚠️ *Nenhum contacto ou grupo encontrado na sua base de dados.*\n\n"
                "Carregue primeiro a sua lista de contactos no sistema antes de iniciar a campanha."
            )

        # 5. Iniciar o disparo assíncrono via Thread daemon
        thread_disparo = threading.Thread(
            target=_worker_executar_disparos,
            args=(destinatarios, grupos, mensagem_campanha, instance_name, client_phone, total_alvos),
            daemon=True
        )
        thread_disparo.start()

        # Resposta de confirmação imediata
        return (
            f"🚀 *Campanha iniciada com sucesso!*\n\n"
            f"• *Contactos:* {len(destinatarios)}\n"
            f"• *Grupos:* {len(grupos)}\n"
            f"• *Total de Alvos:* {total_alvos}\n\n"
            f"A campanha está a ser enviada em segundo plano com pausas anti-bloqueio. Receberá o relatório completo assim que for concluída!"
        )

    except Exception as e:
        logger.error(f"Erro crítico no processar_disparo_cliente para {tenant_id}: {e}", exc_info=True)
        return "❌ Ocorreu um erro interno ao processar a sua campanha de disparos."
