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
    return "O ecossistema Negobot 100% Automático está online! 🚀", 200

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
# ==========================================
def chamar_groq_rest(contents_payload, system_instruction="", temperature=0.1):
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
        "max_tokens": 600
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

    return "Desculpe, estamos a receber muitas mensagens ao mesmo tempo. Por favor, tente novamente dentro de alguns segundos!"

# ==========================================
#   🎙️ TRANSCRIÇÃO DE ÁUDIO VIA GROQ (WHISPER)
# ==========================================
def transcrever_audio_groq(url_audio_whatsapp):
    if not GROQ_API_KEY:
        return ""
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
                
            os.remove(temp_path)
            if response.status_code == 200:
                texto = response.json().get("text", "")
                print(f"🎙️ Áudio Transcrito: {texto}")
                return texto
    except Exception as e:
        print(f"❌ Erro ao transcrever áudio: {e}")
    return ""

# ==========================================
#   👁️ ANÁLISE DE IMAGEM & COMPROVANTES (GROQ VISION)
# ==========================================
def analisar_imagem_groq(url_imagem, instrucao="Analise e extraia todas as informações relevantes desta imagem ou comprovativo:"):
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
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": GROQ_VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instrucao},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            }
            
            resp = requests.post(url, headers=headers, json=payload, timeout=25)
            data = resp.json()
            if resp.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
                resultado = data["choices"][0]["message"]["content"].strip()
                print("👁️ Imagem Analisada com sucesso!")
                return resultado
            else:
                print(f"❌ Erro resposta Groq Vision: {data}")
    except Exception as e:
        print(f"❌ Erro ao analisar imagem no Groq Vision: {e}")
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
        payload = {
            "number": to_number,
            "text": f"⚠️ *[ALERTA CRÍTICO - NEGOBOT]*\n\nOcorreu uma falha no servidor:\n❌ `{erro_msg}`\n\n*Verifique os logs.*"
        }
        try:
            requests.post(url, headers=headers, json=payload, timeout=10)
        except Exception as e:
            print(f"Falha ao enviar notificação de erro ao admin: {e}")

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
                conteudo_pagina = page.extract_text()
                if conteudo_pagina:
                    texto_completo += f"\n--- PÁGINA {idx} ---\n" + conteudo_pagina
            return texto_completo
    except Exception as e:
        print(f"❌ Erro ao ler PDF da URL {pdf_url}: {e}")
    return ""

def extrair_texto_excel_url(excel_url):
    try:
        response = requests.get(excel_url, timeout=25)
        if response.status_code == 200:
            excel_file = io.BytesIO(response.content)
            todas_abas = pd.read_excel(excel_file, sheet_name=None)
            texto_completo = ""
            for nome_aba, df in todas_abas.items():
                texto_completo += f"\n--- ABA EXCEL: {nome_aba} ---\n"
                texto_completo += df.to_string(index=False) + "\n"
            return texto_completo
    except Exception as e:
        print(f"❌ Erro ao ler Excel da URL {excel_url}: {e}")
    return ""

def criar_prompt_profissional_groq(pedido_utilizador):
    try:
        sys_instruction = (
            "Você é um especialista em Engenharia de Prompts para geração de imagens publicitárias. "
            "Converta o pedido do utilizador num prompt altamente detalhado em INGLÊS. "
            "Adicione detalhes de qualidade visual e contexto corporativo moçambicano como: "
            "'professional marketing banner, microfinance Mozambique context, bright clean lighting, photorealistic, 8k'. "
            "Responda APENAS com o prompt em inglês, sem saudações."
        )
        contents = [{"parts": [{"text": pedido_utilizador}]}]
        resultado = chamar_groq_rest(contents, system_instruction=sys_instruction, temperature=0.7)
        return resultado if resultado else pedido_utilizador
    except Exception as e:
        print(f"❌ Erro ao otimizar prompt no Groq: {e}")
        return pedido_utilizador

