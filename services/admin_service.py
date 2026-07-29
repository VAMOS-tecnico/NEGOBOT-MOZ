import threading
import logging
from services.broadcast_service import disparar_broadcast_seguro

logger = logging.getLogger(__name__)

def processar_mensagem_admin(telefone_remetente, texto_mensagem, instance_name, api_key_evolution):
    """
    Verifica se o administrador enviou o comando de broadcast
    e dispara as mensagens em segundo plano.
    """
    if texto_mensagem.upper().startswith("DISPARAR"):
        try:
            partes = texto_mensagem.split("|")
            
            if len(partes) < 3:
                return "⚠️ Formato inválido! Use o formato:\n\nDISPARAR | 258841234567, 258859876543 | Sua mensagem aqui (use {nome} para personalizar)."

            numeros_brutos = partes[1].strip().split(",")
            lista_contactos = [{"telefone": num.strip(), "nome": "Cliente"} for num in numeros_brutos if num.strip()]
            mensagem_campanha = partes[2].strip()

            if not lista_contactos:
                return "⚠️ Nenhum número válido foi encontrado na lista."

            # Thread em segundo plano para não bloquear a resposta rápida
            hilo = threading.Thread(
                target=disparar_broadcast_seguro,
                args=(instance_name, api_key_evolution, lista_contactos, mensagem_campanha)
            )
            hilo.start()

            return f"✅ Campanha de broadcast iniciada com sucesso para {len(lista_contactos)} contactos!\n\nO sistema está a enviar as mensagens de forma pausada e segura nos bastidores."

        except Exception as e:
            logger.error(f"Erro no comando de disparo admin: {e}")
            return f"❌ Erro ao processar o comando de disparo: {str(e)}"

    return None
