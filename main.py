import os
import json
import datetime
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "https://vamos-tecnico.github.io/NEGOBOT-MOZ/"}})

# Configuração do Firebase
firebase_json = os.environ.get('FIREBASE_JSON')
if firebase_json:
    cred = credentials.Certificate(json.loads(firebase_json))
    firebase_admin.initialize_app(cred)
    db = firestore.client()

# SEUS NÚMEROS DE RECEBIMENTO
MEU_MPESA = "855000929"
MEU_EMOLA = "879900929"

def processar_pagamento_automatico(telefone_cliente, valor, operadora):
    """
    Aqui será o motor que conecta com a API da Vodacom ou Movitel.
    Para isso, precisaremos das chaves (API Key) oficiais.
    """
    print(f"💰 Processando {valor} MT via {operadora} para o cliente {telefone_cliente}")
    # Por enquanto, o sistema grava como 'pendente' até termos as chaves da API
    return True

@app.route('/solicitar-pagamento', methods=['POST'])
def solicitar_pagamento():
    data = request.json
    telefone = data.get('telefone')
    plano = data.get('plano', 'Iniciação')
    
    # Define o valor e deteta a operadora
    valor = "500" if plano == "Elite" else "250"
    operadora = "M-Pesa" if telefone.startswith(('84', '85')) else "e-Mola"

    try:
        # 1. Tenta iniciar o processo de cobrança
        processar_pagamento_automatico(telefone, valor, operadora)

        # 2. Grava no Firebase para o seu Executor (Bot) ficar de vigia
        db.collection('assinantes').document(telefone).set({
            'status': 'pendente',
            'plano': plano,
            'valor': valor,
            'operadora': operadora,
            'data_pedido': datetime.datetime.now()
        })

        return jsonify({
            "status": "sucesso", 
            "mensagem": f"Pedido {operadora} recebido! Verifique o seu telemóvel para o PIN."
        }), 200

    except Exception as e:
        return jsonify({"mensagem": "Erro ao processar"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
