import os
import json
import requests
from flask import Flask, request
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Inicialização do Firebase usando a variável de ambiente FIREBASE_CONFIG
firebase_config_env = os.getenv('FIREBASE_CONFIG')
if firebase_config_env:
    try:
        firebase_config = json.loads(firebase_config_env)
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Erro ao carregar JSON do Firebase: {e}")
        firebase_admin.initialize_app()
else:
    firebase_admin.initialize_app()

db = firestore.client()

# Configuração do NOVO cliente Gemini (SDK oficial google-genai)
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
# Usando o novíssimo Gemini 3 Flash Preview!
MODEL_NAME = 'gemini-3-flash-preview'

def get_chat_history(phone_number):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('history', [])
    except Exception as e:
        print(f"Erro ao obter historico: {e}")
    return []

def save_chat_history(phone_number, history):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc_ref.set({"history": history}, merge=True)
    except Exception as e:
        print(f"Erro ao salvar historico: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        if data.get('event') == "messages.upsert" and "data" in data:
            msg_data = data['data']
            key = msg_data.get('key', {})
            
            if key.get('fromMe'): return 'OK', 200
                
            phone_number = key.get('remoteJid')
            message = msg_data.get('message', {})
            message_text = ""
            
            # Extração de texto conforme o tipo de mensagem
            if 'conversation' in message:
                message_text = message['conversation']
            elif 'extendedTextMessage' in message:
                message_text = message['extendedTextMessage'].get('text', '')
            elif 'buttonsResponseMessage' in message:
                message_text = message['buttonsResponseMessage'].get('selectedButtonId', '')
            elif 'templateButtonReplyMessage' in message:
                message_text = message['templateButtonReplyMessage'].get('selectedId', '')

            if message_text and phone_number:
                # Recuperar o histórico do Firebase
                raw_history = get_chat_history(phone_number)
                
                # Converter o histórico antigo para o formato correto do novo SDK (types.Content)
                contents = []
                for msg in raw_history:
                    role = msg.get('role')
                    # O novo SDK espera "user" ou "model"
                    if role == "assistant":
                        role = "model"
                    
                    parts_list = []
                    for p in msg.get('parts', []):
                        parts_list.append(types.Part.from_text(text=p.get('text', '')))
                        
                    contents.append(
                        types.Content(
                            role=role,
                            parts=parts_list
                        )
                    )
                
                # Adicionar a nova mensagem do usuário ao histórico de envio
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message_text)]
                    )
                )

                try:
                    # Chamar o modelo usando o novo SDK
                    response = client.models.generate_content(
                        model=MODEL_NAME,
                        contents=contents
                    )
                    
                    # Adicionar a resposta do modelo ao histórico final
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part.from_text(text=response.text)]
                        )
                    )

                    # Converter de volta para formato JSON simples para salvar no Firebase
                    updated_history = []
                    for content in contents:
                        updated_history.append({
                            "role": content.role,
                            "parts": [{"text": p.text} for p in content.parts]
                        })
                    
                    save_chat_history(phone_number, updated_history)
                    send_whatsapp(phone_number, response.text)

                except Exception as e:
                    print(f"Erro no Gemini: {e}")
    except Exception as e:
        print(f"Erro no webhook: {e}")
        
    return 'OK', 200

def send_whatsapp(to, text):
    url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{os.getenv('EVOLUTION_INSTANCE_NAME')}"
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    payload = {
        "number": to,
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": text}
    }
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"Erro ao enviar: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
