import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega as chaves secretas
load_dotenv()

app = Flask(__name__)

# Configuração da IA Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-pro')

@app.route('/')
def home():
    return "Negobot Moz está Online! 🇲🇿🚀"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. Validação da Meta (WhatsApp)
    if request.method == 'GET':
        verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN", "negobotmoz_token")
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == verify_token:
            return challenge, 200
        return "Token de verificação inválido", 403

    # 2. Recebimento de Mensagens
    if request.method == 'POST':
        # Por enquanto, apenas confirmamos que recebemos o evento
        return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
