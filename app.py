import os
import requests
from flask import Flask, request, jsonify

app = Flask(name)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        event = data.get('event')
        
        if event == "messages.upsert" and "data" in data:
            msg_data = data['data']
            key = msg_data.get('key', {})
            
            if key.get('fromMe') == True:
                return 'OK', 200
                
            phone_number = key.get('remoteJid')
            
            message = msg_data.get('message', {})
            message_text = ""
            
            if 'conversation' in message:
                message_text = message['conversation']
            elif 'extendedTextMessage' in message:
                message_text = message['extendedTextMessage'].get('text', '')
            elif 'buttonsResponseMessage' in message:
                message_text = message['buttonsResponseMessage'].get('selectedButtonId', '')
            elif 'templateButtonReplyMessage' in message:
                message_text = message['templateButtonReplyMessage'].get('selectedId', '')

            if message_text and phone_number:
                history = get_chat_history(phone_number)
                
                try:
                    chat = model.start_chat(history=history)
                    response = chat.send_message(message_text) 
                    response_text = response.text

                    new_history = []
                    for msg in chat.history:
                        new_history.append({
                            "role": msg.role,
                            "parts": [p.text for p in msg.parts]
                        })
                    
                    save_chat_history(phone_number, new_history)
                    send_whatsapp(phone_number, response_text)

                except Exception as e:
                    print(f"Erro no Gemini: {e}")

    except Exception as e:
        print(f"Erro no processamento do webhook da Evolution: {e}")
        
    return 'OK', 200

def send_whatsapp(to, text):
    evolution_api_url = os.getenv('EVOLUTION_API_URL')
    evolution_api_key = os.getenv('EVOLUTION_API_KEY')
    instance_name = os.getenv('EVOLUTION_INSTANCE_NAME')
    
    url = f"{evolution_api_url}/message/sendText/{instance_name}"
    
    headers = {
        "apikey": evolution_api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "number": to,
        "options": {
            "delay": 1200,
            "presence": "composing"
        },
        "textMessage": {
            "text": text
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Resposta do envio Evolution: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro ao enviar via Evolution API: {e}")

if name == 'main':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
