from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import requests
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'negobotmoz-secret-2026')

# Configuração do Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    print("Gemini pronto!")
else:
    print("Erro: GEMINI_API_KEY não configurada.")

@app.route('/')
def index():
    return "Negobot Moz está Online! 🇲🇿🚀"

# --- WEBHOOK (Ajustado para /webhook conforme os seus logs) ---

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
    print('Mensagem recebida:', data)

    try:
        if data.get('entry') and data['entry'][0].get('changes') and data['entry'][0]['changes'][0].get('value', {}).get('messages'):
            message_obj = data['entry'][0]['changes'][0]['value']['messages'][0]
            phone_number = message_obj['from']
            
            message_text = ""
            if message_obj.get('type') == 'text':
                message_text = message_obj['text']['body']
            
            if message_text:
                # 1. Resposta da IA (Gemini)
                chat_response = model.generate_content(message_text)
                response_text = chat_response.text

                # 2. Enviar via WhatsApp API
                send_whatsapp(phone_number, response_text)

    except Exception as e:
        print(f"Erro no processamento: {e}")

    return 'OK', 200

def send_whatsapp(to, text):
    token = os.getenv('WHATSAPP_TOKEN')
    phone_number_id = os.getenv('PHONE_NUMBER_ID')
    
    # URL fundamentada na documentação da Meta
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
    requests.post(url, headers=headers, json=payload)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
