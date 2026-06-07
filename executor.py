import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import time

# 1. LIGAR AO FIREBASE
# Use a mesma variável FIREBASE_JSON que configurámos no outro projeto
firebase_json = os.environ.get('FIREBASE_JSON')
if not firebase_json:
    print("❌ ERRO: Variável FIREBASE_JSON não encontrada no Render.")
    exit()

cred = credentials.Certificate(json.loads(firebase_json))
firebase_admin.initialize_app(cred)
db = firestore.client()

def entregar_negobot(telefone, plano):
    """
    ESTA É A FUNÇÃO QUE ENVIA O BOT PARA O CLIENTE
    """
    print(f"🚀 [EXECUTOR] A ativar Plano {plano} para o número {telefone}")
    
    # AQUI o senhor colocará o comando para o seu Bot de WhatsApp
    # Exemplo: Enviar link de acesso ou credenciais
    
    # Após entregar, podemos mudar o status para 'entregue' para não repetir
    # db.collection('assinantes').document(telefone).update({'status': 'entregue'})

def monitorar_pagamentos(col_snapshot, changes, read_time):
    for change in changes:
        # Verifica se um novo cliente foi adicionado ou se o status mudou
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc = change.document.to_dict()
            telefone = change.document.id
            status = doc.get('status')
            plano = doc.get('plano', 'Iniciação')

            # O GATILHO: Só age se o status for 'ativo'
            if status == 'ativo':
                entregar_negobot(telefone, plano)

# 2. INICIAR A VIGILÂNCIA EM TEMPO REAL
print("👀 Negobot Executor: Vigia iniciada. À espera de ativações no Firebase...")
assinantes_ref = db.collection('assinantes')
assinantes_ref.on_snapshot(monitorar_pagamentos)

# Mantém o programa vivo para sempre
while True:
    time.sleep(10)
