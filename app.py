import os
import json
import time
import requests
import threading
import re
import random
import io
import base64
import tempfile
import urllib.parse
from flask import Flask, request
from datetime import datetime, timedelta, timezone

# Processamento de Documentos e Planilhas (PDF e Excel)
from pypdf import PdfReader
import pandas as pd

# Firebase Admin
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# Configuração de Timeout para Atendimento Humano (Tempo em minutos)
TIMEOUT_HUMANO_MINUTOS = int(os.getenv('TIMEOUT_HUMANO_MINUTOS', 2))

@app.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Multilocatário Negobot Moz está 100% operacional, blindado contra alucinações e com memória protegida! 🚀", 200

# ==========================================
#   📦 INICIALIZAÇÃO SEGURA DO FIREBASE
# ==========================================
firebase_config_env = os.getenv('FIREBASE_CONFIG')
if firebase_config_env:
    try:
        firebase_config = json.loads(firebase_config_env)
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        print("📦 [SISTEMA] Firebase inicializado com credenciais da ENV.")
    except Exception as e:
        print(f"⚠️ [SISTEMA] Falha ao carregar FIREBASE_CONFIG da ENV: {e}. Tentando padrão...")
        try:
            firebase_admin.initialize_app()
        except Exception as ex:
            print(f"❌ [SISTEMA] Erro crítico ao inicializar Firebase: {ex}")
else:
    try:
        firebase_admin.initialize_app()
        print("📦 [SISTEMA] Firebase inicializado com configurações padrão.")
    except Exception as e:
        print(f"❌ [SISTEMA] Erro crítico na inicialização padrão do Firebase: {e}")

db = firestore.client()

# ==========================================
#   CONFIGURAÇÕES DA API GROQ
# ==========================================
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'qwen-2.5-32b')

NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')
ADMIN_NUMBER = os.getenv('ADMIN_NUMBER')

# ==========================================
#   🌐 CHAMADA REST DIRETA PARA GROQ API
#   (temperature=0.0 para determinismo estrito)
# ==========================================
def chamar_groq_rest(contents_payload, system_instruction="", temperature=0.0):
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY não encontrada nas variáveis de ambiente.")
        return ""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})

    for item in contents_payload:
        role = item.get("role", "user")
        if role in ["model", "assistant", "atendente"]:
            role = "assistant"
        
        parts = item.get("parts", [])
        texto_msg = "".join([p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p])
        
        if texto_msg:
            messages.append({"role": role, "content": texto_msg})

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 700
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        data = response.json()
        
        if response.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"❌ Erro na API do Groq (Status {response.status_code}): {data}")
    except Exception as e:
        print(f"❌ Exceção ao chamar Groq API: {e}")

    return "Desculpe, estamos a receber muitas mensagens. Por favor, tente novamente em instantes!"

# ==========================================
#   🎙️ TRANSCRIÇÃO DE ÁUDIO (WHISPER) PROTEGIDA
# ==========================================
def transcrever_audio_groq(url_audio_whatsapp):
    if not GROQ_API_KEY:
        return ""
    
    temp_path = None
    try:
        headers_evo = {"apikey": os.getenv('EVOLUTION_API_KEY')}
        res = requests.get(url_audio_whatsapp, headers=headers_evo, timeout=25)
        if res.status_code != 200:
            res = requests.get(url_audio_whatsapp, timeout=25)
            
        if res.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
                temp_audio.write(res.content)
                temp_path = temp_audio.name

            headers_groq = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            url_whisper = "https://api.groq.com/openai/v1/audio/transcriptions"
            
            with open(temp_path, "rb") as audio_file:
                files = {
                    "file": (temp_path, audio_file, "audio/ogg"),
                    "model": (None, "whisper-large-v3")
                }
                response = requests.post(url_whisper, headers=headers_groq, files=files, timeout=30)
                
            if response.status_code == 200:
                return response.json().get("text", "")
    except Exception as e:
        print(f"❌ Erro ao transcrever áudio: {e}")
    finally:
        # Garante a eliminação do ficheiro temporário SEMPRE
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                print(f"⚠️ Aviso: Não foi possível remover o ficheiro temporário {temp_path}: {e}")
                
    return ""

