import os
import logging
import urllib.parse
import requests

logger = logging.getLogger(__name__)

def gerar_imagem_publicitaria(prompt: str) -> str:
    """
    Gera uma imagem publicitária com base no prompt em português enviado pelo cliente.
    Retorna o URL público da imagem gerada.
    """
    try:
        # Sanitiza e limpa o prompt do utilizador
        prompt_limpo = prompt.replace("#imagem", "").replace("gerar imagem", "").replace("cria uma arte", "").strip()
        
        if not prompt_limpo:
            prompt_limpo = "Cartaz publicitário profissional para redes sociais, estilo moderno e comercial"

        # Adiciona sufixos para melhorar a qualidade estética da publicidade
        prompt_estilizado = f"{prompt_limpo}, professional commercial poster, high resolution, 4k, vibrant colors, marketing style"
        prompt_encoded = urllib.parse.quote(prompt_estilizado)

        # Exemplo utilizando o Pollinations AI (API gratuita e direta sem necessidade de API Key)
        # Pode alterar para OpenAI DALL-E, Stability AI ou Midjourney se tiver chave de API
        image_url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&seed=42&nologo=true"

        # Teste rápido para validar se o serviço respondeu com sucesso
        response = requests.head(image_url, timeout=10)
        if response.status_code == 200:
            return image_url
        
        logger.error(f"Erro na API de imagem: Status Code {response.status_code}")
        return None

    except Exception as e:
        logger.error(f"Erro ao gerar imagem publicitária: {e}", exc_info=True)
        return None
