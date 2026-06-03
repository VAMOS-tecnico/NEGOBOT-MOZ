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
        print("Firebase ligado! Memória contextual ativa. 🔥")
    except Exception as e:
        print(f"Erro no Firebase: {e}")

# ─── CONFIGURAÇÃO DO GEMINI 3.1 (REATIVO E CONCISO) ────────────────
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # INSTRUÇÃO: Responde apenas ao que for perguntado
    instruction = (
        "És o Negobot Moz. Tens o seguinte conhecimento sobre o teu criador (Abel Silva Francisco, "
        "29 anos, formado em Contabilidade no ISPM-Manica, CEO da Fácilcred Imobiliários e Microcrédito, "
        "casado, pai de um menino e uma menina, missão de escalar PMEs no WhatsApp/Messenger/Web). "
        "\n\nREGRA DE OURO: Responde APENAS ao que o utilizador perguntar. "
        "Não dês informações que não foram pedidas. Se perguntarem 'Quem te fez?', diz o nome dele. "
        "Se perguntarem 'O que ele faz?', explica o trabalho. Se perguntarem pela família, fala da família. "
        "Mantém a conversa natural, faseada e nunca dês blocos de texto com informações extras."
    )
    
    model = genai.GenerativeModel(
        model_name='gemini-3.1-flash-lite',
        system_instruction=instruction
    )
    print("Negobot Moz pronto para conversar de forma reativa! 🚀")

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
    return "Negobot Moz: Inteligência Reativa e Focada! 🇲🇿🚀"

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
            msg = data['entry'][0]['changes'][0]['value']['messages'][0]
            num = msg['from']
            text = msg.get('text', {}).get('body', '') or msg.get('button', {}).get('text', '')

            if text:
                history = get_chat_history(num)
                history.append({"role": "user", "parts": [text]})
                
                response = model.generate_content(history)
                res_text = response.text

                history.append({"role": "model", "parts": [res_text]})
                save_chat_history(num, history)
                send_whatsapp(num, res_text)
    except Exception as e:
        print(f"Erro: {e}")
    return 'OK', 200

def send_whatsapp(to, text):
    token = os.getenv('WHATSAPP_TOKEN')
    phone_number_id = os.getenv('PHONE_NUMBER_ID')
    
    # URL oficial Cloud API da Meta
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
    requests.post(url, headers=headers, json=payload)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
