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
# Inicialização Firebase
# ---------------------------
_db = None

def init_services():
    """Inicializa o cliente Firestore com tratamento de erro melhorado."""
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
        logger.info("Firebase inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar Firebase com config: {e}")
        try:
            firebase_admin.initialize_app()
            _db = firestore.client()
            logger.info("Firebase inicializado em modo padrão")
        except Exception as ex:
            logger.critical(f"Falha crítica ao inicializar Firebase: {ex}")
            raise

def get_db():
    """Retorna o cliente Firestore, inicializando se necessário."""
    global _db
    if _db is None:
        init_services()
    return _db

# ---------------------------
# Helpers do Firestore / Empresa
# ---------------------------
def make_empresa_id_from_phone(phone_number: str) -> str:
    """Gera ID da empresa a partir do número de telefone."""
    cleaned = re.sub(r'\D', '', phone_number or '')
    return cleaned or str(uuid.uuid4())

def upsert_empresa_from_onboarding(empresa_id: str, data: dict):
    """Cria ou atualiza dados da empresa."""
    db = get_db()
    doc_ref = db.collection('empresas').document(empresa_id)
    data_to_set = dict(data)
    data_to_set['updated_at'] = datetime.now(timezone.utc)
    doc_ref.set(data_to_set, merge=True)
    return doc_ref

def get_empresa_by_phone(phone_number: str):
    """Busca empresa pelo número de telefone."""
    db = get_db()
    clean_phone = re.sub(r'\D', '', phone_number or '')
    try:
        docs = db.collection('empresas').where('phone_number', '==', clean_phone).limit(1).stream()
        for d in docs:
            return (d.id, d)
    except Exception as e:
        logger.warning(f"Erro ao buscar empresa por telefone: {e}")
    
    empresa_id = make_empresa_id_from_phone(clean_phone)
    doc = db.collection('empresas').document(empresa_id).get()
    if doc.exists:
        return (empresa_id, doc)
    return (None, None)

def get_empresa_by_id(empresa_id: str):
    """Busca empresa pelo ID."""
    db = get_db()
    doc = db.collection('empresas').document(empresa_id).get()
    return (empresa_id, doc) if doc.exists else (None, None)

def append_empresa_history(empresa_id: str, entry: dict):
    """Adiciona entrada ao histórico de eventos da empresa."""
    try:
        db = get_db()
        entry['timestamp'] = datetime.now(timezone.utc)
        db.collection('empresas').document(empresa_id).collection('events').add(entry)
    except Exception as e:
        logger.error(f"Erro ao adicionar histórico da empresa {empresa_id}: {e}")

# ---------------------------
# Gestão de Histórico de Conversas (CORRIGIDO)
# ---------------------------
def get_chat_history(empresa_id: str, phone_number: str, limit: int = 10):
    """
    Busca o histórico de mensagens de uma conversa.
    
    Args:
        empresa_id: ID da empresa
        phone_number: Número de telefone do cliente (obrigatório)
        limit: Número máximo de mensagens a retornar
    
    Returns:
        Lista de mensagens formatadas para o Groq
    """
    try:
        db = get_db()
        
        # VALIDAÇÃO: phone_number é obrigatório
        if not phone_number:
            logger.warning(f"Tentativa de buscar histórico sem phone_number para empresa {empresa_id}")
            return []

        historico_ref = (
            db.collection('empresas')
            .document(empresa_id)
            .collection('conversas')
            .document(phone_number)
            .collection('historico')
        )
        docs = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()
        
        mensagens = []
        for doc in list(docs)[::-1]:
            d = doc.to_dict()
            role = "assistant" if d.get("role") in ["assistant", "atendente"] else "user"
            text = d.get("text", "").strip()
            if text:
                mensagens.append({"role": role, "parts": [{"text": text}]})
        return mensagens
    except Exception as e:
        logger.error(f"Erro ao buscar histórico para {phone_number}: {e}")
        return []

