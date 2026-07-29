import time
import random
import logging
import requests
from config import Config

logger = logging.getLogger(__name__)

def disparar_broadcast_seguro(instance_name, api_key_evolution, lista_contactos, mensagem_texto):
    """
    Dispara mensagens em massa de forma segura, simulando o comportamento humano
    através de uma fila com pausa (delay) entre os envios.
    """
    url_base = getattr(Config, 'EVOLUTION_API_URL', 'https://api.evolution.com')
    url = f"{url_base}/message/sendText/{instance_name}"
    
    headers = {
        "apikey": api_key_evolution,
        "Content-Type": "application/json"
    }

    sucessos = 0
    falhas = 0

    logger.info(f"Iniciando broadcast seguro para {len(lista_contactos)} contactos...")

    for contacto in lista_contactos:
        telefone = contacto.get("telefone")
        nome = contacto.get("nome", "Cliente")

        if not telefone:
            continue

        # Personaliza a mensagem com o nome do cliente (opcional, mas aumenta muito a conversão)
        conteudo_personalizado = mensagem_texto.replace("{nome}", nome)

        payload = {
            "number": telefone,
            "text": conteudo_personalizado
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code in [200, 201]:
                sucessos += 1
                logger.info(f"Mensagem enviada com sucesso para {telefone}")
            else:
                falhas += 1
                logger.warning(f"Falha ao enviar para {telefone}: {response.text}")

        except Exception as e:
            falhas += 1
            logger.error(f"Erro de conexão ao enviar para {telefone}: {e}")

        # 🛡️ O SEGREDO DA BLINDAGEM: Pausa aleatória entre 15 e 30 segundos
        # Isto evita o padrão robótico e protege o número contra bloqueios por spam.
        tempo_espera = random.randint(15, 30)
        logger.info(f"A aguardar {tempo_espera} segundos antes do próximo envio...")
        time.sleep(tempo_espera)

    logger.info(f"Broadcast finalizado! Sucessos: {sucessos}, Falhas: {falhas}")
    return {"sucessos": sucessos, "falhas": falhas}
