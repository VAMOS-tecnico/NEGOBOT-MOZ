import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from config import Config

logger = logging.getLogger(__name__)

def inicializar_firebase():
    """Inicializa o SDK do Firebase Admin tratando strings JSON e arquivos locais."""
    if not firebase_admin._apps:
        try:
            raw_config = getattr(Config, 'FIREBASE_CONFIG', None) or os.getenv('FIREBASE_CONFIG')
            
            if raw_config:
                # Tenta ler como JSON (formato usado no Render)
                if isinstance(raw_config, str):
                    cred_dict = json.loads(raw_config)
                    cred = credentials.Certificate(cred_dict)
                else:
                    cred = credentials.Certificate(raw_config)
                
                firebase_admin.initialize_app(cred)
                logger.info("🟢 Firebase inicializado com sucesso via Variável de Ambiente!")
            else:
                # Fallback para desenvolvimento local
                local_file = "serviceAccountKey.json"
                if os.path.exists(local_file):
                    cred = credentials.Certificate(local_file)
                    firebase_admin.initialize_app(cred)
                    logger.info("🟢 Firebase inicializado via ficheiro local!")
                else:
                    raise RuntimeError("❌ Nenhuma credencial do Firebase foi encontrada em FIREBASE_CONFIG ou no ficheiro local!")
        except Exception as e:
            logger.error(f"Falha ao carregar credenciais do Firebase: {e}")
            raise e

# Garante que o Firebase é arrancado
inicializar_firebase()

# Exporta a instância do Firestore para usar no projeto todo
db = firestore.client()
