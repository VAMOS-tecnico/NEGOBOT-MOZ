    from flask import Flask, request, jsonify
    import os
    import requests
    import google.generativeai as genai
    from dotenv import load_dotenv

    load_dotenv()
    app = Flask(__name__)

    # Configurar Gemini
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-pro')

    @app.route('/')
    def home():
        return "Negobot Moz Online! 🇲🇿"

    @app.route('/webhook', methods=['GET'])
    def verify():
        token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'negobotmoz_token')
        if request.args.get('hub.verify_token') == token:
            return request.args.get('hub.challenge')
        return 'Erro de verificação', 403

    @app.route('/webhook', methods=['POST'])
    def webhook():
        data = request.json
        try:
            if 'messages' in data['entry'][0]['changes'][0]['value']:
                msg = data['entry'][0]['changes'][0]['value']['messages'][0]
                pergunta = msg['text']['body']
                quem_enviou = msg['from']

                # IA responde
                resposta = model.generate_content(pergunta).text

                # Enviar de volta usando o URL oficial da Meta
                pid = os.getenv('PHONE_NUMBER_ID')
                url = f"https://graph.facebook.com/v18.0/{pid}/messages"
                
                headers = {"Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}"}
                json_data = {
                    "messaging_product": "whatsapp",
                    "to": quem_enviou,
                    "type": "text",
                    "text": {"body": resposta}
                }
                requests.post(url, headers=headers, json=json_data)
        except:
            pass
        return 'OK', 200

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
    
