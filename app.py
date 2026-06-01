from flask import Flask, request
import os
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Configurar o Gemini (IA)
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/')
def home():
    return "Negobot Moz Online! 🇲🇿🚀"

@app.route('/webhook', methods=['GET'])
def verify():
    # Token que o senhor configurou na Meta
    token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'negobotmoz_token')
    if request.args.get('hub.verify_token') == token:
        return request.args.get('hub.challenge')
    return 'Erro de verificação', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        if 'messages' in data['entry'][0]['changes'][0]['value']:
            value = data['entry'][0]['changes'][0]['value']
            msg = value['messages'][0]
            pergunta = msg['text']['body']
            quem_enviou = msg['from']

            # A IA cria a resposta
            response = model.generate_content(pergunta)
            resposta_ia = response.text

            # Enviar para o WhatsApp (usando os dados da Meta)
            # O URL oficial deve ser copiado do seu painel da Meta
            url = os.getenv('WHATSAPP_API_URL') 
            token = os.getenv('ACCESS_TOKEN')
            
            headers = {"Authorization": f"Bearer {token}"}
            json_data = {
                "messaging_product": "whatsapp",
                "to": quem_enviou,
                "type": "text",
                "text": {"body": resposta_ia}
            }
            requests.post(url, headers=headers, json=json_data)
    except Exception as e:
        print(f"Erro detetado: {e}")
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
