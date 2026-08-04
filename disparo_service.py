import os
import re
import time
import random
import logging
import requests
from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from firebase_admin import firestore
from dotenv import load_dotenv

# Importa as extensões da aplicação (instância do Firebase/Firestore)
import extensions

# ------------------------------------------------------------------------------
# CARREGAMENTO DE VARIÁVEIS DE AMBIENTE (.env)
# ------------------------------------------------------------------------------
load_dotenv()

# ------------------------------------------------------------------------------
# CONFIGURAÇÃO DE LOGS E APLICAÇÃO
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("disparo_service")

app = FastAPI(
    title="Negobot Moz - Módulo Unificado & Anti-Bloqueio de Disparos",
    description="Gestão de disparos em massa com proteção contra banimento da Meta.",
    version="2026.2"
)

# ------------------------------------------------------------------------------
# VARIÁVEIS DE AMBIENTE E SEGURANÇA INTEGRADAS
# ------------------------------------------------------------------------------
# Captura SERVER_URL ou EVOLUTION_API_URL do .env
EVOLUTION_API_URL = os.getenv("SERVER_URL", os.getenv("EVOLUTION_API_URL", "https://evolution.62.238.52.209.sslip.io")).rstrip("/")

# Captura a AUTHENTICATION_API_KEY definida no seu .env do Evolution API
API_KEY = os.getenv("AUTHENTICATION_API_KEY", os.getenv("EVOLUTION_API_KEY", "41AF721F-8171-4B9A-9C5F-F6D684FAF556"))

# Processa e sanitiza a lista de telefones de administradores
RAW_ADMIN_PHONES = os.getenv("ADMIN_PHONES", "")
ADMIN_PHONES = [re.sub(r'\D', '', p) for p in RAW_ADMIN_PHONES.split(",") if re.sub(r'\D', '', p)]

# Parâmetros Padrão Anti-Bloqueio
DELAY_MIN_SEGUNDOS = 7      # Tempo mínimo entre envios (segundos)
DELAY_MAX_SEGUNDOS = 15     # Tempo máximo entre envios (segundos)
LOTE_TAMANHO = 12           # A cada X mensagens, faz uma pausa longa
PAUSA_LOTE_MIN = 60         # Pausa longa mínima em segundos (1 minuto)
PAUSA_LOTE_MAX = 120        # Pausa longa máxima em segundos (2 minutos)

# ------------------------------------------------------------------------------
# MODELOS DE DADOS (PYDANTIC)
# ------------------------------------------------------------------------------
class DisparoRequest(BaseModel):
    instance_name: str = "assistente_negobot"
    numeros: List[str]
    mensagem: str
    delay_segundos: Optional[int] = 7

class AdminTextoRequest(BaseModel):
    admin_phone: str
    message_text: str
    instance_name: Optional[str] = "assistente_negobot"

class ClienteDisparoTextoRequest(BaseModel):
    tenant_id: str
    client_phone: str
    message_text: str

# ------------------------------------------------------------------------------
# FUNÇÃO ANTI-BAN 1: PROCESSADOR DE SPINTAX
# ------------------------------------------------------------------------------
def processar_spintax(texto: str) -> str:
    """
    Converte variações de texto no formato {Opção 1|Opção 2|Opção 3}.
    Exemplo: "{Olá|Oi|Tudo bem}, {como vai|como está}?"
    Gera combinações totalmente aleatórias para evitar padrão de mensagem idêntica.
    """
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(texto)
        if not match:
            break
        opcoes = match.group(1).split('|')
        texto = texto[:match.start()] + random.choice(opcoes) + texto[match.end():]
    return texto

# ------------------------------------------------------------------------------
# CORE DE ENVIO COM DIGITAÇÃO SIMULADA E LOGS
# ------------------------------------------------------------------------------
def enviar_mensagem_unica(instance_name: str, number: str, text: str) -> bool:
    """Envia uma única mensagem simulando tempo de digitação variável humano."""
    endpoint = f"{EVOLUTION_API_URL}/message/sendText/{instance_name}"
    headers = {
        "apikey": API_KEY,
        "Content-Type": "application/json"
    }
    
    # Gera um tempo de digitação humano aleatório entre 1.5s e 4.5s
    tempo_digitacao_ms = random.randint(1500, 4500)
    
    payload = {
        "number": number,
        "text": text,
        "delay": tempo_digitacao_ms,
        "linkPreview": False
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=12)
        if response.status_code in [200, 201]:
            return True
        else:
            logger.error(f"❌ Erro Evolution API ({response.status_code}) para {number}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Exceção na conexão com a Evolution API para {number}: {e}")
        return False

