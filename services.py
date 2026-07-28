# services.py
import os
import json
import time
import requests
import threading
import re
import io
import base64
import tempfile
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pypdf import PdfReader
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------------------
# Configuração de Logging
# ---------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------
# Inicialização e helpers
# ---------------------------
_db = None

def init_services():
    global _db
    if firebase_admin._apps:
        _db = firestore.client()
        return
    firebase_config_env = os.getenv('FIREBASE_CONFIG')
    try:
        if firebase_config_env:
            firebase_config = json.loads(firebase_config_env)
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
        _db = firestore.client()
    except Exception as e:
        logger.error(f"Erro ao inicializar Firebase com credenciais: {e}")
        try:
            firebase_admin.initialize_app()
            _db = firestore.client()
        except Exception as ex:
            logger.critical(f"Falha crítica ao inicializar Firebase: {ex}")
            raise

def get_db():
    global _db
    if _db is None:
        init_services()
    return _db

# ---------------------------
# Multitenancy Firestore helpers
# ---------------------------
def make_empresa_id_from_phone(phone_number: str) -> str:
    if not phone_number:
        return str(uuid.uuid4())
    cleaned = re.sub(r'\D', '', phone_number)
    return cleaned or str(uuid.uuid4())

def upsert_empresa_from_onboarding(empresa_id: str, data: dict):
    db = get_db()
    doc_ref = db.collection('empresas').document(empresa_id)
    data_to_set = dict(data)
    data_to_set['updated_at'] = datetime.now(timezone.utc)
    doc_ref.set(data_to_set, merge=True)
    return doc_ref

def get_empresa_by_phone(phone_number: str):
    db = get_db()
    try:
        docs = db.collection('empresas').where('phone_number', '==', phone_number).limit(1).stream()
        for d in docs:
            return (d.id, d)
    except Exception as e:
        logger.warning(f"Erro ao buscar empresa por telefone: {e}")
    empresa_id = make_empresa_id_from_phone(phone_number)
    doc = db.collection('empresas').document(empresa_id).get()
    if doc.exists:
        return (empresa_id, doc)
    return (None, None)

def get_empresa_by_id(empresa_id: str):
    db = get_db()
    doc = db.collection('empresas').document(empresa_id).get()
    return (empresa_id, doc) if doc.exists else (None, None)

def append_empresa_history(empresa_id: str, entry: dict):
    try:
        db = get_db()
        events = db.collection('empresas').document(empresa_id).collection('events')
        events.add(entry)
    except Exception as e:
        logger.error(f"Erro ao adicionar histórico da empresa {empresa_id}: {e}")

# ---------------------------
# File extraction
# ---------------------------
def extrair_texto_pdf_url(pdf_url):
    try:
        r = requests.get(pdf_url, timeout=25)
        if r.status_code == 200:
            pdf_file = io.BytesIO(r.content)
            reader = PdfReader(pdf_file)
            pages = []
            for idx, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"\n--- PÁGINA {idx} ---\n{text}")
            return "".join(pages)
    except Exception as e:
        logger.error(f"Erro ao extrair texto do PDF: {e}")
    return ""

def extrair_texto_excel_url(excel_url):
    try:
        r = requests.get(excel_url, timeout=25)
        if r.status_code == 200:
            todas_abas = pd.read_excel(io.BytesIO(r.content), sheet_name=None)
            return "".join([f"\n--- ABA: {aba} ---\n{df.to_string(index=False)}\n" for aba, df in todas_abas.items()])
    except Exception as e:
        logger.error(f"Erro ao extrair texto do Excel: {e}")
    return ""

# ---------------------------
# Evolution (WhatsApp) helpers
# ---------------------------
EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL')
EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY')
EVOLUTION_INSTANCE_NAME = os.getenv('EVOLUTION_INSTANCE_NAME')

def send_whatsapp(to, text, instance_name=None):
    if not text or not to:
        return False
    instance_name = instance_name or EVOLUTION_INSTANCE_NAME
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    try:
        requests.post(f"{EVOLUTION_API_URL}/chat/sendPresence/{instance_name}", headers=headers, json={"number": to, "presence": "composing"}, timeout=5)
        time.sleep(1)
        requests.post(f"{EVOLUTION_API_URL}/message/sendText/{instance_name}", headers=headers, json={"number": to, "text": text}, timeout=10)
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem WhatsApp para {to}: {e}")
        return False

