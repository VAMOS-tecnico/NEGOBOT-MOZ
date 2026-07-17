import os
import json
import time
import requests
from flask import Flask, request
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# --- Rota de Saúde ---
@app.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Negobot está online e operacional! 🚀", 200

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

# Variável do assistente para evitar loops (Configurada no Render)
NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')


# ==========================================
#        FUNÇÕES AUXILIARES E DE API
# ==========================================

def verificar_ou_criar_cliente(phone_number):
    """Controla o período de teste de 2 dias do cliente no Firestore."""
    try:
        cliente_ref = db.collection('clientes').document(phone_number)
        doc = cliente_ref.get()
        agora = datetime.now(timezone.utc)

        if not doc.exists:
            dados_cliente = {
                "phone_number": phone_number,
                "data_registro": agora,
                "trial_start": agora,
                "status": "trial"  # Estados: 'trial', 'bloqueado', 'active'
            }
            cliente_ref.set(dados_cliente)
            return dados_cliente, True
        
        return doc.to_dict(), False
    except Exception as e:
        print(f"❌ Erro ao verificar/criar cliente: {e}")
        return None, False

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

def send_whatsapp(to, text, instance_name=None):
    """Envia mensagens de texto genéricas. Se não passar instância, usa a Master Central."""
    if not instance_name:
        instance_name = os.getenv('EVOLUTION_INSTANCE_NAME')
        
    url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{instance_name}"
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    payload = {"number": to, "text": text}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"DEBUG: Envio via [{instance_name}] Status: {response.status_code}")
    except Exception as e:
        print(f"ERRO ao enviar mensagem: {e}")

def desconectar_instancia_evolution(phone_number):
    """Envia um comando de LOGOUT para a Evolution API para destruir a sessão expirada."""
    try:
        instance_name = phone_number.split('@')[0]
        url = f"{os.getenv('EVOLUTION_API_URL')}/instance/logout/{instance_name}"
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        response = requests.post(url, headers=headers)
        print(f"🔄 [EVOLUTION] Logout executado na instância '{instance_name}'. Resposta: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Erro ao desconectar instância: {e}")
        return False

def gerar_e_enviar_qrcode_central(phone_number):
    """
    Gera uma nova sessão de QR Code e envia como Imagem pelo número Central Master.
    Trata instâncias abertas e limpa o cabeçalho Data URI do Base64.
    """
    try:
        client_instance = phone_number.split('@')[0]
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        # 1. Forçar a Evolution API a gerar uma nova sessão/QR Code
        url_connect = f"{os.getenv('EVOLUTION_API_URL')}/instance/connect/{client_instance}"
        response_connect = requests.get(url_connect, headers=headers)
        
        if response_connect.status_code != 200:
            print(f"❌ [API] Erro ao conectar instância {client_instance}: {response_connect.text}")
            return False
            
        dados_resposta = response_connect.json()
        
        # [Ajuste Ponto 1]: Se a instância já estiver aberta por segurança, avisa o cliente diretamente
        if dados_resposta.get("instance", {}).get("state") == "open":
            print(f"ℹ️ [API] A instância {client_instance} já está conectada e ativa.")
            send_whatsapp(phone_number, "✅ O seu assistente virtual já se encontra ativo e totalmente operacional no nosso sistema!")
            return True
            
        base64_qrcode = dados_resposta.get("base64")
        if not base64_qrcode:
            print(f"❌ [API] O campo 'base64' veio vazio. Resposta recebida: {dados_resposta}")
            return False

        # [Ajuste Ponto 2]: Remove o prefixo 'data:image/...;base64,' se existir para enviar a string limpa
        if "," in base64_qrcode:
            base64_qrcode = base64_qrcode.split(",")[1]

        # 2. Enviar a imagem do QR Code pelo WhatsApp Central Master
        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        url_send_media = f"{os.getenv('EVOLUTION_API_URL')}/message/sendMedia/{central_instance}"
        
        caption_text = (
            "✅ *Pagamento Confirmado com Sucesso!* 🎉\n\n"
            "Aqui está o seu novo **QR Code** para reativar o seu assistente virtual:\n\n"
            "1️⃣ Abra o seu WhatsApp pessoal ou da empresa.\n"
            "2️⃣ Vá a *Aparelhos Conectados* -> *Conectar um aparelho*.\n"
            "3️⃣ Aponte a câmara para este QR Code.\n\n"
            "Assim que escanear, o seu *Negobot Moz* voltará a trabalhar e a faturar imediatamente! 🚀"
        )
        
        payload_media = {
            "number": phone_number,
            "caption": caption_text,
            "media": base64_qrcode,
            "mediatype": "image",
            "fileName": "qrcode.png"  # Nome de arquivo estático para renderização correta
        }
        
        response_send = requests.post(url_send_media, headers=headers, json=payload_media)
        print(f"🔄 [AUTOPAY] Status de envio de média para {phone_number}: {response_send.status_code}")
        return response_send.status_code in [200, 201]

    except Exception as e:
        print(f"❌ Erro crítico no fluxo de envio de QR Code: {e}")
        return False


