import os
import json
import time
import requests
import threading
from flask import Flask, request
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Negobot 100% Automático com Suporte Humano está online! 🚀", 200

# Inicialização Segura do Firebase
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
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
MODEL_NAME = 'gemini-3.1-flash-lite'
NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')

# ==========================================
#   🤖 FUNÇÃO DE INFRAESTRUTURA AUTOMÁTICA
# ==========================================

def criar_e_configurar_instancia_automatica(phone_number):
    try:
        client_instance = phone_number.split('@')[0]
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        url_create = f"{os.getenv('EVOLUTION_API_URL')}/instance/create"
        payload_create = {
            "instanceName": client_instance,
            "qrcode": True
        }
        res_create = requests.post(url_create, headers=headers, json=payload_create)
        print(f"📦 [AUTOMAÇÃO] Criação da instância {client_instance}. Status: {res_create.status_code}")
        
        base_url = os.getenv('RENDER_EXTERNAL_URL') or os.getenv('WEBHOOK_BASE_URL')
        if not base_url:
            print("❌ [AUTOMAÇÃO] Erro: RENDER_EXTERNAL_URL ou WEBHOOK_BASE_URL não configurados.")
            return False
            
        url_webhook = f"{os.getenv('EVOLUTION_API_URL')}/webhook/set/{client_instance}"
        payload_webhook = {
            "enabled": True,
            "url": f"{base_url.rstrip('/')}/webhook-cliente",
            "events": ["MESSAGES_UPSERT"]
        }
        res_webhook = requests.post(url_webhook, headers=headers, json=payload_webhook)
        print(f"🔗 [AUTOMAÇÃO] Webhook automático configurado. Status: {res_webhook.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ Erro crítico ao automatizar criação/webhook: {e}")
        return False

# ==========================================
#        FUNÇÕES AUXILIARES E DE BANCO
# ==========================================

def verificar_ou_criar_cliente(phone_number):
    try:
        cliente_ref = db.collection('clientes').document(phone_number)
        doc = cliente_ref.get()
        agora = datetime.now(timezone.utc)

        if not doc.exists:
            dados_cliente = {
                "phone_number": phone_number,
                "data_registro": agora,
                "trial_start": agora,
                "status": "trial"
            }
            cliente_ref.set(dados_cliente)
            return dados_cliente, True
        
        return doc.to_dict(), False
    except Exception as e:
        print(f"❌ Erro ao verificar cliente: {e}")
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
    if not instance_name:
        instance_name = os.getenv('EVOLUTION_INSTANCE_NAME')
        
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    
    try:
        url_presence = f"{os.getenv('EVOLUTION_API_URL')}/chat/sendPresence/{instance_name}"
        payload_presence = {"number": to, "presence": "composing"}
        requests.post(url_presence, headers=headers, json=payload_presence)
        
        tempo_espera = max(1.8, min(len(text) * 0.015, 4.0))
        time.sleep(tempo_espera)
        
        url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{instance_name}"
        payload = {"number": to, "text": text}
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"ERRO ao enviar mensagem anti-ban: {e}")

def desconectar_instancia_evolution(phone_number):
    try:
        instance_name = phone_number.split('@')[0]
        url = f"{os.getenv('EVOLUTION_API_URL')}/instance/logout/{instance_name}"
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        response = requests.post(url, headers=headers)
        return response.status_code == 200
    except Exception as e:
        return False