# ==========================================
#   👁️ ANÁLISE DE IMAGEM & COMPROVANTES
# ==========================================
def analisar_imagem_groq(url_imagem, instrucao="Analise e extraia todas as informações desta imagem:"):
    if not GROQ_API_KEY:
        return ""
    try:
        headers_evo = {"apikey": os.getenv('EVOLUTION_API_KEY')}
        res = requests.get(url_imagem, headers=headers_evo, timeout=25)
        if res.status_code != 200:
            res = requests.get(url_imagem, timeout=25)
            
        if res.status_code == 200:
            image_base64 = base64.b64encode(res.content).decode('utf-8')
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            
            payload = {
                "model": GROQ_VISION_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instrucao},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }],
                "max_tokens": 500
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=25)
            data = resp.json()
            if resp.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"❌ Erro ao analisar imagem: {e}")
    return ""

# ==========================================
#   🛡️ CONTROLE DE DUPLICADOS E ALERTAS
# ==========================================
PROCESSADOS = {}
processados_lock = threading.Lock()

def notificar_erro_admin(erro_msg):
    if ADMIN_NUMBER:
        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{central_instance}"
        to_number = ADMIN_NUMBER if "@" in ADMIN_NUMBER else f"{ADMIN_NUMBER}@s.whatsapp.net"
        try:
            requests.post(url, headers=headers, json={"number": to_number, "text": f"⚠️ *[ALERTA NEGOBOT]*\n\n`{erro_msg}`"}, timeout=10)
        except Exception as e:
            print(f"Erro ao notificar admin: {e}")

# ==========================================
#   📄 EXTRAÇÃO DE CONTEÚDO (PDF E EXCEL)
# ==========================================
def extrair_texto_pdf_url(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=25)
        if response.status_code == 200:
            pdf_file = io.BytesIO(response.content)
            reader = PdfReader(pdf_file)
            texto_completo = ""
            for idx, page in enumerate(reader.pages, start=1):
                txt = page.extract_text()
                if txt:
                    texto_completo += f"\n--- PÁGINA {idx} ---\n" + txt
            return texto_completo
    except Exception as e:
        print(f"❌ Erro PDF: {e}")
    return ""

def extrair_texto_excel_url(excel_url):
    try:
        response = requests.get(excel_url, timeout=25)
        if response.status_code == 200:
            excel_file = io.BytesIO(response.content)
            todas_abas = pd.read_excel(excel_file, sheet_name=None)
            texto_completo = ""
            for nome_aba, df in todas_abas.items():
                texto_completo += f"\n--- ABA: {nome_aba} ---\n" + df.to_string(index=False) + "\n"
            return texto_completo
    except Exception as e:
        print(f"❌ Erro Excel: {e}")
    return ""

def criar_prompt_profissional_groq(pedido_utilizador):
    sys_instruction = "Converta o pedido num prompt detalhado em INGLÊS para marketing/publicidade moçambicana. Responda APENAS com o prompt em inglês."
    return chamar_groq_rest([{"parts": [{"text": pedido_utilizador}]}], system_instruction=sys_instruction, temperature=0.0) or pedido_utilizador

def gerar_url_imagem_pollinations(prompt_otimizado):
    return f"https://pollinations.ai/p/{urllib.parse.quote(prompt_otimizado)}?width=1024&height=1024&model=flux&seed=42"

