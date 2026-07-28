import os
import json
import threading
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# Configuração de Timeout para Atendimento Humano (Tempo em minutos)
TIMEOUT_HUMANO_MINUTOS = int(os.getenv('TIMEOUT_HUMANO_MINUTOS', 2))

# ==========================================
#   📦 INICIALIZAÇÃO SEGURA DO FIREBASE
# ==========================================
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

# ==========================================
#   CONFIGURAÇÕES DA API GROQ
# ==========================================
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'qwen-2.5-32b')

NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')
ADMIN_NUMBER = os.getenv('ADMIN_NUMBER')

# Controle de Duplicados
PROCESSADOS = {}
processados_lock = threading.Lock()
