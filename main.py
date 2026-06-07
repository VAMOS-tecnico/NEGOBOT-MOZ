import os
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
# Permite que o seu site no GitHub envie dados para o Render
CORS(app, resources={r"/*": {"origins": "https://vamos-tecnico.github.io/NEGOBOT-MOZ/"}})

# Liga ao Firebase usando a variável FIREBASE_JSON que o senhor criou no Render
firebase_json = os.environ.get('FIREBASE_JSON')
if firebase_json:
    cred = credentials.Certificate(json.loads(firebase_json))
    firebase_admin.initialize_app(cred)
    db = firestore.client()

@app.route('/solicitar-pagamento', methods=['POST'])
def solicitar_pagamento():
    data = request.json
    telefone = data.get('telefone')
    plano = data.get('plano')
    
    try:
        # O "Balde": Grava o cliente como "pendente" no Firebase
        db.collection('assinantes').document(telefone).set({
            'status': 'pendente',
            'plano': plano,
            'data': datetime.datetime.now()
        })
        return jsonify({"status": "sucesso", "mensagem": "Pedido recebido!"}), 200
    except Exception as e:
        return jsonify({"mensagem": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