def gerar_url_imagem_pollinations(prompt_otimizado):
    prompt_encoded = urllib.parse.quote(prompt_otimizado)
    return f"https://pollinations.ai/p/{prompt_encoded}?width=1024&height=1024&model=flux&seed=42"

# ==========================================
#   ⏱️ LÓGICA DE TIMEOUT AUTOMÁTICO
# ==========================================
def checar_timeout_atendimento_humano(conversa_ref, conversa_dados, agora):
    if conversa_dados and conversa_dados.get("status_atendimento") == "humano":
        ultima_interacao = conversa_dados.get("ultima_interacao")
        ultima_msg_por = conversa_dados.get("ultima_mensagem_por")
        
        if ultima_msg_por == "cliente_final" and ultima_interacao:
            if ultima_interacao.tzinfo is None:
                ultima_interacao = ultima_interacao.replace(tzinfo=timezone.utc)
            
            minutos_decorridos = (agora - ultima_interacao).total_seconds() / 60.0
            if minutos_decorridos >= TIMEOUT_HUMANO_MINUTOS:
                conversa_ref.set({
                    "status_atendimento": "bot",
                    "ultima_interacao": agora
                }, merge=True)
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
        payload_create = {"instanceName": client_instance, "qrcode": True, "integration": "WHATSAPP-BAILEYS"}
        res_create = requests.post(url_create, headers=headers, json=payload_create, timeout=10)
        res_create.raise_for_status()
        
        # Configuração automática do Webhook para a nova instância
        webhook_target_url = os.getenv('WEBHOOK_URL')
        if webhook_target_url:
            url_webhook = f"{os.getenv('EVOLUTION_API_URL')}/webhook/set/{client_instance}"
            payload_webhook = {
                "url": webhook_target_url,
                "enabled": True,
                "events": ["MESSAGES_UPSERT"]
            }
            requests.post(url_webhook, headers=headers, json=payload_webhook, timeout=10)

        return True
    except Exception as e:
        erro_msg = f"Erro ao automatizar criação/webhook para {phone_number}: {e}"
        notificar_erro_admin(erro_msg)
        return False

def get_chat_history(phone_number):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('history', [])
    except Exception as e:
        print(f"Erro ao obter histórico: {e}")
    return []

def save_chat_history(phone_number, history):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc_ref.set({"history": history}, merge=True)
    except Exception as e:
        print(f"Erro ao salvar histórico: {e}")

def send_whatsapp(to, text, instance_name=None):
    if not text or not str(text).strip():
        return False

    if not instance_name:
        instance_name = os.getenv('EVOLUTION_INSTANCE_NAME')
        
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    
    try:
        url_presence = f"{os.getenv('EVOLUTION_API_URL')}/chat/sendPresence/{instance_name}"
        requests.post(url_presence, headers=headers, json={"number": to, "presence": "composing"}, timeout=5)
        time.sleep(1)
        
        url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{instance_name}"
        res = requests.post(url, headers=headers, json={"number": to, "text": text}, timeout=10)
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"ERRO ao enviar mensagem: {e}")
        return False

def gerar_e_enviar_qrcode_central(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        url_connect = f"{os.getenv('EVOLUTION_API_URL')}/instance/connect/{client_instance}"
        response_connect = requests.get(url_connect, headers=headers, timeout=10)
        response_connect.raise_for_status()
        
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
            "1️⃣ Abra o WhatsApp que vai atender os seus clientes.\n"
            "2️⃣ Vá a *Aparelhos Conectados* -> *Conectar um aparelho*.\n"
            "3️⃣ Aponte a câmara e escaneie *imediatamente* este QR Code.\n\n"
            "Se expirar, digite *#qrcode* aqui para gerar um novo!"
        )
        
        payload_media = {
            "number": phone_number,
            "caption": caption_text,
            "media": base64_qrcode,
            "mediatype": "image",
            "fileName": "qrcode.png"
        }
        requests.post(url_send_media, headers=headers, json=payload_media, timeout=15)
        return True
    except Exception as e:
        print(f"Erro ao gerar QR Code: {e}")
        return False

