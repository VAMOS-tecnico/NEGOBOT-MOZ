# executor.py
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import time
import requests
import threading

# Variáveis de ambiente (obrigatórias)
firebase_config_str = os.environ.get('FIREBASE_CONFIG')
EVOLUTION_API_URL = os.environ.get('EVOLUTION_API_URL')
EVOLUTION_API_KEY = os.environ.get('EVOLUTION_API_KEY')
PAINEL_INSTANCE = os.environ.get('EVOLUTION_INSTANCE_NAME')  # instância principal que envia mensagens

if not firebase_config_str:
    raise RuntimeError("FIREBASE_CONFIG não encontrada nas variáveis de ambiente.")

# Inicializa Firebase (idempotente)
def _init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(firebase_config_str))
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = _init_firebase()

def criar_instancia_cliente(instancia_cliente):
    url = f"{EVOLUTION_API_URL}/instance/create"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {"instanceName": instancia_cliente, "qrcode": True}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code in (200, 201):
            return True
        # se já existir, consideramos sucesso (log)
        return True
    except Exception as e:
        print(f"[executor] Erro criar_instancia_cliente: {e}")
        return False

def buscar_qrcode_cliente(instancia_cliente):
    url = f"{EVOLUTION_API_URL}/instance/connect/{instancia_cliente}"
    headers = {"apikey": EVOLUTION_API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            dados = response.json()
            return dados.get("base64") or dados.get("code")
        return None
    except Exception as e:
        print(f"[executor] Erro buscar_qrcode_cliente: {e}")
        return None

def entregar_negobot(telefone, plano):
    print(f"[executor] Iniciando ativação para {telefone} (plano {plano})")
    instancia_cliente = f"instance_{telefone}"
    if not criar_instancia_cliente(instancia_cliente):
        print("[executor] Falha ao criar instância")
        return

    time.sleep(3)
    qrcode = buscar_qrcode_cliente(instancia_cliente)
    if not qrcode:
        print("[executor] QR Code não disponível")
        return

    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    # enviar texto de instrução
    url_texto = f"{EVOLUTION_API_URL}/message/sendText/{PAINEL_INSTANCE}"
    mensagem = (
        f"Perfeito! O seu Negobot Moz (Plano {plano}) está pronto para ativação.\n\n"
        "Siga as instruções: Abra WhatsApp -> Aparelhos Conectados -> Conectar um aparelho -> Escaneie o QR Code abaixo."
    )
    try:
        requests.post(url_texto, json={"number": telefone, "text": mensagem}, headers=headers, timeout=10)
    except Exception as e:
        print(f"[executor] Erro enviar texto: {e}")

    # enviar media (QR)
    url_media = f"{EVOLUTION_API_URL}/message/sendMedia/{PAINEL_INSTANCE}"
    payload_media = {"number": telefone, "media": qrcode, "mediatype": "image", "caption": "Escaneie este QR Code para ativar."}
    try:
        response_media = requests.post(url_media, json=payload_media, headers=headers, timeout=20)
        if response_media.status_code in (200, 201):
            print(f"[executor] QR Code enviado para {telefone}")
            try:
                db.collection('assinantes').document(telefone).update({'status': 'entregue'})
            except Exception as e:
                print(f"[executor] Erro atualizar Firestore: {e}")
        else:
            print(f"[executor] Falha ao enviar media: {response_media.status_code} {response_media.text}")
    except Exception as e:
        print(f"[executor] Exceção ao enviar media: {e}")

def monitorar_pagamentos(col_snapshot, changes, read_time):
    for change in changes:
        if change.type.name in ('ADDED', 'MODIFIED'):
            doc = change.document.to_dict()
            telefone = change.document.id
            status = doc.get('status')
            plano = doc.get('plano', 'Iniciação')
            if status == 'ativo':
                # executar em thread para não bloquear o listener
                threading.Thread(target=entregar_negobot, args=(telefone, plano), daemon=True).start()

def start_executor():
    """
    Inicializa o listener e mantém o executor a correr.
    Chama-se a partir de um processo separado ou via import no app principal.
    """
    print("[executor] Iniciando executor e registando listener no Firestore...")
    assinantes_ref = db.collection('assinantes')
    assinantes_ref.on_snapshot(monitorar_pagamentos)
    # manter o processo vivo
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("[executor] Interrompido manualmente.")

if __name__ == "__main__":
    start_executor()
