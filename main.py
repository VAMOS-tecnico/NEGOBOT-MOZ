import os
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS  # Importa o CORS para Flask
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Configura o CORS exatamente para o seu site no GitHub
CORS(app, resources={r"/*": {"origins": "https://vamos-tecnico.github.io/NEGOBOT-MOZ/"}})

# Configuração do Firebase
firebase_config = os.environ.get('FIREBASE_JSON')
if firebase_config:
    cred_dict = json.loads(firebase_config)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

@app.route('/')
def home():
    return "API Negobot Moz Ativa!", 200

@app.route('/solicitar-pagamento', methods=['POST'])
def solicitar_pagamento():
    data = request.json
    telefone = data.get('telefone')
    plano = data.get('plano', 'Iniciação')
    
    if not telefone:
        return jsonify({"mensagem": "Número de telefone é obrigatório"}), 400

    try:
        # Grava o pedido no Firestore para o Bot poder consultar depois
        doc_ref = db.collection('assinantes').document(telefone)
        doc_ref.set({
            'status': 'pendente',
            'plano': plano,
            'data_pedido': datetime.datetime.now()
        })

        return jsonify({
            "status": "sucesso", 
            "mensagem": "Pedido recebido com sucesso! Siga as instruções no seu WhatsApp."
        }), 200

    except Exception as e:
        print(f"Erro ao gravar no Firebase: {e}")
        return jsonify({"mensagem": "Erro ao processar o pedido no servidor"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
