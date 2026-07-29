import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from config import Config

logger = logging.getLogger(__name__)

if not firebase_admin._apps:
    # 1. Procura a string JSON nas variáveis de ambiente
    raw_config = getattr(Config, 'FIREBASE_CONFIG', None) or os.getenv('FIREBASE_CONFIG')
    
    cred = None
    if raw_config:
        try:
            if isinstance(raw_config, str):
                cred_dict = json.loads(raw_config.strip())
                cred = credentials.Certificate(cred_dict)
            elif isinstance(raw_config, dict):
                cred = credentials.Certificate(raw_config)
        except Exception as e:
            logger.error(f"Erro ao processar JSON da variavel FIREBASE_CONFIG: {e}")

    # 2. Fallback para ficheiro local (caso estejas a testar no computador)
    if not cred and os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")

    # 3. Inicializa APENAS se a credencial for válida
    if cred:
        firebase_admin.initialize_app(cred)
        logger.info("🟢 Firebase inicializado com sucesso!")
    else:
        # Levanta um erro claro em vez de deixar a Google falhar em silêncio
        raise RuntimeError(
            "❌ FALTAM CREDENCIAIS: A variável 'FIREBASE_CONFIG' não está definida no Render "
            "ou o JSON colado no painel é inválido."
        )

db = firestore.client()