# ==========================================
#   🎛 WEBHOOK GLOBAL UNIVERSAL
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
                send_whatsapp(phone_number, "👁️ *A analisar o documento/imagem...*", instance_name=nome_instancia_atual)
                instrucao = caption if caption else "Analise e extraia todas as informações deste comprovativo ou imagem."
                analise_foto = analisar_imagem_groq(url_imagem, instrucao=instrucao)
                if analise_foto:
                    message_text = f"[ANÁLISE DA IMAGEM/DOCUMENTO: {analise_foto}]\nTexto do cliente: {caption}"

        if not message_text and not document_message:
            return

        msg_clean = message_text.lower().strip()
        agora = datetime.now(timezone.utc)
        is_from_me = key.get('fromMe') is True or str(key.get('fromMe')).lower() == 'true'

        # =======================================================
        # 🏢 FLUXO A: INSTÂNCIA CENTRAL (SUPORTE E VENDAS NEGOBOT)
        # =======================================================
        if nome_instancia_atual == central_instance:
            chat_ref = db.collection('chats').document(phone_number)
            chat_doc = chat_ref.get()
            chat_dados = chat_doc.to_dict() if chat_doc.exists else {}

            if is_from_me:
                chat_ref.set({"ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
                return

            cliente_doc_ref = db.collection('clientes').document(phone_number)
            if not cliente_doc_ref.get().exists:
                cliente_doc_ref.set({
                    "phone_number": phone_number,
                    "data_registro": agora,
                    "status": "prospect"
                }, merge=True)

            if msg_clean == "#qrcode":
                send_whatsapp(phone_number, "🔄 A gerar QR Code...", instance_name=central_instance)
                criar_e_configurar_instancia_automatica(phone_number)
                time.sleep(2)
                gerar_e_enviar_qrcode_central(phone_number)
                return

            gatilhos_teste = ["teste", "testar", "quero o bot", "começar", "criar bot"]
            if any(g in msg_clean for g in gatilhos_teste):
                cliente_data_cur = cliente_doc_ref.get().to_dict() or {}
                status_atual = cliente_data_cur.get('status', 'prospect')
                
                if status_atual == 'prospect':
                    send_whatsapp(phone_number, "⏳ *A preparar o seu teste de 2 dias...* 🚀", instance_name=central_instance)
                    if criar_e_configurar_instancia_automatica(phone_number):
                        cliente_doc_ref.set({
                            "phone_number": phone_number,
                            "data_registro": agora,
                            "trial_start": agora,
                            "status": "trial"
                        }, merge=True)
                        tenant_id = re.sub(r'\D', '', phone_number)
                        db.collection('clientes_bot').document(tenant_id).set({
                            "status_plano": "demonstracao", "data_ativacao": agora, "data_expiracao": agora + timedelta(days=2)
                        })
                        time.sleep(3)
                        gerar_e_enviar_qrcode_central(phone_number)
                    return

            # --- ANTIGRIPAGEM / REATIVAÇÃO AUTOMÁTICA (ANTI-MORTE DE FLUXO) ---
            status_atendimento = chat_dados.get("status_atendimento", "bot")
            if status_atendimento == "humano":
                if checar_timeout_atendimento_humano(chat_ref, chat_dados, agora):
                    status_atendimento = "bot"
                else:
                    # Se mandou bom dia, ola, oy, etc., força a reativação imediata para a IA
                    if msg_clean in ["/bot", "/reset", "continuar", "bot", "bom dia", "boa tarde", "boa noite", "ola", "olá", "oy", "oi"]:
                        chat_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                        status_atendimento = "bot"
                    else:
                        chat_ref.set({"ultima_interacao": agora, "ultima_mensagem_por": "cliente_final"}, merge=True)
                        hist = chat_dados.get("history", [])
                        hist.append({"role": "user", "parts": [{"text": message_text}]})
                        save_chat_history(phone_number, hist[-10:])
                        return

            gatilhos_humano = ["falar com atendente", "suporte humano", "atendente", "humano", "#suporte"]
            if any(g in msg_clean for g in gatilhos_humano):
                chat_ref.set({
                    "status_atendimento": "humano",
                    "ultima_mensagem_por": "cliente_final",
                    "ultima_interacao": agora
                }, merge=True)
                send_whatsapp(
                    phone_number,
                    f"🔔 *Atendimento Transferido:* Encaminhamos para a nossa equipa. Se não houver resposta em {TIMEOUT_HUMANO_MINUTOS} minutos, o assistente responderá automaticamente.",
                    instance_name=central_instance
                )
                return

            # RESPOSTA IA CENTRAL (SEMPRE ATIVA PARA NOVAS MENSAGENS)
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
Responda sempre com cortesia, clareza e dinamismo em Português de Moçambique.
ATENÇÃO: Nunca ignore novas saudações (como 'Bom dia', 'Boa noite', 'Oy'). Retome a conversa de forma natural, prestativa e ativa, independentemente de despedidas anteriores."""

            response_text = chamar_groq_rest(contents, system_instruction=sys_instruction_central, temperature=0.3)
            if response_text:
                contents.append({"role": "assistant", "parts": [{"text": response_text}]})
                save_chat_history(phone_number, [{"role": c["role"], "parts": c["parts"]} for c in contents[-10:]])
                send_whatsapp(phone_number, response_text, instance_name=central_instance)
                chat_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

        # =======================================================
        # 🤖 FLUXO B: INSTÂNCIA INDIVIDUAL DO CLIENTE (FINAL USER)
        # =======================================================
        else:
            client_doc_ref = db.collection('clientes_bot').document(nome_instancia_atual)
            conversa_ref = client_doc_ref.collection('conversas').document(phone_number)
            historico_ref = conversa_ref.collection('historico')

            if is_from_me:
                conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
                historico_ref.add({"role": "atendente", "text": message_text, "timestamp": agora})
                return

            client_doc = client_doc_ref.get()
            default_rules = "És o assistente virtual oficial de atendimento. Responda de forma profissional e objetiva."

            if not client_doc.exists:
                dados_cliente = {"status_plano": "demonstracao", "data_ativacao": agora, "data_expiracao": agora + timedelta(days=2), "diretrizes_corporativas": default_rules}
                client_doc_ref.set(dados_cliente)
            else:
                dados_cliente = client_doc.to_dict()

            status_plano = dados_cliente.get("status_plano", "demonstracao")
            data_expiracao = dados_cliente.get("data_expiracao")
            if data_expiracao and data_expiracao.tzinfo is None:
                data_expiracao = data_expiracao.replace(tzinfo=timezone.utc)

            if status_plano == "demonstracao" and agora > data_expiracao:
                send_whatsapp(phone_number, "⚠️ O período de teste deste assistente expirou.", instance_name=nome_instancia_atual)
                return

            if msg_clean.startswith("/criar-arte"):
                pedido = message_text.replace("/criar-arte", "").strip()
                if not pedido:
                    send_whatsapp(phone_number, "✍️ Exemplo: `/criar-arte Banner de oferta de crédito`", instance_name=nome_instancia_atual)
                    return
                send_whatsapp(phone_number, "🎨 A criar a sua imagem...", instance_name=nome_instancia_atual)
                prompt_ingles = criar_prompt_profissional_groq(pedido)
                link_imagem = gerar_url_imagem_pollinations(prompt_ingles)
                
                payload = {"number": phone_number, "caption": f"✨ *Arte Gerada!*\n🎯 _{pedido}_", "media": link_imagem, "mediatype": "image", "fileName": "arte.jpg"}
                requests.post(f"{os.getenv('EVOLUTION_API_URL')}/message/sendMedia/{nome_instancia_atual}", headers={"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}, json=payload, timeout=25)
                return

            if document_message and phone_number.split('@')[0] in nome_instancia_atual:
                url_doc = document_message.get('url')
                file_name = document_message.get('fileName', '').lower()

                if file_name.endswith(('.xlsx', '.xls')):
                    send_whatsapp(phone_number, "📊 A processar documento Excel...", instance_name=nome_instancia_atual)
                    texto_excel = extrair_texto_excel_url(url_doc)
                    if texto_excel:
                        client_doc_ref.set({"diretrizes_corporativas": f"{dados_cliente.get('diretrizes_corporativas', '')}\n\n=== EXCEL ===\n{texto_excel}"}, merge=True)
                        send_whatsapp(phone_number, "✅ *Excel Carregado!* Tabela assimilada com sucesso.", instance_name=nome_instancia_atual)
                    return

                elif file_name.endswith('.pdf') or not file_name:
                    send_whatsapp(phone_number, "📄 A ler arquivo PDF...", instance_name=nome_instancia_atual)
                    texto_pdf = extrair_texto_pdf_url(url_doc)
                    if texto_pdf:
                        client_doc_ref.set({"diretrizes_corporativas": f"{dados_cliente.get('diretrizes_corporativas', '')}\n\n=== PDF ===\n{texto_pdf}"}, merge=True)
                        send_whatsapp(phone_number, "✅ *PDF Carregado!* Conteúdo incorporado às diretrizes.", instance_name=nome_instancia_atual)
                    return

            # --- ANTIGRIPAGEM / REATIVAÇÃO AUTOMÁTICA (CLIENTE) ---
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
                conversa_ref.set({
                    "status_atendimento": "humano",
                    "ultima_mensagem_por": "cliente_final",
                    "ultima_interacao": agora
                }, merge=True)
                historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                send_whatsapp(
                    phone_number, 
                    f"🔔 *Atendimento Transferido:* A mensagem foi enviada para o nosso operador. Se não houver resposta em {TIMEOUT_HUMANO_MINUTOS} minutos, o assistente retomará o atendimento.", 
                    instance_name=nome_instancia_atual
                )
                return

            # RESPOSTA IA CLIENTE (SEMPRE ATIVA)
            docs_h = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
            lista_m = [d.to_dict() for d in docs_h]
            lista_m.reverse()

            contents = []
            for m in lista_m:
                role_g = "assistant" if m.get('role') in ["assistant", "model", "atendente"] else "user"
                contents.append({"role": role_g, "parts": [{"text": m.get('text', '')}]})
            
            contents.append({"role": "user", "parts": [{"text": message_text}]})

            diretrizes = dados_cliente.get("diretrizes_corporativas", default_rules)
            sys_instruction = f"""Você é um assistente comercial atencioso.
Português de Moçambique, tom profissional e conciso.

DIRETRIZES DA EMPRESA:
{diretrizes}

REGRA DE REATIVAÇÃO E FLUXO:
- Nunca ignore novas saudações (como 'Bom dia', 'Boa noite', 'Oy'). Retome a conversa de forma ativa.
- NUNCA use a tag [TRANSICAO_HUMANO] em saudações simples.
- Apenas inclua a tag [TRANSICAO_HUMANO] se o cliente exigir expressamente um humano e você não tiver a resposta."""

            response_text = chamar_groq_rest(contents, system_instruction=sys_instruction, temperature=0.1)
            historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})

            e_saudacao = any(s in msg_clean for s in ["bom dia", "boa tarde", "boa noite", "olá", "ola", "oi", "oy"])
            
            if "[TRANSICAO_HUMANO]" in response_text and not e_saudacao:
                response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
                conversa_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                
                if response_text:
                    send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
                else:
                    send_whatsapp(phone_number, f"🔔 *Atendimento Transferido:* A sua mensagem foi encaminhada para a equipa humana. Aguarde por favor.", instance_name=nome_instancia_atual)
                
                historico_ref.add({"role": "assistant", "text": response_text, "timestamp": agora})
                return

            if response_text:
                response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
                send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
                historico_ref.add({"role": "assistant", "text": response_text, "timestamp": agora})
                conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

    except Exception as e:
        erro_completo = f"Erro Webhook (Instância: {data.get('instance')}): {e}"
        print(f"❌ {erro_completo}")
        notificar_erro_admin(erro_completo)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