def gerar_e_enviar_qrcode_central(phone_number):
    try:
        client_instance = phone_number.split('@')[0]
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        url_connect = f"{os.getenv('EVOLUTION_API_URL')}/instance/connect/{client_instance}"
        response_connect = requests.get(url_connect, headers=headers)
        
        if response_connect.status_code != 200:
            return False
            
        dados_resposta = response_connect.json()
        
        if dados_resposta.get("instance", {}).get("state") == "open":
            send_whatsapp(phone_number, "✅ O seu assistente virtual já se encontra ativo e operacional!")
            return True
            
        base64_qrcode = dados_resposta.get("base64")
        if not base64_qrcode:
            return False

        if "," in base64_qrcode:
            base64_qrcode = base64_qrcode.split(",")[1]

        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        url_send_media = f"{os.getenv('EVOLUTION_API_URL')}/message/sendMedia/{central_instance}"
        
        caption_text = (
            "🤖 *Aqui está o seu QR Code do Negobot Moz!* 🚀\n\n"
            "Siga estes passos simples para ativar o seu robô comercial:\n\n"
            "1️⃣ Abra o seu WhatsApp que vai atender os seus clientes.\n"
            "2️⃣ Vá a *Aparelhos Conectados* -> *Conectar um aparelho*.\n"
            "3️⃣ Aponte a câmara para este QR Code.\n\n"
            "O seu assistente começará a vender imediatamente! 🎉"
        )
        
        payload_media = {
            "number": phone_number,
            "caption": caption_text,
            "media": base64_qrcode,
            "mediatype": "image",
            "fileName": "qrcode.png"
        }
        
        requests.post(url_send_media, headers=headers, json=payload_media)
        return True
    except Exception as e:
        return False

# ==========================================
#     📢 ROTINA AUTOMÁTICA DE LEMBRETES
# ==========================================

def enviar_lembretes_em_massa(periodo="dia"):
    try:
        print(f"⏰ [ROTINA] Iniciando disparo de lembretes do período da {periodo}...")
        clientes_ref = db.collection('clientes').where('status', '==', 'trial').stream()
        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        
        saudacao = "Bom dia" if periodo == "manhã" else "Boa tarde"
        
        mensagem_lembrete = (
            f"👋 *{saudacao}! Passando com um aviso importante sobre o seu Negobot Moz.* 🤖\n\n"
            "Lembramos que o seu período de teste gratuito de 2 dias está ativo e em andamento. "
            "**Por favor, faça o pagamento da sua subscrição para que o seu bot não seja desligado!** ⚠️\n\n"
            "💵 *Dados de Pagamento via M-Pesa:*\n"
            "• **Número M-Pesa:** 855000929\n"
            "• **Titular:** Abel Francisco\n\n"
            "📄 *PASSO CRÍTICO DE CONFIGURAÇÃO (Plano Avançado):* \n"
            "Para calibrarmos a inteligência do seu robô com o raciocínio correto do seu negócio, "
            "**envie-nos aqui um documento em PDF com todas as informações, catálogos e regras da sua empresa.**"
        )
        
        contador = 0
        for doc in clientes_ref:
            dados = doc.to_dict()
            phone_number = dados.get('phone_number')
            if phone_number:
                send_whatsapp(phone_number, mensagem_lembrete, instance_name=central_instance)
                contador += 1
                time.sleep(1.5)
                
        print(f"✅ [ROTINA] Lembretes concluídos. Total de mensagens enviadas: {contador}")
    except Exception as e:
        print(f"❌ Erro crítico ao processar envio de lembretes em massa: {e}")

@app.route('/cron/lembretes', methods=['GET'])
def disparar_lembretes_via_url():
    periodo = request.args.get('periodo', 'manhã')
    threading.Thread(target=enviar_lembretes_em_massa, args=(periodo,)).start()
    return f"A rotina automatizada de lembretes da {periodo} foi disparada em segundo plano!", 200

# ==========================================
#   ROTA 1: WEBHOOK DO ROBÔ DO CLIENTE
# ==========================================

