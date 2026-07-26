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

# Document & Spreadsheet Processing (PDF and Excel)
from pypdf import PdfReader
import pandas as pd

# Firebase Admin
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Negobot 100% Automático (Groq Engine) está online! 🚀", 200

# ==========================================
#   📦 FIREBASE SECURE INITIALIZATION
# ==========================================
firebase_config_env = os.getenv('FIREBASE_CONFIG')
if firebase_config_env:
    try:
        firebase_config = json.loads(firebase_config_env)
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        print("📦 [SISTEMA] Firebase inicializado com credenciais da ENV.")
    except Exception as e:
        print(f"⚠️ [SISTEMA] Falha ao carregar FIREBASE_CONFIG da ENV: {e}. Tentando inicialização padrão...")
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
#   GROQ API CONFIGURATIONS
# ==========================================
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'qwen-2.5-32b')

NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')
ADMIN_NUMBER = os.getenv('ADMIN_NUMBER')

# ==========================================
#   🌐 DIRECT REST CALL TO GROQ API (LLAMA 3.3)
# ==========================================
def chamar_groq_rest(contents_payload, system_instruction="", temperature=0.1):
    """
    Realiza chamadas de texto à API da Groq com sistema de retry automático
    em caso de limite de requisições (HTTP 429).
    """
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"].strip()
            elif response.status_code == 429:
                print(f"⚠️ [GROQ] Rate limit atingido (429). Tentativa {attempt + 1} de {max_retries}. A aguardar 2s...")
                time.sleep(2)
                continue
            else:
                print(f"❌ Erro na API do Groq (Status {response.status_code}): {response.text}")
                break
        except Exception as e:
            print(f"❌ Exceção ao chamar Groq API: {e}")
            time.sleep(1)

    return "Desculpe, estamos a receber muitas mensagens ao mesmo tempo. Por favor, tente novamente dentro de alguns segundos!"

# ==========================================
#   🎙️ AUDIO TRANSCRIPTION VIA GROQ (WHISPER)
# ==========================================
def transcrever_audio_groq(url_audio_whatsapp):
    """Descarrega áudios do WhatsApp e converte em texto via Whisper no Groq"""
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
#   👁️ IMAGE & DOCUMENT ANALYSIS (GROQ VISION)
# ==========================================
def analisar_imagem_groq(url_imagem, instrucao="Analise e extraia todas as informações relevantes desta imagem ou comprovativo:"):
    """Baixa a imagem enviada no WhatsApp e analisa via modelo Vision da Groq"""
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
#   🛡️ DUPLICATE CONTROL
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
            "text": f"⚠️ *[ALERTA CRÍTICO - NEGOBOT]*\n\nOcorreu uma falha no servidor:\n❌ `{erro_msg}`\n\n*Verifique a consola do Render imediatamente.*"
        }
        try:
            requests.post(url, headers=headers, json=payload, timeout=10)
        except Exception as e:
            print(f"Falha ao enviar notificação de erro ao admin: {e}")

# ==========================================
#   📄 EXTRACTION MODULES (PDF, EXCEL & ART)
# ==========================================
def extrair_texto_pdf_url(pdf_url, max_caracteres=10000):
    """Extrai texto de um PDF limitando o tamanho total para proteger o contexto da IA."""
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
                if len(texto_completo) >= max_caracteres:
                    texto_completo = texto_completo[:max_caracteres] + "\n\n[...Texto do PDF truncado para otimizar tamanho...]"
                    break
            return texto_completo
    except Exception as e:
        print(f"❌ Erro ao ler PDF da URL {pdf_url}: {e}")
    return ""

def extrair_texto_excel_url(excel_url, max_linhas_por_aba=100, max_caracteres=10000):
    """Extrai dados do Excel limitando linhas por aba e total de carateres."""
    try:
        response = requests.get(excel_url, timeout=25)
        if response.status_code == 200:
            excel_file = io.BytesIO(response.content)
            todas_abas = pd.read_excel(excel_file, sheet_name=None)
            texto_completo = ""
            for nome_aba, df in todas_abas.items():
                texto_completo += f"\n--- ABA EXCEL: {nome_aba} ---\n"
                df_resumido = df.head(max_linhas_por_aba)
                texto_completo += df_resumido.to_string(index=False) + "\n"
                if len(texto_completo) >= max_caracteres:
                    texto_completo = texto_completo[:max_caracteres] + "\n\n[...Dados do Excel truncados para otimizar tamanho...]"
                    break
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
    """Gera URL com seed aleatório para garantir imagens variadas."""
    prompt_encoded = urllib.parse.quote(prompt_otimizado)
    seed_aleatorio = random.randint(1, 999999)
    return f"https://pollinations.ai/p/{prompt_encoded}?width=1024&height=1024&model=flux&seed={seed_aleatorio}"

