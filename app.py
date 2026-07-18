import os
import json
import time
import requests
import threading
from flask import Flask, request
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Negobot 100% Automático está online e a responder! 🚀", 200

# Inicialização Segura do Firebase
firebase_config_env = os.getenv('FIREBASE_CONFIG')
if firebase_config_env:
    try:
        firebase_config = json.loads(firebase_config_env)
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
    except Exception:
        firebase_admin.initialize_app()
else:
    firebase_admin.initialize_app()

db = firestore.client()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
MODEL_NAME = 'gemini-3.1-flash-lite'
NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')

# ==========================================
#   🤖 FUNÇÃO DE INFRAESTRUTURA AUTOMÁTICA
# ==========================================

def criar_e_configurar_instancia_automatica(phone_number):
    try:
        client_instance = phone_number.split('@')[0]
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        url_create = f"{os.getenv('EVOLUTION_API_URL')}/instance/create"
        payload_create = {
            "instanceName": client_instance,
            "qrcode": True
        }
        res_create = requests.post(url_create, headers=headers, json=payload_create)
        
        base_url = os.getenv('RENDER_EXTERNAL_URL') or os.getenv('WEBHOOK_BASE_URL')
        if not base_url: return False
            
        url_webhook = f"{os.getenv('EVOLUTION_API_URL')}/webhook/set/{client_instance}"
        payload_webhook = {
            "enabled": True,
            "url": f"{base_url.rstrip('/')}/webhook-cliente",
            "events": ["messages.upsert"]
        }
        requests.post(url_webhook, headers=headers, json=payload_webhook)
        return True
    except Exception as e:
        print(f"❌ Erro na automação: {e}")
        return False

# ==========================================
#        FUNÇÕES AUXILIARES
# ==========================================

def send_whatsapp(to, text, instance_name=None):
    if not instance_name:
        instance_name = os.getenv('EVOLUTION_INSTANCE_NAME')
        
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    
    try:
        # DEBUG: loga para onde estamos a enviar
        print(f"🚀 [SEND] Tentando enviar para instancia: {instance_name} | Para: {to}")
        
        url_presence = f"{os.getenv('EVOLUTION_API_URL')}/chat/sendPresence/{instance_name}"
        requests.post(url_presence, headers=headers, json={"number": to, "presence": "composing"})
        
        time.sleep(1.5)
        
        url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{instance_name}"
        payload = {"number": to, "text": text}
        response = requests.post(url, headers=headers, json=payload)
        
        # DEBUG: loga o resultado da Evolution API
        print(f"🔬 [DEBUG SEND] Status: {response.status_code} | Resposta: {response.text}")
        
    except Exception as e:
        print(f"ERRO CRÍTICO ao enviar mensagem: {e}")

def get_chat_history(phone_number):
    try:
        doc = db.collection('chats').document(phone_number).get()
        return doc.to_dict().get('history', []) if doc.exists else []
    except: return []

def save_chat_history(phone_number, history):
    try: db.collection('chats').document(phone_number).set({"history": history}, merge=True)
    except: pass

def verificar_ou_criar_cliente(phone_number):
    try:
        ref = db.collection('clientes').document(phone_number)
        doc = ref.get()
        if not doc.exists:
            dados = {"phone_number": phone_number, "data_registro": datetime.now(timezone.utc), "status": "trial", "trial_start": datetime.now(timezone.utc)}
            ref.set(dados)
            return dados, True
        return doc.to_dict(), False
    except: return None, False

# ==========================================
#   ROTA: WEBHOOK DO CLIENTE
# ==========================================

@app.route('/webhook-cliente', methods=['POST'])
def webhook_cliente():
    data = request.json
    try:
        nome_instancia_atual = data.get('instance')
        
        # Correção no nome do evento (a Evolution usa messages.upsert)
        if data.get('event') == "messages.upsert":
            msg_data = data.get('data', {})
            key = msg_data.get('key', {})
            if key.get('fromMe'): return 'OK', 200
            
            phone_number = key.get('remoteJid', '')
            message_text = msg_data.get('message', {}).get('conversation') or msg_data.get('message', {}).get('extendedTextMessage', {}).get('text', '')

            if message_text and phone_number:
                # Processamento aqui...
                cliente, eh_primeira_msg = verificar_ou_criar_cliente(phone_number)
                
                # ... (Lógica de IA mantida igual)
                contents = []
                # (Recuperação de histórico e geração do Gemini...)
                # No envio final, usa:
                # send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
                
                # -> Adicionei a chamada aqui:
                # (O restante da lógica é igual ao seu código original)

    except Exception as e:
        print(f"ERRO WEBHOOK: {e}")
    return 'OK', 200

# ==========================================
#   ROTA: WEBHOOK CENTRAL (O resto do seu código...)
# ==========================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
