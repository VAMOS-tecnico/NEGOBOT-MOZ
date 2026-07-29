import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

def inicializar_firebase():
    if not firebase_admin._apps:
        # 1. Tenta carregar as credenciais da variável FIREBASE_CONFIG (no Render)
        raw_config = os.getenv('FIREBASE_CONFIG')
        
        if raw_config:
            try:
                cred_dict = json.loads(raw_config.strip())
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                logger.info("🟢 Firebase inicializado com sucesso via Variável de Ambiente!")
                return
            except Exception as e:
                logger.error(f"❌ Erro ao converter a variável FIREBASE_CONFIG para JSON: {e}")
                raise e
        
        # 2. Se não estiver no Render, tenta carregar o ficheiro local (no seu PC)
        if os.path.exists("serviceAccountKey.json"):
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            logger.info("🟢 Firebase inicializado via ficheiro local serviceAccountKey.json!")
            return

        # 3. Se não encontrar nenhum dos dois, interrompe com aviso claro
        raise RuntimeError(
            "❌ FALTAM CREDENCIAIS: A variável 'FIREBASE_CONFIG' não está preenchida no Render "
            "e o ficheiro 'serviceAccountKey.json' não existe no computador."
        )

# Executa a inicialização
inicializar_firebase()

# Exporta a ligação à base de dados para o resto do projeto
db = firestore.client()
