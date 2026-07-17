import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import time
import requests

# 1. CONFIGURAÇÕES E INICIALIZAÇÃO
firebase_config_str = os.environ.get('FIREBASE_CONFIG')
EVOLUTION_API_URL = os.environ.get('EVOLUTION_API_URL')
EVOLUTION_API_KEY = os.environ.get('EVOLUTION_API_KEY')
# A sua instância principal (a que conversa com os seus clientes no WhatsApp)
PAINEL_INSTANCE = os.environ.get('EVOLUTION_INSTANCE_NAME') 

if not firebase_config_str:
    print("❌ ERRO: Variável FIREBASE_CONFIG não encontrada no Render.")
    exit()

# Inicialização do Firebase
cred = credentials.Certificate(json.loads(firebase_config_str))
firebase_admin.initialize_app(cred)
db = firestore.client()

def criar_instancia_cliente(instancia_cliente):
    """
    PASSO 1: Cria a nova instância para o cliente de forma 100% automática
    """
    url = f"{EVOLUTION_API_URL}/instance/create"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "instanceName": instancia_cliente,
        "qrcode": True
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            print(f"✅ [EVOLUTION] Instância '{instancia_cliente}' criada com sucesso!")
            return True
        else:
            # Se a instância já existir por algum motivo, permitimos continuar para tentar obter o QR Code
            print(f"⚠️ [EVOLUTION] Aviso ou Instância já existente: {response.text}")
            return True
    except Exception as e:
        print(f"❌ [ERRO] Falha crítica ao criar instância na API: {e}")
        return False

def buscar_qrcode_cliente(instancia_cliente):
    """
    PASSO 2: Solicita o QR Code de conexão da instância recém-criada
    """
    url = f"{EVOLUTION_API_URL}/instance/connect/{instancia_cliente}"
    headers = {"apikey": EVOLUTION_API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            dados = response.json()
            # Retorna o código base64 da imagem enviado pela Evolution API
            return dados.get("base64") or dados.get("code")
        else:
            print(f"❌ [EVOLUTION] Erro ao obter QR Code para {instancia_cliente}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ [ERRO] Falha ao ligar para extrair o QR Code: {e}")
        return None

def entregar_negobot(telefone, plano):
    """
    Orquestra a criação, captura e envio automático sem intervenção humana
    """
    print(f"🚀 [EXECUTOR] Processo de Ativação Automatizado Iniciado para o número {telefone}")
    
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Padroniza o nome da instância usando o número do cliente (Ex: instance_25884...)
    instancia_cliente = f"instance_{telefone}"
    
    # 🤖 1. CRIAR INSTÂNCIA AUTOMATICAMENTE
    print(f"🔄 [PROCESSO 1/4] A criar a instância '{instancia_cliente}' na API...")
    if not criar_instancia_cliente(instancia_cliente):
        print("❌ [CANCELADO] Interrompido por falha na criação da instância.")
        return
        
    # Pausa estratégica de 3 segundos para dar tempo ao servidor da Evolution de processar e carregar a nova instância
    time.sleep(3)

    # 🤖 2. CAPTURAR O QR CODE GERADO
    print(f"🔄 [PROCESSO 2/4] A capturar o QR Code em tempo real...")
    qrcode = buscar_qrcode_cliente(instancia_cliente)
    
    if not qrcode:
        print("❌ [CANCELADO] Interrompido porque o QR Code não pôde ser gerado.")
        return

    # 🤖 3. ENVIAR TEXTO DE INSTRUÇÃO PARA O CLIENTE
    print(f"🔄 [PROCESSO 3/4] A enviar guia de ativação para o cliente...")
    url_texto = f"{EVOLUTION_API_URL}/message/sendText/{PAINEL_INSTANCE}"
    mensagem = (
        f"Perfeito! O seu pagamento foi processado e o seu *Negobot Moz* (Plano {plano}) está pronto para ativação! 🚀\n\n"
        f"Como solicitado, aqui está o seu **Código QR** exclusivo, gerado neste instante.\n\n"
        f"Para automatizar o seu número agora mesmo:\n"
        f"1️⃣ Abra o WhatsApp no telemóvel que vai usar para o Bot.\n"
        f"2️⃣ Vá a Definições / Configurações > *Aparelhos Conectados*.\n"
        f"3️⃣ Clique em *Conectar um aparelho* e aponte a câmara para o QR Code que vou enviar abaixo.\n\n"
        f"Assim que escanear, o seu robô assume o controlo e começa a responder sozinho!"
    )
    payload_texto = {"number": telefone, "text": mensagem}
    requests.post(url_texto, json=payload_texto, headers=headers)

    # 🤖 4. ENVIAR A IMAGEM DO QR CODE DO CLIENTE
    print(f"🔄 [PROCESSO 4/4] A disparar imagem do QR Code...")
    url_media = f"{EVOLUTION_API_URL}/message/sendMedia/{PAINEL_INSTANCE}"
    payload_media = {
        "number": telefone,
        "media": qrcode, # Envia o Base64 puro capturado
        "mediatype": "image",
        "caption": "Aponte a câmara do seu WhatsApp para este QR Code para concluir a ativação! 📲"
    }
    
    response_media = requests.post(url_media, json=payload_media, headers=headers)
    if response_media.status_code in [200, 201]:
        print(f"✅ [SUCESSO TOTAL] Mensagem e QR Code entregues para {telefone}!")
        # Atualiza para 'entregue' no Firebase para fechar o ciclo e parar a monitorização deste ID
        db.collection('assinantes').document(telefone).update({'status': 'entregue'})
        print(f"💾 [DATABASE] Status de {telefone} atualizado com sucesso para 'entregue'.")
    else:
        print(f"❌ [ERRO] Falha ao enviar a mensagem de média: {response_media.text}")

def monitorar_pagamentos(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ['ADDED', 'MODIFIED']:
            doc = change.document.to_dict()
            telefone = change.document.id
            status = doc.get('status')
            plano = doc.get('plano', 'Iniciação')

            # Gatilho de Execução: Só age no exato momento em que o status passa a 'ativo'
            if status == 'ativo':
                entregar_negobot(telefone, plano)

# 2. VIGILÂNCIA CONSTANTE E EM TEMPO REAL
print("👀 Negobot Executor: Automação Total Ligada. À espera de gatilhos do Firebase...")
assinantes_ref = db.collection('assinantes')
assinantes_ref.on_snapshot(monitorar_pagamentos)

# Mantém o script em execução infinita no Render
while True:
    time.sleep(10)