# ==========================================
#   ⏱️ VERIFICAÇÃO AUTOMÁTICA DE ESPERA HUMANA
# ==========================================
def verificar_espera_humano_isolado(instancia_cliente, numero_remetente):
    time.sleep(180)  # Aguarda 3 minutos exatos
    try:
        conversa_ref = db.collection('clientes_bot').document(instancia_cliente).collection('conversas').document(numero_remetente)
        doc = conversa_ref.get()
        if doc.exists:
            dados = doc.to_dict()
            if dados.get("status_atendimento") == "humano" and dados.get("ultima_mensagem_por") == "cliente_final":
                conversa_ref.set({"status_atendimento": "bot", "ultima_interacao": datetime.now(timezone.utc)}, merge=True)
                
                msg_aviso = (
                    "🕒 *AVISO DE ATENDIMENTO* ⚠️\n\n"
                    "Todos os nossos assistentes humanos estão ocupados no momento. "
                    "Para que não fique sem resposta, o nosso assistente virtual foi reativado automaticamente para continuar a ajudá-lo!\n\n"
                    "Como posso continuar a ajudar?"
                )
                send_whatsapp(numero_remetente, msg_aviso, instance_name=instancia_cliente)
    except Exception as e:
        print(f"❌ Falha na verificação de tempo de espera: {e}")

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
        return True
    except Exception as e:
        erro_msg = f"Erro ao automatizar criação para {phone_number}: {e}"
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

def listar_grupos_instancia(instance_name):
    url = f"{os.getenv('EVOLUTION_API_URL')}/group/fetchAllGroups/{instance_name}"
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY')}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
            
        grupos_brutos = response.json()
        lista_grupos = []
        for idx, g in enumerate(grupos_brutos, start=1):
            lista_grupos.append({
                "indice": idx, "id": g.get("id", ""), "nome": g.get("subject", "Grupo sem nome"),
                "qtd": len(g.get("participants", [])), "dados_brutos": g
            })
        return lista_grupos
    except Exception as e:
        print(f"Erro ao listar grupos: {e}")
        return []

def extrair_participantes_de_grupos_especificos(grupos_selecionados):
    telefones_unicos = set()
    for g in grupos_selecionados:
        for p in g.get("dados_brutos", {}).get("participants", []):
            numero_limpo = re.sub(r'\D', '', p.get("id", "").split("@")[0])
            if len(numero_limpo) >= 9:
                telefones_unicos.add(numero_limpo)
    return list(telefones_unicos)

def executar_campanha_duas_etapas(instance_name, telefones, mensagem_saudacao):
    contador = 0
    for phone in telefones:
        if send_whatsapp(phone, mensagem_saudacao, instance_name=instance_name):
            contador += 1
            db.collection("clientes_bot").document(instance_name).collection("campanha_leads").document(phone).set({
                "status": "saudacao_enviada", "timestamp": firestore.SERVER_TIMESTAMP
            })
        time.sleep(random.randint(25, 50))
        if contador > 0 and contador % 40 == 0:
            time.sleep(900)
    send_whatsapp(instance_name, f"✅ *Campanha Concluída!* {contador} mensagens enviadas.", instance_name=instance_name)

def enviar_lembretes_em_massa(periodo="dia"):
    try:
        clientes_ref = db.collection('clientes').where('status', '==', 'trial').stream()
        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        saudacao = "Bom dia" if periodo == "manhã" else "Boa tarde"
        mensagem_lembrete = (
            f"👋 *{saudacao}! Passando com um aviso importante sobre o seu Negobot Moz.* 🤖\n\n"
            "O seu teste gratuito de 2 dias está ativo. "
            "**Faça o pagamento da subscrição para não perder o acesso!** ⚠️\n\n"
            "💵 *M-Pesa:* 855000929 (Abel Francisco)\n"
            "📄 Envie o seu catálogo em PDF ou Excel para personalizar o seu robô!"
        )
        for doc in clientes_ref:
            phone = doc.to_dict().get('phone_number')
            if phone:
                send_whatsapp(phone, mensagem_lembrete, instance_name=central_instance)
                time.sleep(1.5)
    except Exception as e:
        notificar_erro_admin(f"Erro lembretes: {e}")