# ------------------------------------------------------------------------------
# ENGINE DE DISPARO PROTEGIDO (LOOP ANTI-BLOQUEIO)
# ------------------------------------------------------------------------------
def processar_disparo_em_massa(instance_name: str, numeros: List[str], mensagem_base: str, delay_base: int = 7):
    """
    Executa o disparo com proteção multicamada em segundo plano:
    - Variação por Spintax
    - Delays variáveis (Jitter)
    - Descanso por lotes
    """
    sucessos = 0
    falhas = 0
    total = len(numeros)

    logger.info(f"🛡️ [DISPARO PROTEGIDO INICIADO] Instância: {instance_name} | Total: {total} contactos")

    for index, numero in enumerate(numeros, start=1):
        numero_limpo = re.sub(r'\D', '', str(numero))

        if not numero_limpo or len(numero_limpo) < 8:
            logger.warning(f"[{index}/{total}] ⚠️ Número inválido ignorado: {numero}")
            falhas += 1
            continue

        # 1. Aplica Spintax para gerar mensagem única por destinatário
        mensagem_variada = processar_spintax(mensagem_base)

        # 2. Executa envio
        sucesso = enviar_mensagem_unica(instance_name, numero_limpo, mensagem_variada)

        if sucesso:
            sucessos += 1
            logger.info(f"[{index}/{total}] ✅ Enviado para: {numero_limpo}")
        else:
            falhas += 1
            logger.warning(f"[{index}/{total}] ❌ Falha no envio para: {numero_limpo}")

        # Se for o último envio, encerra o loop sem pausas adicionais
        if index == total:
            break

        # 3. Pausa de descanso por LOTE (A cada X mensagens)
        if index % LOTE_TAMANHO == 0:
            tempo_pausa_lote = random.uniform(PAUSA_LOTE_MIN, PAUSA_LOTE_MAX)
            logger.info(f"☕ Pausa de segurança por lote ({LOTE_TAMANHO} msgs). A aguardar {int(tempo_pausa_lote)} segundos...")
            time.sleep(tempo_pausa_lote)
        else:
            # 4. Pausa aleatória entre mensagens individuais (Jitter)
            delay_calculado = random.uniform(max(5, delay_base), max(5, delay_base) + (DELAY_MAX_SEGUNDOS - DELAY_MIN_SEGUNDOS))
            logger.debug(f"Aguardando {delay_calculado:.2f}s até o próximo envio...")
            time.sleep(delay_calculado)

    logger.info(f"🏁 [DISPARO PROTEGIDO CONCLUÍDO] Sucessos: {sucessos} | Falhas: {falhas} | Total: {total}")

# ------------------------------------------------------------------------------
# PROCESSADOR DE REGRAS SAAS (#disparo)
# ------------------------------------------------------------------------------
def processar_disparo_cliente_saas(tenant_id: str, client_phone: str, message_text: str, background_tasks: BackgroundTasks) -> str:
    """Valida permissões do plano SaaS no Firestore e inicia a fila de disparo protegido."""
    try:
        client_doc_ref = extensions.db.collection('clientes_bot').document(tenant_id)
        client_doc = client_doc_ref.get()
    except Exception as e:
        logger.error(f"Erro de acesso ao Firestore (extensions.db): {e}")
        return "❌ *Erro interno:* Falha de conexão com a base de dados."

    if not client_doc.exists:
        return "❌ *Conta não encontrada.* Registe a sua empresa na plataforma."

    dados_cliente = client_doc.to_dict() or {}
    status_plano = dados_cliente.get("status_plano", "demonstracao")

    # Trava de Plano
    if status_plano not in ["premium", "demonstracao", "ativo"]:
        return (
            "❌ *Recurso Indisponível:* O envio de *Disparos em Massa* é exclusivo do *Plano Premium*.\n\n"
            "Atualize a sua conta para ativar esta funcionalidade com proteção anti-bloqueio."
        )

    # Trava de Teste Grátis
    if status_plano == "demonstracao":
        disparos_usados = dados_cliente.get("disparos_teste_usados", 0)
        if disparos_usados >= 2:
            return (
                "⚠️ *Limite de Teste Atingido:* No plano de teste grátis são permitidos até *2 disparos em massa*.\n\n"
                "Para disparos contínuos e sem restrições, assine o *Plano Premium*."
            )

    # Validação do formato
    conteudo = message_text.replace("#disparo", "").replace("#broadcast", "").strip()
    if "|" not in conteudo:
        return (
            "❌ *Formato incorreto!* Para disparos protegidos use:\n\n"
            "`#disparo 258841234567,258859876543 | {Olá|Oi}! Veja a nossa promoção de hoje!`\n\n"
            "💡 *Dica Anti-Bloqueio:* Use `{Opção1|Opção2}` para variar o texto automaticamente!"
        )

    partes = conteudo.split("|", 1)
    numeros_raw = partes[0].split(",")
    mensagem_envio = partes[1].strip()

    numeros_filtrados = [re.sub(r'\D', '', n) for n in numeros_raw if re.sub(r'\D', '', n)]

    if not numeros_filtrados:
        return "❌ *Nenhum número válido foi encontrado.*"

    if not mensagem_envio:
        return "❌ *A mensagem não pode estar vazia.*"

    # Atualiza contador no plano de demonstração
    if status_plano == "demonstracao":
        client_doc_ref.set({"disparos_teste_usados": firestore.Increment(1)}, merge=True)

    # Inicia processo assíncrono em segundo plano
    background_tasks.add_task(
        processar_disparo_em_massa,
        instance_name=tenant_id,
        numeros=numeros_filtrados,
        mensagem_base=mensagem_envio,
        delay_base=8
    )

    return (
        f"🛡️ *Disparo Protegido Iniciado!*\n\n"
        f"• *Destinatários:* {len(numeros_filtrados)}\n"
        f"• *Proteção Anti-Bloqueio:* Ativa (Intervalos dinâmicos e variação de texto)\n"
        f"• *Instância:* `{tenant_id}`\n\n"
        f"O processo está a ser executado em segundo plano com segurança."
    )

