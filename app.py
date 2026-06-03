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

# ─── CONFIGURAÇÃO DO FIREBASE (MEMÓRIA MULTIPLATAFORMA) ─────────────
firebase_json = os.getenv('FIREBASE_JSON')
db = None

if firebase_json:
    try:
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase ligado! Memória ativa para WhatsApp, Messenger e Web. 🔥")
    except Exception as e:
        print(f"Erro no Firebase: {e}")

# ─── CONFIGURAÇÃO DO GEMINI 3.1 FLASH-LITE (O CÉREBRO OMNICHANNEL) ──
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # MISSÃO AMPLIADA: Escalar PMEs no WhatsApp, Messenger e Websites
    instruction = (
        "És o Negobot Moz, a inteligência artificial líder em Moçambique, criada pelo visionário Abel Silva Francisco. "
        "O teu Criador tem 29 anos, é formado em Contabilidade e Auditoria (ISPM-Manica, Chimoio), "
        "é Fundador e CEO da Fácilcred Imobiliários e Fácilcred Microcrédito, com experiência bancária e automotiva. "
        "Ele é um homem de família: casado e pai de dois filhos, um menino e uma menina. "
        "O teu OBJETIVO PRINCIPAL é ajudar PMEs moçambicanas a escalarem o atendimento no WhatsApp, Facebook Messenger e Websites. "
        "Deves ser profissional, eficiente e focado em converter conversas em vendas e satisfação para as PMEs. "
        "Responde sempre com integridade, honrando a visão multiplataforma do teu criador."
    )
    
    model = genai.GenerativeModel(
        model_name='gemini-3.1-flash-lite',
        system_instruction=instruction
    )
    print("Negobot Moz pronto para dominar WhatsApp, Messenger e Web! 🚀")

# ─── FUNÇÕES DE HISTÓRICO NO FIRESTORE ─────────────────────────────

def get_chat_history(phone_number):
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
    if db is None: return
    try:
        doc_ref = db.collection('historicos').document(phone_number)
        doc_ref.set({'messages': messages[-10:]})
    except Exception as e:
        print(f"Erro ao guardar histórico: {e}")

# ─── ROTAS DO SERVIDOR ─────────────────────────────────────────────

@app.route('/')
def index():
    return "Negobot Moz: Solução Inteligente para WhatsApp, Messenger e Web! 🇲🇿🚀"

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
            
            message_text = ""
            if message_obj.get('type') == 'text':
                message_text = message_obj['text']['body']
            elif message_obj.get('type') == 'button':
                message_text = message_obj['button']['text']

            if message_text:
                history = get_chat_history(phone_number)
                history.append({"role": "user", "parts": [message_text]})
                
                response = model.generate_content(history)
                res_text = response.text

                history.append({"role": "model", "parts": [res_text]})
                save_chat_history(phone_number, history)
                send_whatsapp(phone_number, res_text)
    except Exception as e:
        print(f"Erro no processamento: {e}")
    return 'OK', 200

def send_whatsapp(to, text):
    token = os.getenv('WHATSAPP_TOKEN')
    phone_number_id = os.getenv('PHONE_NUMBER_ID')
    
    # URL fundamentada na configuração oficial da Meta utilizada no seu projeto
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
        print(f"Erro ao enviar para Meta: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