@app.route('/cron/lembretes', methods=['GET'])
def disparar_lembretes_via_url():
    periodo = request.args.get('periodo', 'manhã')
    threading.Thread(target=enviar_lembretes_em_massa, args=(periodo,)).start()
    return f"Lembretes ({periodo}) iniciados!", 200

# ==========================================
#   🎛 MAIN UNIVERSAL WEBHOOK
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
                instrucao = caption if caption else "Analise e extraia todas as informações, valores, datas e dados deste comprovativo ou imagem."
                analise_foto = analisar_imagem_groq(url_imagem, instrucao=instrucao)
                if analise_foto:
                    message_text = f"[O CLIENTE ENVIOU UMA IMAGEM/COMPROVATIVO. ANÁLISE DA IMAGEM: {analise_foto}]\nTexto do cliente: {caption}"

        if not message_text and not document_message:
            return

        msg_clean = message_text.lower().strip()
        agora = datetime.now(timezone.utc)
        is_from_me = key.get('fromMe') is True or str(key.get('fromMe')).lower() == 'true'

        # =======================================================
        # 👑 TRATAMENTO DE MENSAGENS ENVIADAS PELO PRÓPRIO DONO (FROM ME)
        # =======================================================
        if is_from_me:
            # Verifica se existem sessões de seleção de grupos ou disparos pendentes
            doc_map = db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").get()
            doc_temp = db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").get()
            
            # Identifica se a mensagem enviada por si é um comando operacional do robô
            eh_comando_proprio = (
                msg_clean.startswith('/') or 
                msg_clean.startswith('#') or 
                (msg_clean == "sim" and doc_temp.exists) or 
                (doc_map.exists and re.match(r'^[\d\s,]+$', msg_clean)) or
                document_message is not None
            )

            # Se NÃO for um comando operacional, regista a conversa de atendimento humano e encerra
            if not eh_comando_proprio:
                if nome_instancia_atual != central_instance:
                    conversa_ref = db.collection('clientes_bot').document(nome_instancia_atual).collection('conversas').document(phone_number)
                    conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
                    conversa_ref.collection('historico').add({"role": "atendente", "text": message_text, "timestamp": agora})
                return

        # =======================================================
        # 🏢 FLOW A: CENTRAL SALES INSTANCE
        # =======================================================
        if nome_instancia_atual == central_instance:
            if msg_clean.startswith('#status'):
                remetente_puro = phone_number.split('@')[0]
                if ADMIN_NUMBER and remetente_puro in ADMIN_NUMBER:
                    partes = message_text.split()
                    if len(partes) > 1:
                        jid_pesquisa = partes[1].strip() if "@" in partes[1] else f"{partes[1].strip()}@s.whatsapp.net"
                        doc_c = db.collection('clientes').document(jid_pesquisa).get()
                        if doc_c.exists:
                            c_dados = doc_c.to_dict()
                            resposta_status = f"📊 *NEGOBOT MOZ*\n• Cliente: {partes[1]}\n• Estado: {c_dados.get('status', 'N/A').upper()}\n• Pago: {'Sim ✅' if c_dados.get('pago') else 'Não ❌'}"
                        else:
                            resposta_status = f"❌ Número `{partes[1]}` não encontrado."
                    else:
                        resposta_status = "💡 Uso: `#status 25884xxxxxxx`"
                else:
                    resposta_status = "⛔ Restrito ao admin."
                send_whatsapp(phone_number, resposta_status, instance_name=central_instance)
                return

            if "recebeu" in msg_clean or "confirmado" in msg_clean or "transacao" in msg_clean:
                db.collection('clientes').document(phone_number).update({"status": "active", "pago": True, "data_ativacao": agora})
                db.collection('clientes_bot').document(phone_number.split('@')[0]).set({"status_plano": "active", "data_ativacao": agora}, merge=True)
                criar_e_configurar_instancia_automatica(phone_number)
                time.sleep(2)
                send_whatsapp(phone_number, "🎉 *Pagamento Confirmado!* Negobot ativado.", instance_name=central_instance)
                gerar_e_enviar_qrcode_central(phone_number)
                return
            
            gatilhos_teste = ["teste", "testar", "quero o bot", "começar", "criar bot"]
            if any(g in msg_clean for g in gatilhos_teste):
                cliente_ref = db.collection('clientes').document(phone_number)
                doc = cliente_ref.get()
                if not doc.exists or doc.to_dict().get('status') == 'prospect':
                    send_whatsapp(phone_number, "⏳ *A preparar o seu teste de 2 dias...* 🚀", instance_name=central_instance)
                    if criar_e_configurar_instancia_automatica(phone_number):
                        cliente_ref.set({"phone_number": phone_number, "data_registro": agora, "trial_start": agora, "status": "trial"})
                        tenant_id = re.sub(r'\D', '', phone_number)
                        db.collection('clientes_bot').document(tenant_id).set({
                            "status_plano": "demonstracao", "data_ativacao": agora, "data_expiracao": agora + timedelta(days=2)
                        })
                        time.sleep(3)
                        gerar_e_enviar_qrcode_central(phone_number)
                else:
                    status_atual = doc.to_dict().get('status', 'trial')
                    if status_atual == 'bloqueado':
                        send_whatsapp(phone_number, "⚠️ Teste expirado. Pague via M-Pesa (855000929) para reativar.", instance_name=central_instance)
                    else:
                        send_whatsapp(phone_number, "✅ O seu bot está ativo! Digite *#qrcode* se precisar de novo QR Code.", instance_name=central_instance)
                return

            if msg_clean == "#qrcode":
                send_whatsapp(phone_number, "🔄 A gerar QR Code...", instance_name=central_instance)
                criar_e_configurar_instancia_automatica(phone_number)
                time.sleep(2)
                gerar_e_enviar_qrcode_central(phone_number)
                return

            raw_history = get_chat_history(phone_number)[-10:]
            contents = []
            for msg in raw_history:
                role = "assistant" if msg.get('role') in ["assistant", "model", "atendente"] else "user"
                txt = msg.get('text') or " ".join([p.get('text', '') for p in msg.get('parts', []) if isinstance(p, dict)])
                if txt:
                    contents.append({"role": role, "parts": [{"text": txt}]})
            contents.append({"role": "user", "parts": [{"text": message_text}]})

            sys_instruction_central = """Você é o assistente comercial oficial do Negobot Moz. Sanar dúvidas e instruir o cliente a digitar a palavra-chave 'TESTAR' para receber o QR Code. 
Norma: Português padrão de Moçambique, tom sério.
Planos: Inicial (500 MT) e Avançado (1000 MT). M-Pesa: 855000929 (Abel Francisco)."""

            response_text = chamar_groq_rest(contents, system_instruction=sys_instruction_central, temperature=0.3)
            if response_text:
                contents.append({"role": "assistant", "parts": [{"text": response_text}]})
                save_chat_history(phone_number, [{"role": c["role"], "parts": c["parts"]} for c in contents[-10:]])
                send_whatsapp(phone_number, response_text, instance_name=central_instance)

        # =======================================================
        # 🤖 FLOW B: CLIENT BOT INSTANCE (FINAL BOT USER)
        # =======================================================
        else:
            client_doc_ref = db.collection('clientes_bot').document(nome_instancia_atual)
            conversa_ref = client_doc_ref.collection('conversas').document(phone_number)
            historico_ref = conversa_ref.collection('historico')

            client_doc = client_doc_ref.get()
            default_rules = (
                "És o assistente virtual oficial do promotor de vendas de crédito. "
                "Objectivo: atender solicitantes de crédito, recolher documentos e orientar sobre simulações.\n"
                "Respostas curtas, profissionais e puramente em português de Moçambique."
            )

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
                send_whatsapp(phone_number, "⚠️ O período de teste gratuito deste assistente expirou.", instance_name=nome_instancia_atual)
                return

            if msg_clean.startswith("/criar-arte"):
                pedido = message_text.replace("/criar-arte", "").strip()
                if not pedido:
                    send_whatsapp(phone_number, "✍️ Exemplo: `/criar-arte Banner de crédito rápido`", instance_name=nome_instancia_atual)
                    return
                send_whatsapp(phone_number, "🎨 A criar a sua arte com IA...", instance_name=nome_instancia_atual)
                prompt_ingles = criar_prompt_profissional_groq(pedido)
                link_imagem = gerar_url_imagem_pollinations(prompt_ingles)
                
                payload = {"number": phone_number, "caption": f"✨ *Arte Gerada!*\n🎯 _{pedido}_", "media": link_imagem, "mediatype": "image", "fileName": "arte.jpg"}
                requests.post(f"{os.getenv('EVOLUTION_API_URL')}/message/sendMedia/{nome_instancia_atual}", headers={"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}, json=payload, timeout=25)
                return

            if document_message and phone_number.split('@')[0] in nome_instancia_atual:
                url_doc = document_message.get('url')
                file_name = document_message.get('fileName', '').lower()

                if file_name.endswith(('.xlsx', '.xls')):
                    send_whatsapp(phone_number, "📊 A processar folha de cálculo Excel...", instance_name=nome_instancia_atual)
                    texto_excel = extrair_texto_excel_url(url_doc)
                    if texto_excel:
                        client_doc_ref.set({"diretrizes_corporativas": f"{dados_cliente.get('diretrizes_corporativas', '')}\n\n=== EXCEL ===\n{texto_excel}"}, merge=True)
                        send_whatsapp(phone_number, "✅ *Excel Integrado!* Simulador e dados atualizados.", instance_name=nome_instancia_atual)
                    return

                elif file_name.endswith('.pdf') or not file_name:
                    send_whatsapp(phone_number, "📄 A processar documento PDF...", instance_name=nome_instancia_atual)
                    texto_pdf = extrair_texto_pdf_url(url_doc)
                    if texto_pdf:
                        client_doc_ref.set({"diretrizes_corporativas": f"{dados_cliente.get('diretrizes_corporativas', '')}\n\n=== PDF ===\n{texto_pdf}"}, merge=True)
                        send_whatsapp(phone_number, "✅ *PDF Integrado!* Dados atualizados.", instance_name=nome_instancia_atual)
                    return

            if msg_clean == "/grupos":
                grupos = listar_grupos_instancia(nome_instancia_atual)
                if not grupos:
                    send_whatsapp(phone_number, "❌ Não foi possível encontrar nenhum grupo ativo nesta instância. Certifique-se de que o WhatsApp está conectado corretamente e possui grupos sincronizados.", instance_name=nome_instancia_atual)
                    return
                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").set({"grupos": grupos, "timestamp": firestore.SERVER_TIMESTAMP})
                txt_resp = "📋 *SELECIONE OS GRUPOS:*\n\n" + "\n".join([f"*{g['indice']}* - {g['nome']} ({g['qtd']} membros)" for g in grupos]) + "\n\nResponda ex: `1, 3`"
                send_whatsapp(phone_number, txt_resp, instance_name=nome_instancia_atual)
                return

            doc_map = db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").get()
            if doc_map.exists and re.match(r'^[\d\s,]+$', msg_clean):
                lista_g = doc_map.to_dict().get("grupos", [])
                indices = [int(i.strip()) for i in msg_clean.split(",") if i.strip().isdigit()]
                filtrados = [g for g in lista_g if g["indice"] in indices]
                telefones = extrair_participantes_de_grupos_especificos(filtrados)
                
                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").set({"telefones": telefones})
                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").delete()
                send_whatsapp(phone_number, f"✅ *{len(telefones)} contactos extraídos!* Responda *SIM* para iniciar a campanha.", instance_name=nome_instancia_atual)
                return

            if msg_clean == "sim":
                temp_ref = db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").get()
                if temp_ref.exists:
                    telefones = temp_ref.to_dict().get("telefones", [])
                    send_whatsapp(phone_number, f"🚀 A disparar para {len(telefones)} contactos...", instance_name=nome_instancia_atual)
                    threading.Thread(target=executar_campanha_duas_etapas, args=(nome_instancia_atual, telefones, "Bom dia! Tudo bem?")).start()
                    db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").delete()
                    return

            # Se a mensagem veio do próprio dono e já passou pelos comandos acima, não envia para a IA
            if is_from_me:
                return

            # =======================================================
            # 🔄 GESTÃO DE ESTADO DE ATENDIMENTO HUMANO
            # =======================================================
            conversa_doc = conversa_ref.get()
            if conversa_doc.exists and conversa_doc.to_dict().get("status_atendimento") == "humano":
                if msg_clean in ["/bot", "/reset", "continuar", "bot"]:
                    conversa_ref.set({"status_atendimento": "bot", "ultima_interacao": agora}, merge=True)
                    send_whatsapp(phone_number, "🤖 O assistente virtual foi reativado com sucesso! Como posso ajudar?", instance_name=nome_instancia_atual)
                    return

                conversa_ref.set({"ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                return

            gatilhos_humano = ["falar com atendente", "suporte humano", "atendente", "humano", "#suporte", "assistente humano"]
            if any(g in msg_clean for g in gatilhos_humano):
                conversa_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                send_whatsapp(
                    phone_number, 
                    "🔔 A transferir para um atendente humano... Por favor, aguarde até 3 minutos! 🤝", 
                    instance_name=nome_instancia_atual
                )
                threading.Thread(target=verificar_espera_humano_isolado, args=(nome_instancia_atual, phone_number)).start()
                return

            # =======================================================
            # 🤖 PROCESSAMENTO DE MENSAGENS COM A IA (GROQ ENGINE)
            # =======================================================
            docs_h = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
            lista_m = [d.to_dict() for d in docs_h]
            lista_m.reverse()

            contents = []
            for m in lista_m:
                role_g = "assistant" if m.get('role') in ["assistant", "model", "atendente"] else "user"
                contents.append({"role": role_g, "parts": [{"text": m.get('text', '')}]})
            
            contents.append({"role": "user", "parts": [{"text": message_text}]})

            diretrizes = dados_cliente.get("diretrizes_corporativas", default_rules)
            
            sys_instruction = f"""Você é um assistente comercial profissional e focado em negócios.
Comunicação em Português de Moçambique, tom sério e corporativo.
Respostas curtas e diretas (2 a 3 linhas por bloco).

INFORMAÇÕES E TABELAS CARREGADAS:
{diretrizes}

REGRA OBRIGATÓRIA DE TRANSIÇÃO:
- NUNCA adicione [TRANSICAO_HUMANO] em saudações (ex: "bom dia", "olá", "boa tarde") nem em perguntas normais.
- APENAS adicione a tag [TRANSICAO_HUMANO] no final da resposta se o cliente EXIGIR explicitamente falar com uma pessoa/atendente humano e você não conseguir resolver."""

            response_text = chamar_groq_rest(contents, system_instruction=sys_instruction, temperature=0.1)
            historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})

            e_saudacao = any(s in msg_clean for s in ["bom dia", "boa tarde", "boa noite", "olá", "ola", "oy", "oi"])
            
            if "[TRANSICAO_HUMANO]" in response_text and not e_saudacao:
                response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
                conversa_ref.set({"status_atendimento": "humano", "ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                
                if response_text:
                    send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
                else:
                    send_whatsapp(phone_number, "A transferir o seu atendimento para a equipa humana... Por favor, aguarde até 3 minutos!", instance_name=nome_instancia_atual)
                
                historico_ref.add({"role": "assistant", "text": response_text, "timestamp": agora})
                threading.Thread(target=verificar_espera_humano_isolado, args=(nome_instancia_atual, phone_number)).start()
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

def loop_interno_lembretes():
    ultima_execucao_chave = ""
    while True:
        try:
            agora = datetime.now(timezone(timedelta(hours=2)))
            chave_atual = f"{agora.strftime('%Y-%m-%d_%H:%M')}"
            if chave_atual != ultima_execucao_chave:
                if agora.hour == 9 and agora.minute == 30:
                    enviar_lembretes_em_massa("manhã")
                    ultima_execucao_chave = chave_atual
                elif agora.hour == 17 and agora.minute == 0:
                    enviar_lembretes_em_massa("tarde")
                    ultima_execucao_chave = chave_atual
        except Exception as e:
            print(f"❌ Erro loop lembretes: {e}")
        time.sleep(30)

threading.Thread(target=loop_interno_lembretes, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
