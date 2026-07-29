import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

db = None

def init_extensions(app=None):
    global db

    if not firebase_admin._apps:
        # Procura por FIREBASE_CONFIG ou por FIREBASE_JSON
        raw_config = os.getenv('FIREBASE_CONFIG') or os.getenv('FIREBASE_JSON')
        
        render_secret_path = "/etc/secrets/serviceAccountKey.json"
        local_secret_path = "serviceAccountKey.json"

        if raw_config:
            try:
                cred_dict = json.loads(raw_config.strip())
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                logger.info("📦 [SISTEMA] Firebase inicializado com sucesso via variável de ambiente!")
            except Exception as e:
                logger.error(f"❌ [SISTEMA] Erro ao ler JSON da ENV: {e}")
                raise e

        elif os.path.exists(render_secret_path):
            cred = credentials.Certificate(render_secret_path)
            firebase_admin.initialize_app(cred)
            logger.info("📦 [SISTEMA] Firebase inicializado via Secret File do Render.")

        elif os.path.exists(local_secret_path):
            cred = credentials.Certificate(local_secret_path)
            firebase_admin.initialize_app(cred)
            logger.info("📦 [SISTEMA] Firebase inicializado via ficheiro local serviceAccountKey.json.")

        else:
            raise RuntimeError(
                "❌ [SISTEMA CRÍTICO] Credenciais do Firebase não encontradas na ENV, "
                "em /etc/secrets/ ou localmente!"
            )

    db = firestore.client()
