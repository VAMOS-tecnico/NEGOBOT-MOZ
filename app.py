import os
from flask import Flask, request
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuração da IA
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

@app.route('/')
def home():
    return "Negobot Moz Online! 🇲🇿"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Deve ser igual ao que colocar na Meta e no Render
        verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN", "negobotmoz_token")
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == verify_token:
            return challenge, 200
        return "Token Inválido", 403
    
    return "EVENT_RECEIVED", 200

if name == "main":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
