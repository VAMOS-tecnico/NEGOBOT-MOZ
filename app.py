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

# ─── CONFIGURAÇÃO DO FIREBASE (MEMÓRIA OMNICHANNEL) ────────────────
firebase_json = os.getenv('FIREBASE_JSON')
db = None

if firebase_json:
    try:
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase ligado! Pronto para Whatsapp, Facebook messeger e Websites. 🔥")
    except Exception as e:
        print(f"Erro no Firebase: {e}")

# ─── CONFIGURAÇÃO DO GEMINI 3.1 ────────────────────────────────────
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    instruction = (
        "És o Negobot Moz, o assistente de IA criado pelo CEO Abel Silva Francisco. "
        "A tua missão é atender PMEs no Whatsapp, Facebook messeger e Websites. "
        "\n\nREGRAS DE OURO:"
        "\n1. CLAREZA TOTAL: Usa uma linguagem bem clara e simples."
        "\n2. REATIVIDADE: Responde APENAS ao que for perguntado."
        "\n3. CONHECIMENTO: Sabes que o teu criador (Abel Silva Francisco) tem 29 anos, Auditor, "
        "CEO da Fácilcred, casado e tem um casal de filhos (menino e menina). Revela apenas se pedirem."
    )
    
    model = genai.GenerativeModel(
        model_name='gemini-3.1-flash-lite',
        system_instruction=instruction
    )

# ─── FUNÇÕES DE HISTÓRICO ──────────────────────────────────────────

def get_chat_history(phone_number):
    if db is None: return []
    try:
        doc = db.collection('historicos').document(phone_number).get()
        return doc.to_dict().get('messages', []) if doc.exists else []
    except: return []

def save_chat_history(phone_number, messages):
    if db is not None:
        db.collection('historicos').document(phone_number).set({'messages': messages[-10:]})

# ─── ROTAS DO SERVIDOR ─────────────────────────────────────────────

@app.route('/')
def index():
    return "Negobot Moz Online: Whatsapp, Facebook messeger e Websites! 🇲🇿🚀"

@app.route('/webhook', methods=['GET'])
def verify():
    v_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'negobotmoz_token')
    if request.args.get('hub.verify_token') == v_token:
        return request.args.get('hub.challenge'), 200
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        if data.get('entry') and 'messages' in data['entry'][0]['changes'][0]['value']:
            message_obj = data['entry'][0]['changes'][0]['value']['messages'][0]
            phone_number = message_obj['from']
            message_text = message_obj.get('text', {}).get('body', '') or message_obj.get('button', {}).get('text', '')

            if message_text:
                # 1. Recuperar histórico do Firebase
                history = get_chat_history(phone_number)
                
                # 3. Gerar resposta com Gemini (Snippet do Sr. Abel)
                try:
                    # Iniciamos o chat com o histórico para manter a memória ativa
                    chat = model.start_chat(history=history)
                    
                    response = chat.send_message(message_text) 
                    response_text = response.text

                    # 4. Atualizar o histórico com a nova conversa
                    new_history = []
                    for msg in chat.history:
                        new_history.append({
                            "role": msg.role,
                            "parts": [p.text for p in msg.parts]
                        })
                    
                    save_chat_history(phone_number, new_history)

                    # 5. Enviar de volta ao Whatsapp
                    send_whatsapp(phone_number, response_text)

                except Exception as e:
                    print(f"Erro no Gemini: {e}")

    except Exception as e:
        print(f"Erro no processamento: {e}")

    return 'OK', 200

def send_whatsapp(to, text):
    # Credenciais do ambiente Meta Cloud API
    token = os.getenv('WHATSAPP_TOKEN')
    phone_number_id = os.getenv('PHONE_NUMBER_ID')
    
    # URL da API Cloud da Meta para envio de mensagens
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }

    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"Erro ao enviar para o Whatsapp: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