def save_chat_history(empresa_id: str, phone_number: str, role: str = "user", text: str = ""):
    """
    Guarda uma mensagem no histórico do Firestore.
    
    Args:
        empresa_id: ID da empresa
        phone_number: Número de telefone do cliente
        role: Papel (user/assistant/atendente)
        text: Conteúdo da mensagem
    
    Returns:
        True se guardado com sucesso, False caso contrário
    """
    try:
        db = get_db()
        
        # VALIDAÇÃO: todos os argumentos são obrigatórios
        if not empresa_id or not phone_number or not text:
            logger.warning(f"Tentativa de salvar histórico com argumentos inválidos: empresa={empresa_id}, phone={phone_number}, text_len={len(text)}")
            return False

        # VALIDAÇÃO: role deve ser válido
        if role not in ["user", "assistant", "atendente"]:
            logger.warning(f"Role inválido: {role}, usando 'user' como padrão")
            role = "user"

        historico_ref = (
            db.collection('empresas')
            .document(empresa_id)
            .collection('conversas')
            .document(phone_number)
            .collection('historico')
        )
        historico_ref.add({
            "role": role,
            "text": text.strip(),
            "timestamp": datetime.now(timezone.utc)
        })
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar histórico para {phone_number}: {e}")
        return False

# ---------------------------
# Extração de Ficheiros
# ---------------------------
def extrair_texto_pdf_url(pdf_url):
    """Extrai texto de um PDF a partir de URL."""
    if not pdf_url:
        logger.warning("PDF URL vazia")
        return ""
    
    try:
        r = requests.get(pdf_url, timeout=25)
        if r.status_code == 200:
            pdf_file = io.BytesIO(r.content)
            reader = PdfReader(pdf_file)
            pages = [f"\n--- PÁGINA {idx} ---\n{p.extract_text() or ''}" for idx, p in enumerate(reader.pages, 1)]
            return "".join(pages)
        else:
            logger.warning(f"Erro ao baixar PDF: status {r.status_code}")
    except Exception as e:
        logger.error(f"Erro ao extrair texto do PDF: {e}")
    return ""

def extrair_texto_excel_url(excel_url):
    """Extrai texto de um ficheiro Excel a partir de URL."""
    if not excel_url:
        logger.warning("Excel URL vazia")
        return ""
    
    try:
        r = requests.get(excel_url, timeout=25)
        if r.status_code == 200:
            todas_abas = pd.read_excel(io.BytesIO(r.content), sheet_name=None)
            return "".join([f"\n--- ABA: {aba} ---\n{df.to_string(index=False)}\n" for aba, df in todas_abas.items()])
        else:
            logger.warning(f"Erro ao baixar Excel: status {r.status_code}")
    except Exception as e:
        logger.error(f"Erro ao extrair texto do Excel: {e}")
    return ""

# ---------------------------
# Comunicação WhatsApp (Evolution API)
# ---------------------------
EVOLUTION_API_URL = os.getenv('EVOLUTION_API_URL', '').rstrip('/')
EVOLUTION_API_KEY = os.getenv('EVOLUTION_API_KEY')
EVOLUTION_INSTANCE_NAME = os.getenv('EVOLUTION_INSTANCE_NAME')
ADMIN_NUMBER = os.getenv('ADMIN_NUMBER')

def send_whatsapp(to, text, instance_name=None):
    """Envia mensagem via WhatsApp pela Evolution API com retry."""
    if not text or not to:
        logger.warning("Tentativa de enviar WhatsApp com texto ou número vazio")
        return False
    
    clean_to = re.sub(r'\D', '', str(to))
    instance_name = instance_name or EVOLUTION_INSTANCE_NAME
    
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not instance_name:
        logger.error("Configurações da Evolution API incompletas em variáveis de ambiente!")
        return False

    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    try:
        # Enviar indicador de digitação (sem falhar se não conseguir)
        try:
            requests.post(
                f"{EVOLUTION_API_URL}/chat/sendPresence/{instance_name}",
                headers=headers,
                json={"number": clean_to, "presence": "composing"},
                timeout=5
            )
            time.sleep(0.5)
        except Exception as e:
            logger.debug(f"Aviso: não foi possível enviar indicador de digitação: {e}")
        
        # Enviar mensagem de texto
        res = requests.post(
            f"{EVOLUTION_API_URL}/message/sendText/{instance_name}",
            headers=headers,
            json={"number": clean_to, "text": text},
            timeout=10
        )
        if res.status_code not in [200, 201]:
            logger.error(f"Erro ao enviar WhatsApp ({res.status_code}): {res.text}")
            return False
        
        logger.debug(f"Mensagem enviada para {clean_to}")
        return True
    except Exception as e:
        logger.error(f"Exceção ao enviar mensagem WhatsApp para {clean_to}: {e}")
        return False

