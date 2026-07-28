import os
import threading
from flask import Flask, request
from services import init_services, processar_webhook_background
from services.config import PORT

app = Flask(__name__)

# Inicializar Firebase
init_services()

@app.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Negobot 100% Automático está online! 🚀", 200

@app.route('/webhook-global', methods=['POST'])
@app.route('/webhook-cliente', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def universal_webhook():
    """Webhook universal para receber mensagens do WhatsApp."""
    data = request.json
    if not data:
        return 'OK', 200
    
    # Processar em background
    processar_webhook_background(data)
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