# ==========================================
#   ROTA 1: WEBHOOK DO ROBÔ DO CLIENTE
# ==========================================

@app.route('/webhook-cliente', methods=['POST'])
def webhook_cliente():
    data = request.json
    try:
        if data.get('event') == "messages.upsert" and "data" in data:
            msg_data = data['data']
            key = msg_data.get('key', {})
            
            if key.get('fromMe'): return 'OK', 200
            phone_number = key.get('remoteJid', '')
            
            if NUMERO_ASSISTANTE and NUMERO_ASSISTANTE in phone_number:
                return 'OK', 200
            if '@g.us' in phone_number:
                return 'OK', 200
            
            message = msg_data.get('message', {})
            message_text = ""
            if 'conversation' in message:
                message_text = message['conversation']
            elif 'extendedTextMessage' in message:
                message_text = message['extendedTextMessage'].get('text', '')

            if message_text and phone_number:
                cliente, eh_primeira_msg = verificar_ou_criar_cliente(phone_number)
                agora = datetime.now(timezone.utc)
                
                if cliente:
                    status = cliente.get('status', 'trial')
                    trial_start = cliente.get('trial_start')
                    if trial_start.tzinfo is None:
                        trial_start = trial_start.replace(tzinfo=timezone.utc)
                    
                    # Verificação de Expiração do Teste
                    if status == "trial":
                        if agora > (trial_start + timedelta(days=2)):
                            status = "bloqueado"
                            db.collection('clientes').document(phone_number).update({"status": "bloqueado"})
                    
                    # Fluxo de Bloqueio Ativo
                    if status == "bloqueado":
                        resposta_bloqueio = (
                            "⚠️ *Aviso de Expiração - Negobot Moz* ⚠️\n\n"
                            "O seu período de teste gratuito de **2 dias** chegou ao fim.\n\n"
                            "Para reativar o seu assistente virtual e continuar a responder aos seus clientes "
                            "e a fechar vendas automaticamente 24 horas por dia, siga estes passos:\n\n"
                            "1️⃣ Guarde o seu documento **PDF** com as informações da empresa.\n"
                            "2️⃣ Efetue o pagamento da subscrição via **M-Pesa**:\n"
                            "    • **Número M-Pesa:** 855000929\n"
                            "    • **Titular:** Abel Francisco\n\n"
                            "3️⃣ 📲 *PASSO CRÍTICO:* **Encaminhe a mensagem/SMS de confirmação da transferência** "
                            "para o nosso WhatsApp Central de Suporte.\n\n"
                            "🤖 O nosso sistema integrado (**Negobot Autopay**) vai comparar os dados do SMS automaticamente "
                            "para validar o depósito e libertar o seu novo acesso de imediato! Vamos elevar o seu negócio? 🚀"
                        )
                        # Envia o aviso pela própria instância do cliente antes de desligar
                        client_instance = phone_number.split('@')[0]
                        send_whatsapp(phone_number, resposta_bloqueio, instance_name=client_instance)
                        
                        # [Ajuste Ponto 3]: Delay estratégico de 3 segundos para garantir a entrega da mensagem
                        time.sleep(3)
                        
                        # Desliga e invalida o QR Code imediatamente na API
                        desconectar_instancia_evolution(phone_number)
                        return 'OK', 200

                # IA Responde normalmente se o cliente estiver Ativo ou dentro do Trial
                raw_history = get_chat_history(phone_number)
                recent_history = raw_history[-6:]
                
                contents = []
                for msg in recent_history:
                    role = "model" if msg.get('role') == "assistant" else msg.get('role')
                    parts = [types.Part.from_text(text=p.get('text', '')) for p in msg.get('parts', [])]
                    contents.append(types.Content(role=role, parts=parts))
                
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))

                sys_instruction = (
                    "Você é o Negobot Moz, um assistente virtual comercial de Moçambique, extremamente profissional, persuasivo e amigável. "
                    "Seu objetivo atual é guiar o cliente que está a usar o nosso sistema em período de teste gratuito.\n\n"
                    "REGRAS CRÍTICAS DE COMPORTAMENTO:\n"
                    "1. ABORDAGEM INICIAL DE ALTO IMPACTO (PRIMEIRA MENSAGEM DO TESTE):\n"
                    "   Se for a primeiríssima mensagem do cliente, apresente o teste com esta estrutura:\n"
                    "   'Olá! Que bom ter por aqui. Já imaginou o seu WhatsApp a trabalhar por si 24 horas por dia, a responder clientes e a fechar vendas automaticamente? É exatamente isso que o Negobot Moz faz. O seu período de teste gratuito de 2 dias já está ativo! Aproveite para ver a máquina a funcionar. Como posso ajudar o seu negócio hoje?'\n\n"
                    "2. FILOSOFIA DE ATENDIMENTO DURANTE O TESTE:\n"
                    "   - Demonstre total capacidade de automação. Explique as vantagens do sistema (atendimento 24/7, parágrafos organizados, respostas rápidas).\n"
                    "   - Se o cliente perguntar como deixar definitivo, explique que após os 2 dias ele precisará de enviar o PDF da empresa e realizar o pagamento via M-Pesa para ativação permanente.\n\n"
                    "3. NÃO seja uma IA de pesquisa geral. Não responda a perguntas de cultura geral, matemática ou outros temas.\n\n"
                    "4. IDENTIDADE DO CRIADOR: Se perguntarem quem te criou, "
                    "responda: 'Fui desenvolvido pelo empresário Abel Francisco, um reconhecido empreendedor do ramo "
                    "automotivo e imobiliário em Moçambique, licenciado em Contabilidade e Auditoria.'\n\n"
                    "5. PLANOS E PREÇOS:\n"
                    "   - Plano Inicial: 500 Meticais\n"
                    "   - Plano Avançado: 1000 Meticais\n\n"
                    "6. DADOS DE COBRANÇA (M-PESA):\n"
                    "   - Número do M-Pesa: 855000929\n"
                    "   - Nome do Titular: Abel Francisco\n\n"
                    "7. Use negritos e mensagens organizadas por parágrafos curtos para facilitar a leitura no WhatsApp."
                )

                if eh_primeira_msg:
                    sys_instruction += "\n[CONTEXTO]: Primeira mensagem do cliente. Execute a Regra 1 estritamente."

                config = types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.2)
                response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
                response_text = response.text
                
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))
                save_chat_history(phone_number, [{"role": c.role, "parts": [{"text": p.text} for p in c.parts]} for c in contents[-10:]])

                client_instance = phone_number.split('@')[0]
                send_whatsapp(phone_number, response_text, instance_name=client_instance)

    except Exception as e:
        print(f"ERRO CRÍTICO NO WEBHOOK DO CLIENTE: {e}")
    return 'OK', 200


