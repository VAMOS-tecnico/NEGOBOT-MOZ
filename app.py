import os
import json
import requests
from flask import Flask, request
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# --- Rota de Saúde ---
@app.route('/', methods=['GET'])
def health_check():
    return "O bot está online!", 200

# Inicialização do Firebase
firebase_config_env = os.getenv('FIREBASE_CONFIG')
if firebase_config_env:
    try:
        firebase_config = json.loads(firebase_config_env)
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
    except Exception:
        firebase_admin.initialize_app()
else:
    firebase_admin.initialize_app()

db = firestore.client()

# Instanciar o Cliente Gemini
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
MODEL_NAME = 'gemini-3.1-flash-lite'

def get_chat_history(phone_number):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('history', [])
    except Exception as e:
        print(f"Erro ao obter historico: {e}")
    return []

def save_chat_history(phone_number, history):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc_ref.set({"history": history}, merge=True)
    except Exception as e:
        print(f"Erro ao salvar historico: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        if data.get('event') == "messages.upsert" and "data" in data:
            msg_data = data['data']
            key = msg_data.get('key', {})
            
            if key.get('fromMe'): return 'OK', 200
            
            phone_number = key.get('remoteJid', '')
            if '@g.us' in phone_number:
                return 'OK', 200
            
            message = msg_data.get('message', {})
            message_text = ""
            
            if 'conversation' in message:
                message_text = message['conversation']
            elif 'extendedTextMessage' in message:
                message_text = message['extendedTextMessage'].get('text', '')

            if message_text and phone_number:
                raw_history = get_chat_history(phone_number)
                recent_history = raw_history[-6:]
                
                contents = []
                for msg in recent_history:
                    role = "model" if msg.get('role') == "assistant" else msg.get('role')
                    parts = [types.Part.from_text(text=p.get('text', '')) for p in msg.get('parts', [])]
                    contents.append(types.Content(role=role, parts=parts))
                
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))

                # --- 🌟 CONFIGURAÇÃO DE IDENTIDADE E RESPOSTAS FRACIONADAS 🌟 ---
                sys_instruction = (
                    "Você é o Negobot Moz, um assistente virtual comercial de Moçambique, profissional e muito amigável. "
                    "Seu objetivo é apresentar e vender o serviço de automação de WhatsApp para pequenas e médias empresas.\n\n"
                    "REGRAS CRÍTICAS DE COMPORTAMENTO:\n"
                    "1. RESPOSTAS FRACIONADAS E DIRECIONADAS (REGRA DE OURO): Nunca envie todas as informações do negócio de uma única vez. "
                    "Responda estritamente e apenas à pergunta que o usuário fez no momento. Mantenha as mensagens curtas, naturais e em formato de diálogo.\n"
                    "   - Se ele saudar, apenas saúde de volta e pergunte como pode ajudar.\n"
                    "   - Se ele perguntar o preço, mostre APENAS os planos. Não mande os dados de pagamento ainda.\n"
                    "   - Se ele perguntar quem criou, responda APENAS sobre o criador.\n"
                    "   - Só envie os dados do M-Pesa se ele disser claramente que quer assinar, avançar ou pagar.\n"
                    "2. NÃO seja uma IA de pesquisa geral. Não responda a perguntas de cultura geral, matemática ou outros temas. "
                    "Traga o cliente de volta ao assunto do Negobot Moz com educação.\n"
                    "3. IDENTIDADE DO CRIADOR: Se perguntarem 'Quem te fez?', 'Quem te criou?' ou 'Quem é seu dono?', "
                    "responda: 'Fui desenvolvido pelo empresário Abel Francisco, um reconhecido empreendedor do ramo "
                    "automotivo e imobiliário em Moçambique, licenciado em Contabilidade e Auditoria.'\n"
                    "4. PLANOS E PREÇOS:\n"
                    "   - Plano Inicial: 500 Meticais\n"
                    "   - Plano Avançado: 1000 Meticais\n"
                    "5. DADOS DE COBRANÇA (M-PESA): Quando solicitados pelo cliente para fechar a compra, envie:\n"
                    "   - Número do M-Pesa: 855000929\n"
                    "   - Nome do Titular: Abel Francisco\n"
                    "   Explique brevemente que o nosso sistema integrado (NegoBoto Autopay) valida o SMS de forma automática e gera o QR Code na hora.\n"
                    "6. Use negritos e mensagens organizadas por parágrafos curtos para facilitar a leitura no WhatsApp."
                )

                # Temperatura baixa garante foco total no diálogo sem inventar dados extras
                config = types.GenerateContentConfig(
                    system_instruction=sys_instruction,
                    temperature=0.2
                )

                # Gerar resposta
                response = client.models.generate_content(
                    model=MODEL_NAME, 
                    contents=contents,
                    config=config
                )
                response_text = response.text
                
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))
                save_chat_history(phone_number, [{"role": c.role, "parts": [{"text": p.text} for p in c.parts]} for c in contents[-10:]])

                send_whatsapp(phone_number, response_text)

    except Exception as e:
        print(f"ERRO CRÍTICO: {e}")
        
    return 'OK', 200

def send_whatsapp(to, text):
    url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{os.getenv('EVOLUTION_INSTANCE_NAME')}"
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    payload = {"number": to, "text": text}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"DEBUG: Resposta da API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"ERRO ao enviar: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
