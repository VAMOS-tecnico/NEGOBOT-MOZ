import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

db = None

def init_extensions(app=None):
    global db

    # Evita re-inicializar caso a app já esteja ativa
    if firebase_admin._apps:
        db = firestore.client()
        return

    firebase_config_env = os.getenv('FIREBASE_CONFIG')

    if firebase_config_env:
        try:
            # Tenta converter a string da variável do Render em dicionário JSON
            firebase_config = json.loads(firebase_config_env.strip())
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
            print("📦 [SISTEMA] Firebase inicializado com sucesso via Variável de Ambiente (FIREBASE_CONFIG).")
        except Exception as e:
            print(f"❌ [SISTEMA] Erro ao ler o JSON da variável FIREBASE_CONFIG no Render: {e}")
            raise e
            
    elif os.path.exists("serviceAccountKey.json"):
        # Fallback apenas para quando estiveres a rodar o projeto no teu computador
        try:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            print("📦 [SISTEMA] Firebase inicializado via ficheiro local serviceAccountKey.json.")
        except Exception as e:
            print(f"❌ [SISTEMA] Erro ao carregar ficheiro local do Firebase: {e}")
            raise e
    else:
        # Se não encontrar credenciais nem na ENV nem em ficheiro local, interrompe com mensagem clara
        raise RuntimeError(
            "❌ [SISTEMA CRÍTICO] A variável 'FIREBASE_CONFIG' não foi encontrada no Render "
            "e o ficheiro 'serviceAccountKey.json' não existe na raiz do projeto!"
        )

    # Liga ao Firestore apenas se a inicialização correu bem
    db = firestore.client()
