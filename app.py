from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import requests
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import json

load_dotenv()

app = Flask(__name__)

# ─── CONFIGURAÇÃO DO FIREBASE ──────────────────────────────────────
firebase_json = os.getenv('FIREBASE_JSON')
db = None

if firebase_json:
    try:
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase conectado com sucesso! 🔥")
    except Exception as e:
        print(f"Erro ao ligar o Firebase: {e}")
else:
    print("AVISO: FIREBASE_JSON não encontrado. O robô funcionará sem memória.")

# ─── CONFIGURAÇÃO DO GEMINI ────────────────────────────────────────
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(model_name='gemini-3.1-flash-lite')
else:
    print("ERRO: GEMINI_API_KEY em falta.")

# ─── FUNÇÕES DE APOIO ──────────────────────────────────────────────

def get_chat_history(phone_number):
    """Recupera o histórico do Firebase ou retorna lista vazia"""
    if db is None: return []
    try:
        doc_ref = db.collection('historicos').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('messages', [])
    except Exception as e:
        print(f"Erro ao ler histórico: {e}")
    return []

def save_chat_history(phone_number, messages):
    """Guarda o histórico atualizado no Firebase"""
    if db is None: return
    try:
        # Mantemos apenas as últimas 10 mensagens para não ficar pesado
        doc_ref = db.collection('historicos').document(phone_number)
        doc_ref.set({'messages': messages[-10:]})
    except Exception as e:
        print(f"Erro ao guardar histórico: {e}")

# ─── ROTAS ─────────────────────────────────────────────────────────

@app.route('/')
def index():
    return "Negobot Moz Online com Firebase! 🇲🇿🔥"

@app.route('/webhook', methods=['GET'])
def verify():
    verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'negobotmoz_token')
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == verify_token:
        return challenge, 200
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        if data.get('entry') and data['entry'][0].get('changes') and data['entry'][0]['changes'][0].get('value', {}).get('messages'):
            message_obj = data['entry'][0]['changes'][0]['value']['messages'][0]
            phone_number = message_obj['from']
            
            message_text = ""
            if message_obj.get('type') == 'text':
                message_text = message_obj['text']['body']
            
            if message_text:
                # 1. Buscar histórico no Firebase
                history = get_chat_history(phone_number)
                
                # 2. Adicionar mensagem do usuário
                history.append({"role": "user", "parts": [message_text]})
                
                # 3. Gerar resposta com Gemini
                try:
                    # Instrução do sistema para manter a personalidade
                    system_instruction = "És o Negobot Moz, assistente inteligente em Moçambique. Sê amigável e conciso."
                    chat = model.start_chat(history=[])
                    # Nota: Para manter simples, enviamos o histórico como contexto
                    response = model.generate_content(history)
                    response_text = response.text
                except Exception as e:
                    print(f"Erro Gemini: {e}")
                    response_text = "Tive um pequeno soluço, podes repetir? 🇲🇿"

                # 4. Adicionar resposta ao histórico e guardar
                history.append({"role": "model", "parts": [response_text]})
                save_chat_history(phone_number, history)

                # 5. Enviar para WhatsApp
                send_whatsapp(phone_number, response_text)

    except Exception as e:
        print(f"Erro no Webhook: {e}")

    return 'OK', 200

def send_whatsapp(to, text):
    token = os.getenv('WHATSAPP_TOKEN')
    phone_number_id = os.getenv('PHONE_NUMBER_ID')
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    requests.post(url, headers=headers, json=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