# ------------------------------------------------------------------------------
# LÓGICA DE COMANDOS DE ADMINISTRADOR
# ------------------------------------------------------------------------------
def processar_mensagem_admin(admin_phone: str, text_message: str, instance_name: str, background_tasks: BackgroundTasks) -> Optional[str]:
    clean_admin = re.sub(r'\D', '', str(admin_phone))

    if clean_admin not in ADMIN_PHONES:
        logger.warning(f"Tentativa de acesso não autorizada: {clean_admin}. Admins válidos: {ADMIN_PHONES}")
        return None

    msg_clean = text_message.strip()

    if msg_clean.startswith("#disparo") or msg_clean.startswith("#broadcast"):
        try:
            conteudo = msg_clean.replace("#disparo", "").replace("#broadcast", "").strip()

            if "|" not in conteudo:
                return "❌ *Formato Admin incorreto!* Use:\n`#disparo num1,num2 | {Olá|Oi} Sua Mensagem`"

            partes = conteudo.split("|", 1)
            lista_numeros_raw = partes[0].split(",")
            mensagem_envio = partes[1].strip()

            numeros_filtrados = [re.sub(r'\D', '', n) for n in lista_numeros_raw if re.sub(r'\D', '', n)]

            if not numeros_filtrados or not mensagem_envio:
                return "❌ *Parâmetros inválidos (números ou mensagem ausentes).*"

            background_tasks.add_task(
                processar_disparo_em_massa,
                instance_name=instance_name,
                numeros=numeros_filtrados,
                mensagem_base=mensagem_envio,
                delay_base=8
            )

            return f"📢 *[ADMIN] Disparo Protegido Iniciado!*\n• Total: {len(numeros_filtrados)} destinatários\n• Instância: {instance_name}"

        except Exception as e:
            return f"⚠️ *Erro no comando admin:* {str(e)}"

    if msg_clean == "#ajuda_disparo":
        return (
            "🛠️ *Painel Admin - Disparos Protegidos*\n\n"
            "• `#disparo num1,num2 | {Olá|Oi} Sua Mensagem`\n"
            "• `#ajuda_disparo`"
        )

    return None

# ------------------------------------------------------------------------------
# ROTAS HTTP (API REST FASTAPI)
# ------------------------------------------------------------------------------
@app.get("/")
def health_check():
    return {
        "status": "online",
        "modulo": "Disparo em Massa Protegido - Negobot Moz",
        "evolution_url": EVOLUTION_API_URL,
        "versao": "2026.2"
    }

@app.post("/api/v1/disparo-em-massa")
def disparar_mensagens_json(dados: DisparoRequest, background_tasks: BackgroundTasks):
    if not dados.numeros or not dados.mensagem.strip():
        raise HTTPException(status_code=400, detail="Dados de disparo inválidos.")

    background_tasks.add_task(
        processar_disparo_em_massa,
        instance_name=dados.instance_name,
        numeros=dados.numeros,
        mensagem_base=dados.mensagem,
        delay_base=dados.delay_segundos
    )

    return {
        "status": "sucesso",
        "mensagem": "Disparo protegido iniciado em segundo plano!",
        "total_destinatarios": len(dados.numeros),
        "instancia": dados.instance_name
    }

@app.post("/api/v1/disparo-cliente-saas")
def disparar_comando_cliente(dados: ClienteDisparoTextoRequest, background_tasks: BackgroundTasks):
    resposta = processar_disparo_cliente_saas(
        tenant_id=dados.tenant_id,
        client_phone=dados.client_phone,
        message_text=dados.message_text,
        background_tasks=background_tasks
    )
    return {"status": "processado", "resposta_chat": resposta}

@app.post("/api/v1/disparo-admin-texto")
def disparar_mensagens_texto_admin(dados: AdminTextoRequest, background_tasks: BackgroundTasks):
    resposta = processar_mensagem_admin(
        admin_phone=dados.admin_phone,
        text_message=dados.message_text,
        instance_name=dados.instance_name,
        background_tasks=background_tasks
    )

    if resposta:
        return {"executado": True, "resposta_admin": resposta}

    return {"executado": False, "mensagem": "Comando não autorizado ou inválido."}
