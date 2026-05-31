import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(name)
CORS(app)

# Configuração da IA (Gemini)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

@app.route('/')
def home():
    return "Negobot Moz Backend está Online! 🇲🇿"

# Webhook para o WhatsApp
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Verificação do Webhook pela Meta
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode and token:
            if mode == 'subscribe' and token == "negobotmoz_token":
                return challenge, 200
            return "Token Inválido", 403
            
    if request.method == 'POST':
        data = request.json
        # Aqui o código processa a mensagem recebida e responde usando IA
        # (Lógica simplificada para o arranque)
        return "EVENT_RECEIVED", 200

if name == "main":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
