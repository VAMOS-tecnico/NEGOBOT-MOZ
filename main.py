import os
import json
import datetime
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Configuração do Firebase via Variável de Ambiente
# No Render, vamos colar o conteúdo do seu ficheiro JSON numa variável chamada FIREBASE_JSON
firebase_config = os.environ.get('FIREBASE_JSON')
if firebase_config:
    cred_dict = json.loads(firebase_config)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

@app.route('/')
def health_check():
    return "API Negobot Moz Ativa!", 200

# Endpoint para ativar o acesso (Webhook)
@app.route('/ativar-acesso', methods=['POST'])
def ativar_acesso():
    data = request.json
    telefone = data.get('telefone') # Ex: 25884xxxxxxx
    plano = data.get('plano', 'Iniciação')
    
    if not telefone:
        return jsonify({"erro": "Telefone obrigatorio"}), 400

    # Define a validade para 30 dias a partir de agora
    validade = datetime.datetime.now() + datetime.timedelta(days=30)

    # Grava ou atualiza o status no Firestore
    doc_ref = db.collection('assinantes').document(telefone)
    doc_ref.set({
        'status': 'ativo',
        'plano': plano,
        'data_ativacao': datetime.datetime.now(),
        'data_expiracao': validade
    })

    return jsonify({"status": "sucesso", "mensagem": f"Acesso libertado para {telefone}"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
