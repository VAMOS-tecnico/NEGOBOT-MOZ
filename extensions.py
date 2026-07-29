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
        
        # Caminhos possíveis para o ficheiro de credenciais (Local ou Render Secret File)
        render_secret_path = "/etc/secrets/serviceAccountKey.json"
        local_secret_path = "serviceAccountKey.json"

        if raw_config:
            try:
                # 1. Tenta carregar pela variável de ambiente FIREBASE_CONFIG
                cred_dict = json.loads(raw_config.strip())
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                logger.info("📦 [SISTEMA] Firebase inicializado via variável FIREBASE_CONFIG.")
            except Exception as e:
                logger.error(f"❌ [SISTEMA] Erro ao ler JSON da ENV: {e}")
                raise e

        elif os.path.exists(render_secret_path):
            # 2. Tenta carregar pelo Secret File do Render
            cred = credentials.Certificate(render_secret_path)
            firebase_admin.initialize_app(cred)
            logger.info("📦 [SISTEMA] Firebase inicializado via Secret File do Render (/etc/secrets/).")

        elif os.path.exists(local_secret_path):
            # 3. Tenta carregar pelo ficheiro local no teu computador
            cred = credentials.Certificate(local_secret_path)
            firebase_admin.initialize_app(cred)
            logger.info("📦 [SISTEMA] Firebase inicializado via ficheiro local serviceAccountKey.json.")

        else:
            raise RuntimeError(
                "❌ [SISTEMA CRÍTICO] Credenciais do Firebase não encontradas na ENV, "
                "em /etc/secrets/ ou localmente!"
            )

    # Conecta o cliente ao Firestore
    db = firestore.client()
