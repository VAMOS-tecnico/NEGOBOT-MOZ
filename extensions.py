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
        raw_config = os.getenv('FIREBASE_CONFIG')

        if raw_config:
            try:
                # Lê a variável de ambiente configurada no Render
                cred_dict = json.loads(raw_config.strip())
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                logger.info("📦 [SISTEMA] Firebase inicializado com sucesso via FIREBASE_CONFIG.")
            except Exception as e:
                logger.error(f"❌ [SISTEMA] O conteúdo da variável FIREBASE_CONFIG não é um JSON válido: {e}")
                raise e

        elif os.path.exists("serviceAccountKey.json"):
            # Fallback para o teu computador local
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            logger.info("📦 [SISTEMA] Firebase inicializado via ficheiro local serviceAccountKey.json.")

        else:
            raise RuntimeError(
                "❌ [SISTEMA CRÍTICO] A variável FIREBASE_CONFIG não está configurada no Render "
                "e o ficheiro 'serviceAccountKey.json' não existe localmente!"
            )

    # Liga a variável global db ao Firestore
    db = firestore.client()