# ==========================================
#   ⏱️ LÓGICA DE TIMEOUT AUTOMÁTICO
# ==========================================
def checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
    if conversa_dados and conversa_dados.get("status_atendimento") == "humano":
        ultima_interacao = conversa_dados.get("ultima_interacao")
        if ultima_interacao and conversa_dados.get("ultima_mensagem_por") == "cliente_final":
            if ultima_interacao.tzinfo is None:
                ultima_interacao = ultima_interacao.replace(tzinfo=timezone.utc)
            if (agora - ultima_interacao).total_seconds() / 60.0 >= TIMEOUT_HUMANO_MINUTOS:
                conversa_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                return True
    return False

def criar_e_configurar_instancia_automatica(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        requests.delete(f"{os.getenv('EVOLUTION_API_URL')}/instance/logout/{client_instance}", headers=headers, timeout=5)
        requests.delete(f"{os.getenv('EVOLUTION_API_URL')}/instance/delete/{client_instance}", headers=headers, timeout=5)
        time.sleep(2)
        
        url_create = f"{os.getenv('EVOLUTION_API_URL')}/instance/create"
        res = requests.post(url_create, headers=headers, json={"instanceName": client_instance, "qrcode": True, "integration": "WHATSAPP-BAILEYS"}, timeout=10)
        res.raise_for_status()
        
        webhook_target_url = os.getenv('WEBHOOK_URL')
        if webhook_target_url:
            requests.post(f"{os.getenv('EVOLUTION_API_URL')}/webhook/set/{client_instance}", headers=headers, json={"url": webhook_target_url, "enabled": True, "events": ["MESSAGES_UPSERT"]}, timeout=10)

        return True
    except Exception as e:
        notificar_erro_admin(f"Erro ao criar instância para {phone_number}: {e}")
        return False

def get_chat_history(phone_number):
    try:
        doc = db.collection('chats').document(phone_number).get()
        if doc.exists:
            return doc.to_dict().get('history', [])
    except Exception as e:
        print(f"Erro histórico: {e}")
    return []

def save_chat_history(phone_number, history):
    try:
        db.collection('chats').document(phone_number).set({"history": history}, merge=True)
    except Exception as e:
        print(f"Erro salvar histórico: {e}")

def send_whatsapp(to, text, instance_name=None):
    if not text or not str(text).strip():
        return False
    instance_name = instance_name or os.getenv('EVOLUTION_INSTANCE_NAME')
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    try:
        requests.post(f"{os.getenv('EVOLUTION_API_URL')}/chat/sendPresence/{instance_name}", headers=headers, json={"number": to, "presence": "composing"}, timeout=5)
        time.sleep(1)
        res = requests.post(f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{instance_name}", headers=headers, json={"number": to, "text": text}, timeout=10)
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"Erro enviar mensagem: {e}")
        return False

def gerar_e_enviar_qrcode_central(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        res = requests.get(f"{os.getenv('EVOLUTION_API_URL')}/instance/connect/{client_instance}", headers=headers, timeout=10)
        dados = res.json()
        if dados.get("instance", {}).get("state") == "open":
            send_whatsapp(phone_number, "✅ A sua instância já se encontra ativa!")
            return True
            
        base64_qr = dados.get("base64")
        if not base64_qr:
            return False
        if "," in base64_qr:
            base64_qr = base64_qr.split(",")[1]

        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        payload = {
            "number": phone_number,
            "caption": "🤖 *QR Code do seu Assistente Multilocatário!*\n\nEscaneie com o WhatsApp da empresa para ativar o bot de atendimento.",
            "media": base64_qr,
            "mediatype": "image",
            "fileName": "qrcode.png"
        }
        requests.post(f"{os.getenv('EVOLUTION_API_URL')}/message/sendMedia/{central_instance}", headers=headers, json=payload, timeout=15)
        return True
    except Exception as e:
        print(f"Erro QR Code: {e}")
        return False

# ==========================================
#   🎛 WEBHOOK GLOBAL UNIVERSAL MULTITENANT
# ==========================================
@app.route('/webhook-global', methods=['POST'])
@app.route('/webhook-cliente', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def universal_webhook():
    data = request.json
    if not data:
        return 'OK', 200
    threading.Thread(target=processar_webhook_background, args=(data,)).start()
    return 'OK', 200

def processar_webhook_background(data):
    try:
        event_name = data.get('event', '').lower()
        if event_name not in ["messages.upsert", "messages_upsert"] or "data" not in data:
            return

        msg_data = data['data']
        key = msg_data.get('key', {})
        msg_id = key.get('id')
        
        if msg_id:
            with processados_lock:
                agora_tempo = time.time()
                for k in [k for k, v in PROCESSADOS.items() if agora_tempo - v > 60]:
                    del PROCESSADOS[k]
                if msg_id in PROCESSADOS:
                    return
                PROCESSADOS[msg_id] = agora_tempo

        nome_instancia_atual = data.get('instance')
        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        if not nome_instancia_atual:
            return

        phone_number = key.get('remoteJid', '')
        if not phone_number or '@g.us' in phone_number or (NUMERO_ASSISTANTE and NUMERO_ASSISTANTE in phone_number):
            return

        message = msg_data.get('message', {})
        audio_message = message.get('audioMessage')
        document_message = message.get('documentMessage') or message.get('documentWithCaptionMessage', {}).get('message', {}).get('documentMessage')
        image_message = message.get('imageMessage') or message.get('extendedTextMessage', {}).get('contextInfo', {}).get('quotedMessage', {}).get('imageMessage')
        message_text = message.get('conversation') or message.get('extendedTextMessage', {}).get('text', '')

        if audio_message:
            url_audio = audio_message.get('url')
            if url_audio:
                send_whatsapp(phone_number, "🎙️ *A ouvir o seu áudio...*", instance_name=nome_instancia_atual)
                message_text = transcrever_audio_groq(url_audio)

        if image_message and not message_text.startswith('/criar-arte'):
            url_imagem = image_message.get('url')
            caption = image_message.get('caption', '')
            if url_imagem:
                send_whatsapp(phone_number, "👁️ *A analisar imagem/comprovativo...*", instance_name=nome_instancia_atual)
                analise_foto = analisar_imagem_groq(url_imagem, instrucao=caption or "Extraia os dados relevantes:")
                if analise_foto:
                    message_text = f"[ANÁLISE DA IMAGEM: {analise_foto}]\nTexto: {caption}"

        if not message_text and not document_message:
            return

        msg_clean = message_text.lower().strip()
        agora = datetime.now(timezone.utc)
        is_from_me = key.get('fromMe') is True or str(key.get('fromMe')).lower() == 'true'

        # =======================================================
        # 🏢 FLUXO A: INSTÂNCIA CENTRAL (ONBOARDING & VENDAS)
        # =======================================================
        if nome_instancia_atual == central_instance:
            chat_ref = db.collection('chats').document(phone_number)
            chat_doc = chat_ref.get()
            chat_dados = chat_doc.to_dict() if chat_doc.exists else {}

            if is_from_me:
                chat_ref.set({"ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
                return

            empresa_id = re.sub(r'\D', '', phone_number)
            empresa_doc_ref = db.collection('empresas').document(empresa_id)

            if not empresa_doc_ref.get().exists:
                empresa_doc_ref.set({
                    "empresa_id": empresa_id,
                    "phone_number": phone_number,
                    "data_registro": agora,
                    "status_plano": "demonstracao",
                    "servicos": "Ainda não definidos",
                    "precos": "Sob consulta",
                    "horario_funcionamento": "Segunda a Sábado, 08:00 - 18:00",
                    "diretrizes_corporativas": "Empresa recém-registada no Negobot Moz."
                }, merge=True)

            if msg_clean == "#qrcode":
                send_whatsapp(phone_number, "🔄 A gerar QR Code...", instance_name=central_instance)
                criar_e_configurar_instancia_automatica(phone_number)
                time.sleep(2)
                gerar_e_enviar_qrcode_central(phone_number)
                return

            if document_message:
                url_doc = document_message.get('url')
                file_name = document_message.get('fileName', '').lower()
                
                if file_name.endswith(('.xlsx', '.xls')):
                    send_whatsapp(phone_number, "📊 A processar tabela de preços e serviços da empresa...", instance_name=central_instance)
                    texto_excel = extrair_texto_excel_url(url_doc)
                    if texto_excel:
                        empresa_doc_ref.set({
                            "servicos_catalogo_excel": texto_excel,
                            "ultima_atualizacao": agora
                        }, merge=True)
                        send_whatsapp(phone_number, "✅ *Catálogo Excel atualizado com sucesso no Firestore!* Os seus clientes já poderão consultar.", instance_name=central_instance)
                    return

                elif file_name.endswith('.pdf') or not file_name:
                    send_whatsapp(phone_number, "📄 A ler documento de diretrizes/produtos (PDF)...", instance_name=central_instance)
                    texto_pdf = extrair_texto_pdf_url(url_doc)
                    if texto_pdf:
                        empresa_doc_ref.set({
                            "diretrizes_corporativas": texto_pdf,
                            "ultima_atualizacao": agora
                        }, merge=True)
                        send_whatsapp(phone_number, "✅ *Diretrizes e produtos atualizados com sucesso no Firestore!*", instance_name=central_instance)
                    return

            gatilhos_teste = ["teste", "testar", "quero o bot", "começar", "criar bot"]
            if any(g in msg_clean for g in gatilhos_teste):
                send_whatsapp(phone_number, "⏳ *A configurar o seu assistente dedicado (multilocatário)...* 🚀", instance_name=central_instance)
                if criar_e_configurar_instancia_automatica(phone_number):
                    empresa_doc_ref.set({
                        "status_plano": "demonstracao", 
                        "data_ativacao": agora, 
                        "data_expiracao": agora + timedelta(days=2)
                    }, merge=True)
                    time.sleep(3)
                    gerar_e_enviar_qrcode_central(phone_number)
                return

            status_atendimento = chat_dados.get("status_atendimento", "bot")
            if status_atendimento == "humano":
                if checar_timeout_atendimento_humano(chat_ref, chat_dados, agora):
                    status_atendimento = "bot"
                else:
                    if msg_clean in ["/bot", "/reset", "continuar", "bot", "bom dia", "boa tarde", "boa noite", "ola", "olá", "oy", "oi"]:
                        chat_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                        status_atendimento = "bot"
                    else:
                        chat_ref.set({"ultima_interacao": agora, "ultima_mensagem_por": "cliente_final"}, merge=True)
                        hist = chat_dados.get("history", [])
                        hist.append({"role": "user", "parts": [{"text": message_text}]})
                        save_chat_history(phone_number, hist[-10:])
                        return

            chat_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
            
            raw_history = get_chat_history(phone_number)[-10:]
            contents = []
            for msg in raw_history:
                role = "assistant" if msg.get('role') in ["assistant", "model", "atendente"] else "user"
                txt = msg.get('text') or " ".join([p.get('text', '') for p in msg.get('parts', []) if isinstance(p, dict)])
                if txt:
                    contents.append({"role": role, "parts": [{"text": txt}]})
            contents.append({"role": "user", "parts": [{"text": message_text}]})

            sys_instruction_central = """Você é o assistente comercial e de suporte oficial do Negobot Moz.
Ajude os empresários a configurar os seus catálogos, preços e serviços. Responda em Português de Moçambique com dinamismo e cortesia."""

            response_text = chamar_groq_rest(contents, system_instruction=sys_instruction_central, temperature=0.0)
            if response_text:
                contents.append({"role": "assistant", "parts": [{"text": response_text}]})
                save_chat_history(phone_number, [{"role": c["role"], "parts": c["parts"]} for c in contents[-10:]])
                send_whatsapp(phone_number, response_text, instance_name=central_instance)
                chat_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

        # =======================================================
        # 🤖 FLUXO B: ATENDIMENTO MULTILOCATÁRIO AO CLIENTE FINAL
        # =======================================================
        else:
            empresa_doc_ref = db.collection('empresas').document(nome_instancia_atual)
            empresa_doc = empresa_doc_ref.get()

            default_rules = "Ainda não foram cadastradas informações específicas para esta empresa."

            if not empresa_doc.exists:
                dados_empresa = {
                    "empresa_id": nome_instancia_atual,
                    "status_plano": "demonstracao",
                    "data_ativacao": agora,
                    "data_expiracao": agora + timedelta(days=2),
                    "diretrizes_corporativas": default_rules,
                    "servicos": "Informações indisponíveis",
                    "precos": "Informações indisponíveis"
                }
                empresa_doc_ref.set(dados_empresa, merge=True)
            else:
                dados_empresa = empresa_doc.to_dict()

            status_plano = dados_empresa.get("status_plano", "demonstracao")
            data_expiracao = dados_empresa.get("data_expiracao")
            if data_expiracao:
                if data_expiracao.tzinfo is None:
                    data_expiracao = data_expiracao.replace(tzinfo=timezone.utc)
                if status_plano == "demonstracao" and agora > data_expiracao:
                    send_whatsapp(phone_number, "⚠️ O período de teste do assistente desta empresa expirou.", instance_name=nome_instancia_atual)
                    return

            conversa_ref = empresa_doc_ref.collection('conversas').document(phone_number)
            historico_ref = conversa_ref.collection('historico')

            if is_from_me:
                conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
                historico_ref.add({"role": "atendente", "text": message_text, "timestamp": agora})
                return

            if msg_clean.startswith("/criar-arte"):
                pedido = message_text.replace("/criar-arte", "").strip()
                if not pedido:
                    send_whatsapp(phone_number, "✍️ Exemplo: `/criar-arte Banner promocional`", instance_name=nome_instancia_atual)
                    return
                send_whatsapp(phone_number, "🎨 A criar arte comercial...", instance_name=nome_instancia_atual)
                prompt_ingles = criar_prompt_profissional_groq(pedido)
                link_imagem = gerar_url_imagem_pollinations(prompt_ingles)
                
                payload = {"number": phone_number, "caption": f"✨ *Promoção!*\n🎯 _{pedido}_", "media": link_imagem, "mediatype": "image", "fileName": "arte.jpg"}
                requests.post(f"{os.getenv('EVOLUTION_API_URL')}/message/sendMedia/{nome_instancia_atual}", headers={"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}, json=payload, timeout=25)
                return

            if phone_number.split('@')[0] in nome_instancia_atual and (msg_clean.startswith("adicionar produto") or msg_clean.startswith("atualizar preço") or msg_clean.startswith("novo serviço")):
                empresa_doc_ref.set({
                    "atualizacoes_recentes_chat": firestore.ArrayUnion([{"texto": message_text, "data": agora}]),
                    "diretrizes_corporativas": f"{dados_empresa.get('diretrizes_corporativas', '')}\n- Nova atualização: {message_text}"
                }, merge=True)
                send_whatsapp(phone_number, "✅ *Catálogo atualizado com sucesso no Firestore (Multi-tenant)!*", instance_name=nome_instancia_atual)
                return

            conversa_doc = conversa_ref.get()
            conversa_dados = conversa_doc.to_dict() if conversa_doc.exists else {}
            status_atendimento = conversa_dados.get("status_atendimento", "bot")

            if status_atendimento == "humano":
                if checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
                    status_atendimento = "bot"
                else:
                    if msg_clean in ["/bot", "/reset", "continuar", "bot", "bom dia", "boa tarde", "boa noite", "ola", "olá", "oy", "oi"]:
                        conversa_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                        status_atendimento = "bot"
                    else:
                        conversa_ref.set({"ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                        historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                        return

            gatilhos_humano = ["falar com atendente", "suporte humano", "atendente", "humano", "#suporte"]
            if any(g in msg_clean for g in gatilhos_humano):
                conversa_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                send_whatsapp(phone_number, f"🔔 *Atendimento Transferido:* Encaminhado ao operador da empresa. Se não houver resposta em {TIMEOUT_HUMANO_MINUTOS} minutos, o assistente retomará.", instance_name=nome_instancia_atual)
                return

            # CARREGA DADOS DO FIRESTORE
            diretrizes = dados_empresa.get("diretrizes_corporativas", default_rules)
            servicos = dados_empresa.get("servicos", "Não especificado")
            precos = dados_empresa.get("precos", "Sob consulta")
            horario = dados_empresa.get("horario_funcionamento", "Horário não cadastrado")
            excel_catalogo = dados_empresa.get("servicos_catalogo_excel", "")

            docs_h = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
            lista_m = [d.to_dict() for d in docs_h]
            lista_m.reverse()

            contents = []
            for m in lista_m:
                role_g = "assistant" if m.get('role') in ["assistant", "model", "atendente"] else "user"
                contents.append({"role": role_g, "parts": [{"text": m.get('text', '')}]})
            contents.append({"role": "user", "parts": [{"text": message_text}]})

            # =====================================================================
            # 🛠️ SYSTEM PROMPT RIGOROSO ANTI-ALUCINAÇÃO (REGRAS SOLICITADAS)
            # =====================================================================
            sys_instruction = f"""Você é o assistente virtual de atendimento ao cliente desta empresa. Responda em Português de Moçambique com tom profissional, cortês e objetivo.

=== DADOS CARREGADOS DA BASE DE DADOS DO FIRESTORE (CONTEXTO OFICIAL) ===
DIRETRIZES E PRODUTOS:
{diretrizes}

SERVIÇOS OFERECIDOS:
{servicos}

TABELA DE PREÇOS:
{precos}

HORÁRIO DE FUNCIONAMENTO:
{horario}

CATÁLOGO ADICIONAL (EXCEL):
{excel_catalogo}
=====================================================================

REGRAS RÍGIDAS DE ATENDIMENTO (OBRIGATÓRIAS E INEGOCIÁVEIS):
1. Responda EXCLUSIVAMENTE com base nos dados fornecidos na base de dados/contexto do Firestore acima.
2. NUNCA invente, deduza ou use conhecimento geral sobre preços, horários, serviços, localização ou regras da empresa.
3. Se a informação pedida pelo cliente NÃO estiver na base de dados acima, você DEVE responder exatamente:
"Desculpe, não tenho essa informação no meu sistema no momento. Gostaria que eu te conectasse com um atendente humano?"
4. Sempre que a informação NÃO estiver na base de dados OU o cliente pedir expressamente um atendente humano, você DEVE obrigatoriamente incluir a tag [TRANSICAO_HUMANO] no final absoluto da resposta.
5. Em saudações simples (como 'Olá', 'Bom dia', 'Boa tarde', 'Boa noite'), responda de forma cortês apresentando a empresa, mas sem inventar dados não cadastrados e sem acionar a tag a menos que seja solicitada informação ausente."""

            # Chamada com temperature=0.0 garantindo resposta estritamente factual
            response_text = chamar_groq_rest(contents, system_instruction=sys_instruction, temperature=0.0)
            historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})

            if "[TRANSICAO_HUMANO]" in response_text:
                response_text_limpo = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
                conversa_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                
                texto_envio = response_text_limpo or "Desculpe, não tenho essa informação no meu sistema no momento. Gostaria que eu te conectasse com um atendente humano?"
                send_whatsapp(phone_number, texto_envio, instance_name=nome_instancia_atual)
                historico_ref.add({"role": "assistant", "text": texto_envio, "timestamp": agora})
                return

            if response_text:
                send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
                historico_ref.add({"role": "assistant", "text": response_text, "timestamp": agora})
                conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

    except Exception as e:
        notificar_erro_admin(f"Erro Webhook Multitenant (Instância: {data.get('instance')}): {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
