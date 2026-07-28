import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

_db = None

def init_services():
    """Inicializa o cliente Firestore com tratamento de erro melhorado."""
    global _db
    if firebase_admin._apps:
        _db = firestore.client()
        return
    
    firebase_config_env = os.getenv('FIREBASE_CONFIG')
    try:
        if firebase_config_env:
            firebase_config = json.loads(firebase_config_env)
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
        _db = firestore.client()
        logger.info("✅ Firebase inicializado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar Firebase com config: {e}")
        try:
            firebase_admin.initialize_app()
            _db = firestore.client()
            logger.info("✅ Firebase inicializado em modo padrão")
        except Exception as ex:
            logger.critical(f"❌ Falha crítica ao inicializar Firebase: {ex}")
            raise

def get_db():
    """Retorna o cliente Firestore, inicializando se necessário."""
    global _db
    if _db is None:
        init_services()
    return _db