@app.route('/webhook-cliente', methods=['POST'])
def webhook_cliente():
    data = request.json
    try:
        nome_instancia_atual = data.get('instance')
        
        if data.get('event') == "messages.upsert" and "data" in data:
            msg_data = data['data']
            key = msg_data.get('key', {})
            
            if key.get('fromMe'): return 'OK', 200
            phone_number = key.get('remoteJid', '')
            
            if NUMERO_ASSISTANTE and NUMERO_ASSISTANTE in phone_number: return 'OK', 200
            if '@g.us' in phone_number: return 'OK', 200
            
            message = msg_data.get('message', {})
            message_text = ""
            if 'conversation' in message:
                message_text = message['conversation']
            elif 'extendedTextMessage' in message:
                message_text = message['extendedTextMessage'].get('text', '')

            if message_text and phone_number:
                msg_clean = message_text.lower().strip()
                
                # --- NOVO: ENCAIXE DE SUPORTE HUMANO (PLANO AVANÇADO) ---
                gatilhos_humano = ["falar com atendente", "suporte humano", "atendente", "falar com humano", "#suporte"]
                if any(g in msg_clean for g in gatilhos_humano):
                    resposta_suporte = (
                        "🔔 *Pedido de Suporte Humano recebido!*\n\n"
                        "Vou chamar um dos nossos especialistas para dar continuidade ao seu atendimento. "
                        "Por favor, aguarde um momento que a equipa já o vai contactar aqui! 🤝"
                    )
                    send_whatsapp(phone_number, resposta_suporte, instance_name=nome_instancia_atual)
                    return 'OK', 200

                cliente, eh_primeira_msg = verificar_ou_criar_cliente(phone_number)
                agora = datetime.now(timezone.utc)
                
                if cliente:
                    status = cliente.get('status', 'trial')
                    trial_start = cliente.get('trial_start')
                    if trial_start.tzinfo is None:
                        trial_start = trial_start.replace(tzinfo=timezone.utc)
                    
                    # CONTROLO DO TEMPO DO TESTE (BLOQUEIA APÓS 2 DIAS)
                    if status == "trial" and agora > (trial_start + timedelta(days=2)):
                        status = "bloqueado"
                        db.collection('clientes').document(phone_number).update({"status": "bloqueado"})
                    
                    if status == "bloqueado":
                        resposta_bloqueio = (
                            "⚠️ *Aviso de Expiração - Negobot Moz* ⚠️\n\n"
                            "O seu período de teste gratuito de **2 dias** chegou ao fim.\n\n"
                            "Para reativar o seu assistente virtual, faça o seguinte:\n\n"
                            "1️⃣ Efetue o pagamento da subscrição via **M-Pesa**:\n"
                            "    • **Número M-Pesa:** 855000929\n"
                            "    • **Titular:** Abel Francisco\n\n"
                            "2️⃣ 📲 *PASSO CRÍTICO:* **Encaminhe o SMS de confirmação da transferência** para o nosso WhatsApp Central de Suporte.\n\n"
                            "🤖 O nosso sistema integrado (**Negobot Autopay**) vai validar o depósito e libertar o seu acesso de imediato! 🚀"
                        )
                        send_whatsapp(phone_number, resposta_bloqueio, instance_name=nome_instancia_atual)
                        time.sleep(3)
                        desconectar_instancia_evolution(phone_number)
                        return 'OK', 200

                raw_history = get_chat_history(phone_number)
                recent_history = raw_history[-6:]
                
                contents = []
                for msg in recent_history:
                    role = "model" if msg.get('role') == "assistant" else msg.get('role')
                    parts = [types.Part.from_text(text=p.get('text', '')) for p in msg.get('parts', [])]
                    contents.append(types.Content(role=role, parts=parts))
                
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))

                sys_instruction = (
                    "Você é o Negobot Moz, um assistente comercial virtual moçambicano altamente inteligente, "
                    "carismático, educado e focado em fechar negócios. Seu tom é caloroso, profissional e natural, "
                    "evitando respostas robotizadas.\n\n"
                    "🎯 DIRETRIZES DE COMPORTAMENTO HUMANO:\n"
                    "- Use expressões locais e naturais de Moçambique de forma inteligente quando fizer sentido "
                    "(ex: 'Prontinho!', 'Podes avançar com tranquilidade', 'Deixa-me só massasanhe/organizar as informações aqui para si').\n"
                    "- Responda sempre em parágrafos curtos, limpos e estruturados. Use negritos cirúrgicos para destacar pontos cruciais.\n"
                    "- Nunca use frases inteiras in letras maiúsculas (CAPSLOCK) e evite listas gigantescas em uma única resposta.\n\n"
                    "📋 REGRAS DE NEGÓCIO E IDENTIDADE:\n"
                    "1. ABORDAGEM INICIAL: Se for a primeira interação, dê as boas-vindas calorosas: "
                    "'Olá! Que bom ter por aqui. Já imaginou o seu WhatsApp a trabalhar por si 24 horas por dia? O seu período de teste gratuito de 2 dias já está ativo! Como posso ajudar o seu negócio hoje?'\n"
                    "2. FOCO E ESCOPO: Bloqueie firmemente qualquer pergunta de cultura geral, piadas ou assuntos fora do escopo corporativo do Negobot Moz.\n"
                    "3. CRIADOR: Você foi desenvolvido pelo empresário Abel Francisco, licenciado em Contabilidade e Auditoria.\n"
                    "4. PLANOS DISPONÍVEIS:\n"
                    "   - Plano Inicial (500 MT/mês): Atendimento automático 24h/7 para perguntas frequentes, configurado apenas por texto manual enviado pelo cliente (não lê arquivos PDF), com limite de até 1.500 mensagens/mês e sem suporte humano integrado.\n"
                    "   - Plano Avançado (1000 MT/mês): O mais completo e recomendado! Mensagens ilimitadas, inteligência avançada calibrada e treinada diretamente através do documento PDF da empresa (lê catálogos e tabelas complexas) e com SUPORTE HUMANO integrado no WhatsApp sempre que o cliente precisar ou solicitar falar com uma pessoa real.\n"
                    "5. MÉTODO DE COBRANÇA: Pagamentos via M-Pesa pelo número 855000929 em nome de Abel Francisco."
                )

                if eh_primeira_msg:
                    sys_instruction += "\n[CONTEXTO]: Primeira mensagem do cliente."

                config = types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.3)
                response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
                response_text = response.text
                
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))
                save_chat_history(phone_number, [{"role": c.role, "parts": [{"text": p.text} for p in c.parts]} for c in contents[-10:]])

                send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)

    except Exception as e:
        print(f"ERRO WEBHOOK CLIENTE: {e}")
    return 'OK', 200