def criar_e_configurar_instancia_automatica(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
        requests.delete(f"{EVOLUTION_API_URL}/instance/logout/{client_instance}", headers=headers, timeout=5)
        requests.delete(f"{EVOLUTION_API_URL}/instance/delete/{client_instance}", headers=headers, timeout=5)
        time.sleep(2)
        requests.post(f"{EVOLUTION_API_URL}/instance/create", headers=headers, json={"instanceName": client_instance, "qrcode": True, "integration": "WHATSAPP-BAILEYS"}, timeout=10).raise_for_status()
        webhook_target_url = os.getenv('WEBHOOK_URL')
        if webhook_target_url:
            requests.post(f"{EVOLUTION_API_URL}/webhook/set/{client_instance}", headers=headers, json={"url": webhook_target_url, "enabled": True, "events": ["MESSAGES_UPSERT"]}, timeout=10)
        return True
    except Exception as e:
        logger.error(f"Erro ao criar instância automática para {phone_number}: {e}")
        return False

def gerar_e_enviar_qrcode_central(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
        res = requests.get(f"{EVOLUTION_API_URL}/instance/connect/{client_instance}", headers=headers, timeout=10).json()
        if res.get("instance", {}).get("state") == "open":
            send_whatsapp(phone_number, "✅ A sua instância já se encontra ativa!")
            return True
        base64_qr = res.get("base64")
        if not base64_qr:
            return False
        if "," in base64_qr:
            base64_qr = base64_qr.split(",")[1]
        payload = {"number": phone_number, "caption": "🤖 *QR Code do Negobot Moz!*\\nEscaneie com o WhatsApp da empresa para ativar.", "media": base64_qr, "mediatype": "image", "fileName": "qr.png"}
        requests.post(f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE_NAME}", headers=headers, json=payload, timeout=15)
        return True
    except Exception as e:
        logger.error(f"Erro ao gerar/enviar QR code para {phone_number}: {e}")
        return False

# ---------------------------
# Groq integration & Handlers
# ---------------------------
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'llama-3.2-90b-vision-preview')
GROQ_WHISPER_MODEL = os.getenv('GROQ_WHISPER_MODEL', 'whisper-large-v3')

def chamar_groq_rest(contents_payload, system_instruction="", temperature=0.0, max_tokens=600, top_p=1.0, frequency_penalty=0.0, presence_penalty=0.0, model=None):
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY não configurada.")
        return ""
    model = model or GROQ_MODEL
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
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
    payload = {"model": model, "messages": messages, "temperature": float(temperature), "max_tokens": int(max_tokens), "top_p": float(top_p), "frequency_penalty": float(frequency_penalty), "presence_penalty": float(presence_penalty)}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        data = response.json()
        if response.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Erro na API Groq: {response.status_code} - {data}")
    except Exception as e:
        logger.error(f"Exceção ao chamar Groq REST: {e}")
    return ""

def transcrever_audio_groq(audio_url: str) -> str:
    if not GROQ_API_KEY or not audio_url:
        return ""
    try:
        r = requests.get(audio_url, timeout=25)
        if r.status_code != 200:
            return ""
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp:
            tmp.write(r.content)
            tmp_path = tmp.name

        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        
        with open(tmp_path, "rb") as f:
            files = {"file": ("audio.ogg", f, "audio/ogg")}
            data = {"model": GROQ_WHISPER_MODEL, "language": "pt"}
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

        if response.status_code == 200:
            return response.json().get("text", "").strip()
        else:
            logger.error(f"Erro na transcrição de áudio: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Exceção ao transcrever áudio: {e}")
    return ""

def analisar_imagem_groq(image_url: str, instrucao: str = "Analise e descreva esta imagem em detalhe.") -> str:
    if not GROQ_API_KEY or not image_url:
        return ""
    try:
        r = requests.get(image_url, timeout=20)
        if r.status_code != 200:
            return ""
        
        encoded_image = base64.b64encode(r.content).decode('utf-8')
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        
        payload = {
            "model": GROQ_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instrucao},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                    ]
                }
            ],
            "max_tokens": 500
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        data = response.json()
        if response.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Erro na análise de imagem: {response.status_code} - {data}")
    except Exception as e:
        logger.error(f"Exceção ao analisar imagem: {e}")
    return ""

# ---------------------------
# Safety helpers
# ---------------------------
BLACKLIST_LINK_TOKENS = ["http://", "https://", "www.", "painel", "dashboard", ".com", ".net"]
SUSPICIOUS_VERBS = ["acesse", "clique", "visite", "faça login", "entre em", "registe-se"]

def contains_forbidden_link_or_instruction(text: str) -> bool:
    t = (text or "").lower()
    for token in BLACKLIST_LINK_TOKENS + SUSPICIOUS_VERBS:
        if token in t:
            return True
    return False

