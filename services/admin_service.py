import re
import threading
import logging
from config import Config  # Importa a sua classe Config
from services.broadcast_service import disparar_broadcast_seguro

logger = logging.getLogger(__name__)


def formatar_numero_mocambique(phone_str):
    """Garante que o número tenha apenas dígitos e contenha o DDI 258."""
    clean = re.sub(r'\D', '', str(phone_str or ''))
    if len(clean) == 9 and clean.startswith(('84', '85', '86', '87')):
        return f"258{clean}"
    return clean


def processar_mensagem_admin(telefone_remetente, texto_mensagem, instance_name, api_key_evolution):
    """
    Verifica se o administrador enviou o comando de broadcast
    e dispara as mensagens em segundo plano com validação de segurança.
    """
    texto_limpo = (texto_mensagem or "").strip()
    
    if texto_limpo.upper().startswith("DISPARAR"):
        
        # 1. Trava de Segurança: Valida contra o ADMIN_NUMBER do seu config.py
        admin_autorizado = formatar_numero_mocambique(Config.ADMIN_NUMBER)
        remetente_validado = formatar_numero_mocambique(telefone_remetente)
        
        if admin_autorizado and remetente_validado != admin_autorizado:
            logger.warning(
                f"Tentativa de disparo não autorizada pelo número: {telefone_remetente} (Admin esperado: {admin_autorizado})"
            )
            return "❌ *Acesso Negado!* Este comando é restrito ao Administrador do Negobot Moz."

        try:
            partes = texto_limpo.split("|")
            
            if len(partes) < 3:
                return (
                    "⚠️ *Formato inválido!* Use o seguinte modelo:\n\n"
                    "`DISPARAR | 841234567, 859876543 | Sua mensagem aqui (use {nome} para personalizar).`"
                )

            numeros_brutos = partes[1].strip().split(",")
            mensagem_campanha = partes[2].strip()

            if not mensagem_campanha:
                return "⚠️ A mensagem do disparo não pode estar vazia."

            # 2. Tratamento e higienização dos números recebidos
            lista_contactos = []
            for num in numeros_brutos:
                num_formatado = formatar_numero_mocambique(num)
                if num_formatado:
                    lista_contactos.append({"telefone": num_formatado, "nome": "Cliente"})

            if not lista_contactos:
                return "⚠️ Nenhum número válido foi encontrado na lista fornecida."

            # 3. Thread em segundo plano para envio assíncrono
            hilo = threading.Thread(
                target=disparar_broadcast_seguro,
                args=(instance_name, api_key_evolution, lista_contactos, mensagem_campanha),
                daemon=True
            )
            hilo.start()

            return (
                f"🚀 *Broadcast de Administrador Iniciado!*\n\n"
                f"• *Destinatários Válidos:* {len(lista_contactos)}\n"
                f"• *Status:* A enviar em segundo plano com pausas de segurança."
            )

        except Exception as e:
            logger.error(f"Erro no comando de disparo admin: {e}", exc_info=True)
            return f"❌ Erro ao processar o comando de disparo: {str(e)}"

    return None