def notificar_erro_admin(mensagem: str):
    """Notifica o administrador de um erro crítico via WhatsApp."""
    if not ADMIN_NUMBER:
        logger.warning("ADMIN_NUMBER não configurado, notificação não enviada")
        return
    try:
        send_whatsapp(ADMIN_NUMBER, f"🚨 *ERRO CRÍTICO NO SISTEMA* 🚨\n\n{mensagem}")
    except Exception as e:
        logger.error(f"Erro ao notificar admin: {e}")

# ---------------------------
# Integração Groq (LLM & Multimodal)
# ---------------------------
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'llama-3.2-90b-vision-preview')
GROQ_WHISPER_MODEL = os.getenv('GROQ_WHISPER_MODEL', 'whisper-large-v3')

def chamar_groq_rest(contents_payload, system_instruction="", temperature=0.0, max_tokens=600):
    """Chama a API Groq para gerar resposta."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY não definida.")
        return ""
    
    if not contents_payload:
        logger.warning("contents_payload vazio")
        return ""
    
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

    if not messages:
        logger.warning("Nenhuma mensagem válida para enviar para Groq")
        return ""

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens)
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        data = response.json()
        if response.status_code == 200 and "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Erro na API Groq: {response.status_code} - {data}")
    except Exception as e:
        logger.error(f"Exceção ao chamar Groq: {e}")
    return ""

def transcrever_audio_groq(audio_url: str) -> str:
    """Transcreve áudio para texto usando Groq Whisper."""
    if not GROQ_API_KEY or not audio_url:
        logger.warning("Audio URL vazia ou GROQ_API_KEY não definida")
        return ""
    
    tmp_path = None
    try:
        r = requests.get(audio_url, timeout=25)
        if r.status_code != 200:
            logger.warning(f"Erro ao baixar áudio: status {r.status_code}")
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
        
        if response.status_code == 200:
            transcricao = response.json().get("text", "").strip()
            logger.info(f"Áudio transcrito com sucesso: {len(transcricao)} caracteres")
            return transcricao
        else:
            logger.warning(f"Erro na transcrição: status {response.status_code}")
    except Exception as e:
        logger.error(f"Erro na transcrição de áudio: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Erro ao limpar arquivo temporário: {e}")
    
    return ""

def analisar_imagem_groq(image_url: str, instrucao: str = "Analise e descreva esta imagem.") -> str:
    """Analisa imagem usando Groq Vision."""
    if not GROQ_API_KEY or not image_url:
        logger.warning("Image URL vazia ou GROQ_API_KEY não definida")
        return ""
    
    try:
        r = requests.get(image_url, timeout=20)
        if r.status_code != 200:
            logger.warning(f"Erro ao baixar imagem: status {r.status_code}")
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
            analise = data["choices"][0]["message"]["content"].strip()
            logger.info(f"Imagem analisada com sucesso: {len(analise)} caracteres")
            return analise
        else:
            logger.warning(f"Erro na análise de imagem: {response.status_code}")
    except Exception as e:
        logger.error(f"Erro na análise de imagem: {e}")
    return ""

# ---------------------------
# Regras de Negócio e Prompts
# ---------------------------
TIMEOUT_HUMANO_MINUTOS = int(os.getenv('TIMEOUT_HUMANO_MINUTOS', 2))

def build_strict_system_instruction(dados_contexto: dict, role_label: str = "assistente"):
    """Constrói a instrução do sistema com dados da empresa."""
    diretrizes = dados_contexto.get("diretrizes_corporativas", "")
    servicos = dados_contexto.get("servicos", "")
    precos = dados_contexto.get("precos", "")
    catalogo = dados_contexto.get("servicos_catalogo_excel", "")
    return f"""
