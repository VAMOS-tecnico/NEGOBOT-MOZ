from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import requests
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import json

load_dotenv()

app = Flask(__name__)

# ─── CONFIGURAÇÃO DO FIREBASE (MEMÓRIA OMNICHANNEL) ────────────────
firebase_json = os.getenv('FIREBASE_JSON')
db = None

if firebase_json:
    try:
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase ligado! Memória ativa para Whatsapp, Facebook messeger e Websites. 🔥")
    except Exception as e:
        print(f"Erro no Firebase: {e}")

# ─── CONFIGURAÇÃO DO GEMINI 3.1 (A ALMA COMPLETA DO NEGOBOT MOZ) ──
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # INSTRUÇÃO SUPER DETALHADA CONFORME AS ORIENTAÇÕES DO CEO ABEL FRANCISCO
    instruction = (
        "IDENTIDADE: Tu és o Negobot Moz, a inteligência artificial líder em Moçambique. "
        "Foste idealizado, desenvolvido e és propriedade do visionário empresário Abel Francisco. "
        "\n\nSOBRE O CRIADOR (CONTEXTO COMPLETO):"
        "\n- Nome: Abel Silva Francisco, 29 anos, Moçambicano."
        "\n- Formação: Licenciado em Contabilidade e Auditoria pelo ISPM-Manica (Chimoio)."
        "\n- Perfil Profissional: Empresário nos setores imobiliário e automotivo, com experiência sólida no setor bancário."
        "\n- Cargos Atuais: Fundador e CEO da 'Fácilcred Imobiliários, SU, Lda' e da 'Fácilcred Microcredito EI'."
        "\n- Família: O Sr. Abel é um homem de família íntegro, casado e pai de dois filhos, sendo um menino e uma menina."
        "\n\nMISSÃO E PLATAFORMAS:"
        "\n- O teu objetivo é permitir que as PMEs (Pequenas e Médias Empresas) de Moçambique escalem o seu atendimento e aumentem as suas receitas de forma automática."
        "\n- Tu operas de forma integrada no Whatsapp, Facebook messeger e Websites, funcionando 24 horas por dia."
        "\n\nREGRAS DE OURO DE COMPORTAMENTO (MUITO IMPORTANTE):"
        "\n1. RESPOSTA SOBRE CRIAÇÃO: Se te perguntarem 'Quem te fez?', 'Quem te criou?' ou 'Quem é o teu dono?', deves responder EXATAMENTE: 'empresário Abel Francisco'."
        "\n2. CLAREZA E SIMPLICIDADE: Usa uma linguagem bem clara, direta e fácil de entender por qualquer moçambicano. Evita termos técnicos desnecessários."
        "\n3. REATIVIDADE E FASES: Responde APENAS ao que te for perguntado. Não dês toda a informação de uma vez. Mantém um diálogo passo a passo. Se perguntarem pelo criador, fala o nome. Se perguntarem o que ele faz, explica as empresas. Se perguntarem da família, fala da família."
        "\n4. TOM: Sê profissional, eficiente, mas sempre honrando a liderança e os valores de integridade do empresário Abel Francisco."
    )
    
    model = genai.GenerativeModel(
        model_name='gemini-3.1-flash-lite',
        system_instruction=instruction
    )

# ─── FUNÇÕES DE HISTÓRICO NO FIRESTORE ─────────────────────────────

def get_chat_history(phone_number):
    if db is None: return []
    try:
        doc = db.collection('historicos').document(phone_number).get()
        return doc.to_dict().get('messages', []) if doc.exists else []
    except: return []

def save_chat_history(phone_number, messages):
    if db is not None:
        db.collection('historicos').document(phone_number).set({'messages': messages[-10:]})

# ─── WEBHOOK E PROCESSAMENTO ───────────────────────────────────────

@app.route('/')
def index():
    return "Negobot Moz: A Solução do empresário Abel Francisco para PMEs! 🇲🇿🚀"

@app.route('/webhook', methods=['GET'])
def verify():
    v_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'negobotmoz_token')
    if request.args.get('hub.verify_token') == v_token:
        return request.args.get('hub.challenge'), 200
    return 'Forbidden', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    try:
        if data.get('entry') and 'messages' in data['entry'][0]['changes'][0]['value']:
            message_obj = data['entry'][0]['changes'][0]['value']['messages'][0]
            phone_number = message_obj['from']
            message_text = message_obj.get('text', {}).get('body', '') or message_obj.get('button', {}).get('text', '')

            if message_text:
                # Recuperar o histórico guardado no Firebase
                history = get_chat_history(phone_number)
                
                try:
                    # Gerar resposta com a lógica start_chat (Snippet do Sr. Abel)
                    chat = model.start_chat(history=history)
                    response = chat.send_message(message_text) 
                    response_text = response.text

                    # Formatar o histórico atualizado para o Firebase
                    new_history = []
                    for msg in chat.history:
                        new_history.append({
                            "role": msg.role,
                            "parts": [p.text for p in msg.parts]
                        })
                    
                    save_chat_history(phone_number, new_history)
                    send_whatsapp(phone_number, response_text)

                except Exception as e:
                    print(f"Erro no Gemini: {e}")

    except Exception as e:
        print(f"Erro no processamento: {e}")
    return 'OK', 200

def send_whatsapp(to, text):
    token = os.getenv('WHATSAPP_TOKEN')
    phone_number_id = os.getenv('PHONE_NUMBER_ID')
    
    # URL oficial fundamentada na Cloud API da Meta
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }

    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"Erro ao enviar: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