def contains_unverified_numbers(text: str, dados_empresa: dict) -> bool:
    if not text:
        return False
    nums = set(re.findall(r'\d{2,}', text))
    if not nums:
        return False
    known = " ".join([str(v) for v in dados_empresa.values() if v])
    for n in nums:
        if str(n) not in known:
            return True
    return False

def enforce_response_safety(response_text: str, dados_empresa: dict):
    if not response_text:
        return ("Desculpe, não tenho essa informação no meu sistema no momento. Gostaria que eu te conectasse com um atendente humano? [TRANSICAO_HUMANO]", True)
    if contains_forbidden_link_or_instruction(response_text):
        return ("Desculpe, não tenho essa informação no meu sistema no momento. Gostaria que eu te conectasse com um atendente humano? [TRANSICAO_HUMANO]", True)
    if contains_unverified_numbers(response_text, dados_empresa):
        return ("Desculpe, não tenho essa informação no meu sistema no momento. Gostaria que eu te conectasse com um atendente humano? [TRANSICAO_HUMANO]", True)
    return (response_text, False)

def build_strict_system_instruction(dados_contexto: dict, role_label: str = "assistente"):
    diretrizes = dados_contexto.get("diretrizes_corporativas", "")
    servicos = dados_contexto.get("servicos", "")
    precos = dados_contexto.get("precos", "")
    catalogo = dados_contexto.get("servicos_catalogo_excel", "")
    instruction = f"""
Você é o {role_label} da empresa. Responda somente com base nas informações explicitamente fornecidas abaixo.
Se a resposta não puder ser construída a partir desses dados, responda exatamente:
"Desculpe, não tenho essa informação no meu sistema no momento. Gostaria que eu te conectasse com um atendente humano?"
e inclua a tag [TRANSICAO_HUMANO] no final.

DADOS DISPONÍVEIS (use apenas estes, não invente nada):
DIRETRIZES: {diretrizes}
SERVIÇOS: {servicos}
PREÇOS: {precos}
CATÁLOGO: {catalogo}

REGRAS:
1) NUNCA invente nomes, preços, links, prazos, números de telefone, ou procedimentos que não estejam nos DADOS DISPONÍVEIS.
2) Não sugira sites, painéis, ou ações externas.
3) Responda em Português de Moçambique, de forma curta e direta.
4) Se a pergunta for geral e não estiver coberta pelos dados, use o fallback acima.
"""
    return instruction

# ---------------------------
# Onboarding and updates
# ---------------------------
def handle_onboarding_from_message(phone_number: str, message_text: str, document_message: dict = None):
    empresa_id, empresa_doc = get_empresa_by_phone(phone_number)
    agora = datetime.now(timezone.utc)
    if empresa_doc is None:
        empresa_id = make_empresa_id_from_phone(phone_number)
        upsert_empresa_from_onboarding(empresa_id, {"phone_number": phone_number, "status_plano": "pending_onboarding", "data_registro": agora})
        send_whatsapp(phone_number, "Olá! Para configurar o seu assistente, por favor envie os dados do negócio (serviços, preços, horário) ou um ficheiro PDF/Excel com o roteiro.", instance_name=None)
        append_empresa_history(empresa_id, {"event": "onboarding_requested", "timestamp": agora, "source": "bot"})
        return empresa_id
    if document_message:
        url_doc = document_message.get('url')
        file_name = (document_message.get('fileName') or "").lower()
        updates = {}
        if file_name.endswith(('.xlsx', '.xls')):
            updates['servicos_catalogo_excel'] = extrair_texto_excel_url(url_doc)
        elif file_name.endswith('.pdf') or not file_name:
            updates['diretrizes_corporativas'] = extrair_texto_pdf_url(url_doc)
        if updates:
            upsert_empresa_from_onboarding(empresa_id, updates)
            send_whatsapp(phone_number, "✅ Obrigado — os dados da sua empresa foram atualizados com sucesso.", instance_name=None)
            append_empresa_history(empresa_id, {"event": "onboarding_file_uploaded", "timestamp": agora, "file": file_name})
    return empresa_id

