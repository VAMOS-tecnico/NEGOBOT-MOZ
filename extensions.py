import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

db = None

def init_extensions(app=None):
    global db
    firebase_config_env = os.getenv('FIREBASE_CONFIG')
    if firebase_config_env:
        try:
            firebase_config = json.loads(firebase_config_env)
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
            print("📦 [SISTEMA] Firebase inicializado com credenciais da ENV.")
        except Exception as e:
            print(f"⚠️ [SISTEMA] Falha ao carregar FIREBASE_CONFIG da ENV: {e}. Tentando padrão...")
            try:
                firebase_admin.initialize_app()
            except Exception as ex:
                print(f"❌ [SISTEMA] Erro crítico ao inicializar Firebase: {ex}")
    else:
        try:
            firebase_admin.initialize_app()
            print("📦 [SISTEMA] Firebase inicializado com configurações padrão.")
        except Exception as e:
            print(f"❌ [SISTEMA] Erro crítico na inicialização padrão do Firebase: {e}")

    db = firestore.client()