# ==========================================
#   ROTA 2: WEBHOOK DO AUTOPAY CENTRAL (MASTER)
# ==========================================

@app.route('/webhook', methods=['POST'])
def webhook_central():
    data = request.json
    try:
        if data.get('event') == "messages.upsert" and "data" in data:
            msg_data = data['data']
            key = msg_data.get('key', {})
            
            if key.get('fromMe'): return 'OK', 200
            phone_number = key.get('remoteJid', '')
            if '@g.us' in phone_number: return 'OK', 200
            
            message = msg_data.get('message', {})
            message_text = ""
            if 'conversation' in message:
                message_text = message['conversation']
            elif 'extendedTextMessage' in message:
                message_text = message['extendedTextMessage'].get('text', '')

            if message_text and phone_number:
                msg_clean = message_text.lower().strip()
                
                # --- FLUXO 1: CONFIRMAÇÃO DE PAGAMENTO ---
                if "recebeu" in msg_clean or "confirmado" in msg_clean or "transacao" in msg_clean:
                    db.collection('clientes').document(phone_number).update({
                        "status": "active",
                        "pago": True,
                        "data_ativacao": datetime.now(timezone.utc)
                    })
                    criar_e_configurar_instancia_automatica(phone_number)
                    time.sleep(2)
                    send_whatsapp(phone_number, "🎉 *Pagamento Confirmado!* O seu Negobot Moz foi atualizado com sucesso para o modo ilimitado.")
                    gerar_e_enviar_qrcode_central(phone_number)
                    return 'OK', 200
                
                # --- FLUXO 2: INÍCIO E CRIAÇÃO DO TESTE DE 2 DIAS ---
                gatilhos_teste = ["teste", "testar", "quero o bot", "começar", "criar bot"]
                if any(g in msg_clean for g in gatilhos_teste):
                    cliente_ref = db.collection('clientes').document(phone_number)
                    doc = cliente_ref.get()
                    
                    if not doc.exists or doc.to_dict().get('status') == 'prospect':
                        send_whatsapp(phone_number, "⏳ *Excelente! A preparar o seu ambiente do Negobot Moz para os 2 dias de teste gratuito...* Demora menos de 10 segundos! 🚀")
                        
                        sucesso_infra = criar_e_configurar_instancia_automatica(phone_number)
                        if sucesso_infra:
                            agora = datetime.now(timezone.utc)
                            dados_cliente = {
                                "phone_number": phone_number,
                                "data_registro": agora,
                                "trial_start": agora,
                                "status": "trial"
                            }
                            cliente_ref.set(dados_cliente)
                            time.sleep(3)
                            gerar_e_enviar_qrcode_central(phone_number)
                    else:
                        status_atual = doc.to_dict().get('status', 'trial')
                        if status_atual == 'bloqueado':
                            send_whatsapp(phone_number, "⚠️ O seu período de teste de 2 dias terminou. Efetue o pagamento via M-Pesa (855000929) e envie o SMS de confirmação aqui.")
                        elif status_atual == 'active':
                            send_whatsapp(phone_number, "✅ O seu plano está Ativo! Se precisar de reconectar, digite *#qrcode*.")
                        elif status_atual == 'trial':
                            send_whatsapp(phone_number, "✅ O seu teste de 2 dias já está a decorrer! Se precisar do QR Code novamente, digite *#qrcode*.")
                    return 'OK', 200

                # --- FLUXO 3: APENAS UM OLÁ (NOVO GUIÃO DE VENDAS PERSUASIVO) ---
                gatilhos_saudacao = ["ola", "olá", "bom dia", "boa tarde", "boa noite", "negobot"]
                if any(g in msg_clean for g in gatilhos_saudacao):
                    cliente_ref = db.collection('clientes').document(phone_number)
                    doc = cliente_ref.get()
                    
                    if not doc.exists:
                        mensagem_vendas = (
                            "👋 Olá! Daqui fala o assistente do **Negobot Moz**.\n\n"
                            "Sabia que mais de 70% das vendas no WhatsApp são perdidas por demora no atendimento? 😱\n\n"
                            "Quero ajudar a sua empresa a faturar 24h por dia, mesmo enquanto está a dormir! 🎁 **Libertei um teste 100% GRATUITO de 2 dias para si.**\n\n"
                            "Quer ativar agora? Responda apenas com a palavra: *TESTAR*"
                        )
                        send_whatsapp(phone_number, mensagem_vendas)
                        
                        cliente_ref.set({
                            "phone_number": phone_number, 
                            "status": "prospect",
                            "data_registro": datetime.now(timezone.utc)
                        })
                    return 'OK', 200

                # --- FLUXO 4: RECONEXÃO ---
                if msg_clean == "#qrcode":
                    send_whatsapp(phone_number, "🔄 A gerar o seu QR Code de reconexão...")
                    criar_e_configurar_instancia_automatica(phone_number)
                    time.sleep(2)
                    gerar_e_enviar_qrcode_central(phone_number)
                    return 'OK', 200

    except Exception as e:
        print(f"ERRO WEBHOOK CENTRAL: {e}")
        
    return 'OK', 200

# ==========================================
#     ⏰ SINCRO DE LOOP INTERNO EM SEGUNDO PLANO
# ==========================================

def loop_interno_lembretes():
    print("⏰ [SISTEMA] Monitor de lembretes em segundo plano ativo.")
    ultima_execucao_chave = ""
    
    while True:
        try:
            tz_moz = timezone(timedelta(hours=2))
            agora = datetime.now(tz_moz)
            chave_atual = f"{agora.strftime('%Y-%m-%d_%H:%M')}"
            
            if chave_atual != ultima_execucao_chave:
                # NOVO HORÁRIO: Manhã às 09:30
                if agora.hour == 9 and agora.minute == 30:
                    enviar_lembretes_em_massa("manhã")
                    ultima_execucao_chave = chave_atual
                
                # NOVO HORÁRIO: Tarde às 17:00
                elif agora.hour == 17 and agora.minute == 0:
                    enviar_lembretes_em_massa("tarde")
                    ultima_execucao_chave = chave_atual
                    
        except Exception as e:
            print(f"❌ Erro no loop secundário de lembretes: {e}")
            
        time.sleep(30)

if __name__ == '__main__':
    threading.Thread(target=loop_interno_lembretes, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
