import os
import json
import requests
from flask import Flask, request
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# --- Rota de Saúde (Adicionada) ---
# Isso resolve o erro 404 e permite que o UptimeRobot mantenha o bot ativo
@app.route('/', methods=['GET'])
def health_check():
    return "O bot está online!", 200

# Inicialização do Firebase
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

# Inicialização do novo SDK Gemini
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
MODEL_NAME = 'gemini-3-flash-preview'

def get_chat_history(phone_number):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('history', [])
    except Exception as e:
        print(f"Erro ao obter historico: {e}")
    return []

def save_chat_history(phone_number, history):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc_ref.set({"history": history}, merge=True)
    except Exception as e:
        print(f"Erro ao salvar historico: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        # Verifica se o evento é uma mensagem nova
        if data.get('event') == "messages.upsert" and "data" in data:
            msg_data = data['data']
            key = msg_data.get('key', {})
            
            # --- TRAVA DE SEGURANÇA ---
            # 1. Evita responder a si mesmo
            if key.get('fromMe'): return 'OK', 200
            
            # 2. TRAVA DE GRUPOS: Se tiver @g.us, ignora imediatamente
            phone_number = key.get('remoteJid', '')
            if '@g.us' in phone_number:
                print("Ignorado: Mensagem de grupo detectada.")
                return 'OK', 200
            # ---------------------------
            
            message = msg_data.get('message', {})
            message_text = ""
            
            # Extração de texto
            if 'conversation' in message:
                message_text = message['conversation']
            elif 'extendedTextMessage' in message:
                message_text = message['extendedTextMessage'].get('text', '')

            if message_text and phone_number:
                # Recuperar histórico
                raw_history = get_chat_history(phone_number)
                
                # Converter para o formato do novo SDK
                contents = []
                for msg in raw_history:
                    role = "model" if msg.get('role') == "assistant" else msg.get('role')
                    parts = [types.Part.from_text(text=p.get('text', '')) for p in msg.get('parts', [])]
                    contents.append(types.Content(role=role, parts=parts))
                
                # Adicionar nova mensagem
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))

                # Gerar resposta
                response = client.models.generate_content(model=MODEL_NAME, contents=contents)
                response_text = response.text
                
                # Salvar histórico atualizado
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))
                save_chat_history(phone_number, [{"role": c.role, "parts": [{"text": p.text} for p in c.parts]} for c in contents])

                # Enviar resposta
                send_whatsapp(phone_number, response_text)

    except Exception as e:
        print(f"ERRO CRÍTICO: {e}")
        
    return 'OK', 200

def send_whatsapp(to, text):
    url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{os.getenv('EVOLUTION_INSTANCE_NAME')}"
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    payload = {"number": to, "text": text}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"DEBUG: Resposta da API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"ERRO ao enviar: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