# ==========================================
#   ROTA 2: WEBHOOK DO AUTOPAY CENTRAL
# ==========================================

@app.route('/webhook-central', methods=['POST'])
def webhook_central():
    data = request.json
    try:
        if data.get('event') == "messages.upsert" and "data" in data:
            msg_data = data['data']
            key = msg_data.get('key', {})
            
            if key.get('fromMe'): return 'OK', 200
            
            # O remetente da mensagem para a Central é o número do cliente que pagou
            phone_number = key.get('remoteJid', '')
            if '@g.us' in phone_number: return 'OK', 200
            
            message = msg_data.get('message', {})
            message_text = ""
            if 'conversation' in message:
                message_text = message['conversation']
            elif 'extendedTextMessage' in message:
                message_text = message['extendedTextMessage'].get('text', '')

            # Lógica do Negobot Autopay: Compara se a mensagem colada é um SMS válido do M-Pesa
            if message_text and phone_number:
                msg_clean = message_text.lower()
                
                # Padrões comuns de confirmação de transferência do M-Pesa em Moçambique
                if "recebeu" in msg_clean or "confirmado" in msg_clean or "transacao" in msg_clean:
                    print(f"💳 [AUTOPAY] Possível SMS de pagamento detetado vindo de {phone_number}.")
                    
                    # 1. Atualiza o status do cliente para Ativo no Firebase
                    db.collection('cli... [message truncated]