Você é o {role_label} da empresa. Responda apenas com base nas informações fornecidas abaixo.
Se a informação não existir nos dados, responda exatamente:
"Desculpe, não tenho essa informação no meu sistema no momento. Gostaria que eu te conectasse com um atendente humano?" [TRANSICAO_HUMANO]

DADOS DA EMPRESA:
DIRETRIZES: {diretrizes}
SERVIÇOS: {servicos}
PREÇOS: {precos}
CATÁLOGO: {catalogo}

REGRAS:
1) NUNCA invente preços, prazos, números ou procedimentos.
2) Responda em Português de Moçambique, de forma direta e cordial.
"""

def checar_timeout_atendimento_humano(empresa_id: str, phone_number: str) -> bool:
    """Verifica se o timeout do atendimento humano foi excedido."""
    try:
        db = get_db()
        conversa_ref = db.collection('empresas').document(empresa_id).collection('conversas').document(phone_number)
        doc = conversa_ref.get()
        if not doc.exists:
            return False
        
        dados = doc.to_dict()
        if dados.get("status_atendimento") == "humano":
            ultima_interacao = dados.get("ultima_interacao")
            if ultima_interacao:
                agora = datetime.now(timezone.utc)
                
                # CORRIGIDO: Conversão correta de Firestore Timestamp
                if hasattr(ultima_interacao, 'timestamp'):
                    # É um Firestore Timestamp
                    ultima_interacao_dt = ultima_interacao.replace(tzinfo=timezone.utc)
                else:
                    # Já é um datetime
                    ultima_interacao_dt = ultima_interacao
                
                if agora - ultima_interacao_dt > timedelta(minutes=TIMEOUT_HUMANO_MINUTOS):
                    conversa_ref.set({"status_atendimento": "bot"}, merge=True)
                    logger.info(f"Timeout humano acionado para {phone_number}")
                    return True
        return False
    except Exception as e:
        logger.error(f"Erro ao checar timeout humano: {e}")
        return False

# ---------------------------
# Fluxo do Webhook
# ---------------------------
PROCESSADOS = {}
processados_lock = threading.Lock()
LIMPEZA_INTERVALO = 300  # Limpar cache a cada 5 minutos
ÚLTIMA_LIMPEZA = time.time()

CENTRAL_INSTANCE = os.getenv('EVOLUTION_INSTANCE_NAME')
NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')

def _limpar_cache_processados():
    """Limpa mensagens antigas do cache de deduplicação."""
    global ÚLTIMA_LIMPEZA
    agora_tempo = time.time()
    
    # Executar limpeza apenas a cada LIMPEZA_INTERVALO segundos
    if agora_tempo - ÚLTIMA_LIMPEZA < LIMPEZA_INTERVALO:
        return
    
    with processados_lock:
        antes = len(PROCESSADOS)
        for k in list(PROCESSADOS.keys()):
            if agora_tempo - PROCESSADOS[k] > 3600:  # Manter por 1 hora
                del PROCESSADOS[k]
        depois = len(PROCESSADOS)
        if antes > depois:
            logger.debug(f"Cache limpo: {antes} -> {depois} mensagens")
    
    ÚLTIMA_LIMPEZA = agora_tempo

def handle_onboarding_from_message(phone_number: str, message_text: str, document_message: dict = None, instance_name: str = None):
    """Processa onboarding de uma nova empresa."""
    empresa_id, empresa_doc = get_empresa_by_phone(phone_number)
    agora = datetime.now(timezone.utc)
    
    if empresa_doc is None:
        empresa_id = make_empresa_id_from_phone(phone_number)
        upsert_empresa_from_onboarding(empresa_id, {
            "phone_number": phone_number,
            "status_plano": "pending_onboarding",
            "data_registro": agora
        })
        send_whatsapp(
            phone_number,
            "Olá! Para configurar o seu assistente, envie os dados do negócio (serviços, preços, horário) ou um ficheiro PDF/Excel.",
            instance_name=instance_name
        )
        append_empresa_history(empresa_id, {"event": "onboarding_requested"})
        logger.info(f"Onboarding iniciado para {phone_number}")
        return empresa_id

    if document_message:
        url_doc = document_message.get('url')
        file_name = (document_message.get('fileName') or "").lower()
        
        if not url_doc:
            logger.warning(f"Document message sem URL para {phone_number}")
            return empresa_id
        
        updates = {}
        try:
            if file_name.endswith(('.xlsx', '.xls')):
                updates['servicos_catalogo_excel'] = extrair_texto_excel_url(url_doc)
            elif file_name.endswith('.pdf') or not file_name:
                updates['diretrizes_corporativas'] = extrair_texto_pdf_url(url_doc)
                
            if updates:
                upsert_empresa_from_onboarding(empresa_id, updates)
                send_whatsapp(
                    phone_number,
                    "✅ Dados da empresa atualizados com sucesso!",
                    instance_name=instance_name
                )
                append_empresa_history(empresa_id, {"event": "onboarding_file_uploaded", "file": file_name})
                logger.info(f"Ficheiro {file_name} processado para {phone_number}")
        except Exception as e:
            logger.error(f"Erro ao processar ficheiro de onboarding: {e}")
            send_whatsapp(
                phone_number,
                "❌ Erro ao processar o ficheiro. Tente novamente.",
                instance_name=instance_name
            )
            
    return empresa_id

def _validar_estrutura_mensagem(msg_data: dict) -> bool:
    """Valida se a estrutura da mensagem é válida."""
    try:
        key = msg_data.get('key', {})
        if not key or not isinstance(key, dict):
            return False
        
        message = msg_data.get('message', {})
        if not message or not isinstance(message, dict):
            return False
        
        return True
    except Exception as e:
        logger.warning(f"Erro na validação de estrutura: {e}")
        return False

def _process(data):
    """Processa webhook de mensagem do WhatsApp."""
    try:
        event_name = str(data.get('event', '')).lower()
        if event_name not in ["messages.upsert", "messages_upsert"] or "data" not in data:
            return

        msg_data = data['data']
        
        # CORRIGIDO: Validar estrutura da mensagem
        if not _validar_estrutura_mensagem(msg_data):
            logger.warning("Estrutura de mensagem inválida")
            return
        
        key = msg_data.get('key', {})
        msg_id = key.get('id')
        
        # Desduplicação de mensagens com limpeza periódica
        if msg_id:
            _limpar_cache_processados()
            with processados_lock:
                if msg_id in PROCESSADOS:
                    logger.debug(f"Mensagem duplicada ignorada: {msg_id}")
                    return
                PROCESSADOS[msg_id] = time.time()

        nome_instancia_atual = data.get('instance')
        remote_jid = key.get('remoteJid', '')
        
        # Ignorar mensagens de grupos
        if not remote_jid or '@g.us' in remote_jid:
            return

        # Sanitizar número de telefone
        phone_number = re.sub(r'\D', '', remote_jid.split('@')[0])
        if not phone_number:
            logger.warning("Número de telefone inválido")
            return

        # Ignorar mensagens do próprio bot
        if NUMERO_ASSISTANTE and NUMERO_ASSISTANTE in phone_number:
            logger.debug("Mensagem do próprio bot ignorada")
            return

        message = msg_data.get('message', {})
        audio_message = message.get('audioMessage')
        
        # CORRIGIDO: Validação melhorada de document_message
        document_message = message.get('documentMessage')
        if not document_message:
            doc_with_caption = message.get('documentWithCaptionMessage', {})
            if isinstance(doc_with_caption, dict):
                document_message = doc_with_caption.get('message', {}).get('documentMessage')
        
        # CORRIGIDO: Validação melhorada de image_message
        image_message = message.get('imageMessage')
        if not image_message:
            extended_text = message.get('extendedTextMessage', {})
            if isinstance(extended_text, dict):
                context_info = extended_text.get('contextInfo', {})
                if isinstance(context_info, dict):
                    quoted = context_info.get('quotedMessage', {})
                    if isinstance(quoted, dict):
                        image_message = quoted.get('imageMessage')
        
        message_text = message.get('conversation') or ""
        if not message_text:
            extended_text = message.get('extendedTextMessage', {})
            if isinstance(extended_text, dict):
                message_text = extended_text.get('text', '')

        # Processar Áudio
        if audio_message and isinstance(audio_message, dict):
            audio_url = audio_message.get('url')
            if audio_url:
                send_whatsapp(
                    phone_number,
                    "🎙️ *A ouvir o seu áudio...*",
                    instance_name=nome_instancia_atual
                )
                message_text = transcrever_audio_groq(audio_url)
                if not message_text:
                    logger.warning(f"Falha na transcrição de áudio para {phone_number}")

        # Processar Imagem
        if image_message and isinstance(image_message, dict):
            url_imagem = image_message.get('url')
            caption = image_message.get('caption', '')
            if url_imagem:
                send_whatsapp(
                    phone_number,
                    "👁️ *A analisar a imagem/documento...*",
                    instance_name=nome_instancia_atual
                )
                analise_foto = analisar_imagem_groq(
                    url_imagem,
                    instrucao=caption or "Extraia as informações desta imagem."
                )
                if analise_foto:
                    message_text = f"[CONTEÚDO DA IMAGEM: {analise_foto}]\nTexto do cliente: {caption}"

        if not message_text and not document_message:
            logger.debug("Nenhum conteúdo processável encontrado")
            return

        agora = datetime.now(timezone.utc)
        is_from_me = key.get('fromMe') is True or str(key.get('fromMe')).lower() == 'true'
        db = get_db()

        # Identificação da Empresa
        empresa_id, empresa_doc = get_empresa_by_phone(phone_number)

        # Se for o primeiro contacto, iniciar onboarding
        if empresa_doc is None:
            handle_onboarding_from_message(phone_number, message_text, document_message, instance_name=nome_instancia_atual)
            return

        conversa_ref = db.collection('empresas').document(empresa_id).collection('conversas').document(phone_number)

        # Se a mensagem foi enviada pelo atendente humano via WhatsApp
        if is_from_me:
            conversa_ref.set({
                "status_atendimento": "bot",
                "ultima_mensagem_por": "atendente",
                "ultima_interacao": agora
            }, merge=True)
            save_chat_history(empresa_id, phone_number, role="atendente", text=message_text)
            logger.info(f"Mensagem de atendente processada para {phone_number}")
            return

        # Verificar timeout humano
        checar_timeout_atendimento_humano(empresa_id, phone_number)

        # Se a conversa estiver sob controlo humano, ignorar
        conversa_doc = conversa_ref.get()
        if conversa_doc.exists and conversa_doc.to_dict().get("status_atendimento") == "humano":
            logger.debug(f"Conversa {phone_number} sob controlo humano, ignorada")
            return

        # Buscar Histórico
        contents = get_chat_history(empresa_id, phone_number, limit=10)
        contents.append({"role": "user", "parts": [{"text": message_text}]})

        # Salvar mensagem atual do utilizador
        save_chat_history(empresa_id, phone_number, role="user", text=message_text)

        # Gerar resposta via Groq
        dados_empresa = empresa_doc.to_dict() if empresa_doc else {}
        sys_inst = build_strict_system_instruction(dados_empresa, role_label="assistente virtual")
        response_text = chamar_groq_rest(contents, system_instruction=sys_inst, temperature=0.0)

        if not response_text:
            response_text = "Desculpe, estou a ter dificuldades técnicas de momento. Gostaria de falar com um humano?"

        # Transição para Atendente Humano se solicitado pela IA
        if "[TRANSICAO_HUMANO]" in response_text:
            response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
            conversa_ref.set({
                "status_atendimento": "humano",
                "ultima_interacao": agora
            }, merge=True)
            logger.info(f"Transição para atendente humano: {phone_number}")

        # Enviar Resposta no WhatsApp e salvar no histórico
        send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
        save_chat_history(empresa_id, phone_number, role="assistant", text=response_text)

    except Exception as e:
        logger.error(f"Erro Crítico no Webhook: {e}", exc_info=True)
        notificar_erro_admin(f"Erro no processamento da mensagem: {str(e)}")

def processar_webhook_background(data):
    """Processa webhook em thread background."""
    threading.Thread(target=_process, args=(data,), daemon=True).start()
