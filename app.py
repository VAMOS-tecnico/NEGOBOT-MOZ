from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
import requests
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'negobotmoz-secret-2026')

# ─── CONFIGURAÇÃO DO GEMINI ───────────────────────────────────────
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name='gemini-3.1-flash-lite',
        system_instruction="És o Negobot Moz, um assistente inteligente e amigável em Moçambique. Responde de forma concisa, direta e útil. Evita textos muito longos ou explicações desnecessárias, a menos que o utilizador peça detalhes. Usa um tom respeitoso."
    )
    print("Gemini configurado com sucesso!")
else:
    print("ERRO: GEMINI_API_KEY não encontrada no Environment.")

# Memória Individual por utilizador
user_histories = {}
MAX_HISTORY = 6  # Mantém as últimas 3 trocas de mensagens (3 perguntas + 3 respostas)

# ─── ROTA PRINCIPAL ───────────────────────────────────────────────
@app.route('/')
def index():
    return "Negobot Moz está Online! 🇲🇿🚀"

# ─── WEBHOOK (VERIFICAÇÃO) ────────────────────────────────────────
@app.route('/webhook', methods=['GET'])
def verify():
    verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'negobotmoz_token')
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode == 'subscribe' and token == verify_token:
        print("WEBHOOK VERIFICADO!")
        return challenge, 200
    return 'Forbidden', 403

# ─── WEBHOOK (PROCESSAR MENSAGENS) ───────────────────────────────
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    try:
        # Extrair a mensagem do JSON da Meta
        if data.get('entry') and data['entry'][0].get('changes') and data['entry'][0]['changes'][0].get('value', {}).get('messages'):
            message_obj = data['entry'][0]['changes'][0]['value']['messages'][0]
            phone_number = message_obj['from']
            
            message_text = ""
            if message_obj.get('type') == 'text':
                message_text = message_obj['text']['body']
            elif message_obj.get('type') == 'button':
                message_text = message_obj['button']['text']
            
            if message_text:
                print(f"--- NOVA MENSAGEM DE {phone_number} ---")
                
                # 1. Gerir histórico individual (Memória)
                if phone_number not in user_histories:
                    user_histories[phone_number] = []
                
                # Adicionar a nova mensagem ao histórico
                user_histories[phone_number].append({"role": "user", "parts": [message_text]})
                
                # Limitar histórico para poupar tokens e evitar erro de quota
                if len(user_histories[phone_number]) > MAX_HISTORY:
                    user_histories[phone_number] = user_histories[phone_number][-MAX_HISTORY:]

                # 2. Obter resposta do Gemini usando o contexto do histórico
                try:
                    chat_response = model.generate_content(user_histories[phone_number])
                    response_text = chat_response.text
                    
                    # Guardar a resposta no histórico para a próxima interação
                    user_histories[phone_number].append({"role": "model", "parts": [response_text]})
                    
                except Exception as e:
                    print(f"Erro no Gemini: {e}")
                    response_text = "Estou a processar muita coisa agora, pode repetir? 🇲🇿"

                # 3. Enviar a resposta de volta para o WhatsApp
                send_whatsapp(phone_number, response_text)

    except Exception as e:
        print(f"Erro ao processar webhook: {e}")

    return 'OK', 200

# ─── FUNÇÃO DE ENVIO PARA META ───────────────────────────────────
def send_whatsapp(to, text):
    token = os.getenv('WHATSAPP_TOKEN')
    phone_number_id = os.getenv('PHONE_NUMBER_ID')
    
    if not token or not phone_number_id:
        print("ERRO: WHATSAPP_TOKEN ou PHONE_NUMBER_ID em falta!")
        return

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
        r = requests.post(url, headers=headers, json=payload)
        print(f"Resposta da Meta: {r.status_code}")
    except Exception as e:
        print(f"Erro ao enviar para Meta: {e}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