def handle_empresa_update_from_text(empresa_id: str, phone_number: str, message_text: str):
    updates = {}
    m_serv = re.search(r'servi[cç]os?:\s*(.+)', message_text, flags=re.I)
    m_prec = re.search(r'pre[cç]os?:\s*(.+)', message_text, flags=re.I)
    m_hor = re.search(r'horari[oó]:\s*(.+)', message_text, flags=re.I)
    if m_serv:
        updates['servicos'] = m_serv.group(1).strip()
    if m_prec:
        updates['precos'] = m_prec.group(1).strip()
    if m_hor:
        updates['horario'] = m_hor.group(1).strip()
    if updates:
        upsert_empresa_from_onboarding(empresa_id, updates)
        append_empresa_history(empresa_id, {"event": "empresa_updated_via_text", "timestamp": datetime.now(timezone.utc), "by": phone_number})
        send_whatsapp(phone_number, "✅ Informações atualizadas com sucesso.", instance_name=None)
        return True
    return False

# ---------------------------
# Webhook processing (main)
# ---------------------------
PROCESSADOS = {}
processados_lock = threading.Lock()
CENTRAL_INSTANCE = os.getenv('EVOLUTION_INSTANCE_NAME')
NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')
ADMIN_NUMBER = os.getenv('ADMIN_NUMBER')

def _process(data):
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

        if audio_message and audio_message.get('url'):
            send_whatsapp(phone_number, "🎙️ *A ouvir o seu áudio...*", instance_name=nome_instancia_atual)
            message_text = transcrever_audio_groq(audio_message.get('url'))

        if image_message and not (message_text or "").startswith('/criar-arte'):
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

        agora = datetime.now(timezone.utc)
        is_from_me = key.get('fromMe') is True or str(key.get('fromMe')).lower() == 'true'
        db = get_db()

        # Identificar empresa
        empresa_id = None
        empresa_doc = None
        if nome_instancia_atual and nome_instancia_atual != CENTRAL_INSTANCE:
            empresa_id, empresa_doc = get_empresa_by_id(nome_instancia_atual)
            if empresa_doc is None:
                empresa_id, empresa_doc = get_empresa_by_phone(phone_number)
        else:
            empresa_id, empresa_doc = get_empresa_by_phone(phone_number)

        # Se não existir empresa, iniciar onboarding
        if empresa_doc is None:
            handle_onboarding_from_message(phone_number, message_text, document_message)
            return

        # Se for instância central e remetente for admin/atendente, permitir updates
        if nome_instancia_atual == CENTRAL_INSTANCE:
            if document_message:
                handle_onboarding_from_message(phone_number, message_text, document_message)
                return
            if is_from_me or (ADMIN_NUMBER and ADMIN_NUMBER in phone_number):
                updated = handle_empresa_update_from_text(empresa_id, phone_number, message_text)
                if updated:
                    return

        # Atendimento multilocatário: responder apenas com dados da empresa
        conversa_ref = db.collection('empresas').document(empresa_id).collection('conversas').document(phone_number)
        historico_ref = conversa_ref.collection('historico')

        if is_from_me:
            conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
            historico_ref.add({"role": "atendente", "text": message_text, "timestamp": agora})
            return

        # Montar histórico para contexto
        docs_h = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
        contents = [{"role": "assistant" if m.to_dict().get('role') in ["assistant", "atendente"] else "user", "parts": [{"text": m.to_dict().get('text', '')}]} for m in list(docs_h)[::-1]]
        contents.append({"role": "user", "parts": [{"text": message_text}]})

        dados_empresa = empresa_doc.to_dict() if empresa_doc else {}
        dados_contexto = {
            "diretrizes_corporativas": dados_empresa.get("diretrizes_corporativas", ""),
            "servicos": dados_empresa.get("servicos", ""),
            "precos": dados_empresa.get("precos", ""),
            "servicos_catalogo_excel": dados_empresa.get("servicos_catalogo_excel", "")
        }
        sys_inst = build_strict_system_instruction(dados_contexto, role_label="assistente virtual da empresa")
        response_text = chamar_groq_rest(contents, system_instruction=sys_inst, temperature=0.0, max_tokens=600)

        final_text, flagged = enforce_response_safety(response_text, dados_empresa)
        if flagged:
            conversa_ref.set({"status_atendimento": "humano", "ultima_interacao": agora}, merge=True)
            send_whatsapp(phone_number, final_text, instance_name=nome_instancia_atual)
            try:
                historico_ref.add({"role": "assistant", "text": final_text, "timestamp": agora})
            except Exception:
                pass
        else:
            send_whatsapp(phone_number, final_text, instance_name=nome_instancia_atual)
            try:
                historico_ref.add({"role": "assistant", "text": final_text, "timestamp": agora})
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Erro Crítico no Webhook: {e}", exc_info=True)

def processar_webhook_background(data):
    threading.Thread(target=_process, args=(data,), daemon=True).start()
