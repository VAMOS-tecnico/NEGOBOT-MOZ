import os
import json
import time
import requests
import threading
import re
import random
import io
import urllib.parse
from flask import Flask, request
from datetime import datetime, timedelta, timezone

# Manipulação de Documentos e Tabelas (PDF e Excel)
from pypdf import PdfReader
import pandas as pd

# Google GenAI SDK e Firebase
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Negobot 100% Automático com Suporte Humano, Multimodalidade e Campanhas está online! 🚀", 200

# ==========================================
#   📦 INICIALIZAÇÃO SEGURA DO FIREBASE E GEMINI
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
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# CORREÇÃO CRÍTICA: O modelo oficial e estável da Google para a API
MODEL_NAME = 'gemini-3.1-flash-lite'

NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')
ADMIN_NUMBER = os.getenv('ADMIN_NUMBER')

# ==========================================
#   🛡️ CONTROLO DE DUPLICADOS (ANTI-DUPLICAÇÃO)
# ==========================================
PROCESSADOS = {}
processados_lock = threading.Lock()

# ==========================================
#   📢 FUNÇÃO DE NOTIFICAÇÃO DE ERROS CRÍTICOS
# ==========================================
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
#   📄 MÓDULOS DE EXTRAÇÃO (PDF, EXCEL E IMAGEM)
# ==========================================
def extrair_texto_pdf_url(pdf_url):
    """Descarrega um PDF via URL e extrai todo o texto para string"""
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
    """Descarrega uma folha de cálculo Excel (.xlsx / .xls) via URL e extrai as tabelas para texto"""
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

def descarregar_imagem_bytes(image_url):
    """Descarrega uma imagem da URL da Evolution API e devolve os bytes e mime_type"""
    try:
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY')}
        response = requests.get(image_url, headers=headers, timeout=20)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', 'image/jpeg')
            return response.content, content_type
    except Exception as e:
        print(f"❌ Erro ao descarregar imagem: {e}")
    return None, None

def criar_prompt_profissional_gemini(pedido_utilizador):
    """O Gemini constrói um prompt publicitário profissional em inglês"""
    try:
        sys_instruction = (
            "Você é um especialista em Engenharia de Prompts para geração de imagens publicitárias. "
            "Converta o pedido do utilizador num prompt altamente detalhado em INGLÊS. "
            "Adicione detalhes de qualidade visual, iluminação e contexto corporativo moçambicano como: "
            "'professional marketing banner, microfinance Mozambique context, bright clean lighting, "
            "corporate style, photorealistic, 8k resolution, clean focal point'. "
            "Responda APENAS com o prompt em inglês, sem saudações ou textos adicionais."
        )
        config = types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.7)
        response = client.models.generate_content(
            model=MODEL_NAME, 
            contents=pedido_utilizador, 
            config=config
        )
        return response.text.strip() if response.text else pedido_utilizador
    except Exception as e:
        print(f"❌ Erro ao otimizar prompt no Gemini: {e}")
        return pedido_utilizador

def gerar_url_imagem_pollinations(prompt_otimizado):
    """Gera o URL da imagem usando o modelo FLUX da Pollinations"""
    prompt_encoded = urllib.parse.quote(prompt_otimizado)
    return f"https://pollinations.ai/p/{prompt_encoded}?width=1024&height=1024&model=flux&seed=42"

# ==========================================
#   ⏱️ TEMPORIZADOR DE ESPERA HUMANA (4 MINUTOS)
# ==========================================
def verificar_espera_humano_isolado(instancia_cliente, numero_remetente):
    print(f"⏱️ [TEMPORIZADOR] Iniciada monitorização de 4 minutos para {numero_remetente} na instância {instancia_cliente}")
    time.sleep(240)
    
    try:
        conversa_ref = db.collection('clientes_bot').document(instancia_cliente).collection('conversas').document(numero_remetente)
        doc = conversa_ref.get()
        
        if doc.exists:
            dados = doc.to_dict()
            status_atendimento = dados.get("status_atendimento")
            ultima_mensagem_por = dados.get("ultima_mensagem_por")
            
            if status_atendimento == "humano" and ultima_mensagem_por == "cliente_final":
                msg_aviso = (
                    "🕒 AVISO DE ATENDIMENTO ⚠️\n\n"
                    "Pedimos desculpas pela demora. O nosso assistente está ocupado no momento com outros atendimentos, "
                    "mas assim que estiver disponível vai responder diretamente aqui. Obrigado pela paciência!"
                )
                send_whatsapp(numero_remetente, msg_aviso, instance_name=instancia_cliente)
                print(f"📢 [TEMPORIZADOR] Alerta de espera de 4 minutos enviado para {numero_remetente}")
    except Exception as e:
        print(f"❌ [ERRO TEMPORIZADOR] Falha na verificação de estouro de tempo: {e}")

# ==========================================
#   🤖 FUNÇÃO DE INFRAESTRUTURA AUTOMÁTICA
# ==========================================
def criar_e_configurar_instancia_automatica(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        print(f"🔄 [AUTOMAÇÃO] Limpando sessões antigas para a instância {client_instance}...")
        requests.delete(f"{os.getenv('EVOLUTION_API_URL')}/instance/logout/{client_instance}", headers=headers, timeout=5)
        requests.delete(f"{os.getenv('EVOLUTION_API_URL')}/instance/delete/{client_instance}", headers=headers, timeout=5)
        time.sleep(2)
        
        url_create = f"{os.getenv('EVOLUTION_API_URL')}/instance/create"
        payload_create = {
            "instanceName": client_instance,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        res_create = requests.post(url_create, headers=headers, json=payload_create, timeout=10)
        res_create.raise_for_status()
        print(f"📦 [AUTOMAÇÃO] Nova instância {client_instance} criada com sucesso.")
        return True
    except Exception as e:
        erro_msg = f"Erro ao automatizar criação para {phone_number}: {e}"
        print(f"❌ {erro_msg}")
        notificar_erro_admin(erro_msg)
        return False

# ==========================================
#   📦 HISTÓRICO DE COMPATIBILIDADE (FLUXO A)
# ==========================================
def get_chat_history(phone_number):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('history', [])
    except Exception as e:
        print(f"Erro ao obter histórico do painel central: {e}")
    return []

def save_chat_history(phone_number, history):
    try:
        doc_ref = db.collection('chats').document(phone_number)
        doc_ref.set({"history": history}, merge=True)
    except Exception as e:
        print(f"Erro ao salvar histórico do painel central: {e}")

# ==========================================
#   📞 COMUNICAÇÃO DE SAÍDA COM "A ESCREVER..." REAL
# ==========================================
def send_whatsapp(to, text, instance_name=None):
    if not instance_name:
        instance_name = os.getenv('EVOLUTION_INSTANCE_NAME')
        
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    
    try:
        url_presence = f"{os.getenv('EVOLUTION_API_URL')}/chat/sendPresence/{instance_name}"
        payload_presence = {"number": to, "presence": "composing"}
        requests.post(url_presence, headers=headers, json=payload_presence, timeout=5)
        
        time.sleep(1.5)
        
        url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{instance_name}"
        payload = {"number": to, "text": text}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"ERRO ao enviar mensagem pela instância {instance_name}: {e}")
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
            "⚠️ *ATENÇÃO:* Este código expira rápido por motivos de segurança do WhatsApp.\n\n"
            "1️⃣ Abra o WhatsApp que vai atender os seus clientes.\n"
            "2️⃣ Vá a *Aparelhos Conectados* -> *Conectar um aparelho*.\n"
            "3️⃣ Aponte a câmara e escaneie *imediatamente* este QR Code.\n\n"
            "Se o tempo esgotar, basta enviar o comando *#qrcode* aqui para gerar um novo! 🎉"
        )
        
        payload_media = {
            "number": phone_number,
            "caption": caption_text,
            "media": base64_qrcode,
            "mediatype": "image",
            "fileName": "qrcode.png"
        }
        res_media = requests.post(url_send_media, headers=headers, json=payload_media, timeout=15)
        res_media.raise_for_status()
        return True
    except Exception as e:
        print(f"Erro ao gerar/enviar QR Code: {e}")
        return False

# ==========================================
#   🚀 MÓDULO DE SELEÇÃO E EXTRAÇÃO DE GRUPOS
# ==========================================
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
            gid = g.get("id", "")
            nome = g.get("subject", "Grupo sem nome")
            participantes_qtd = len(g.get("participants", []))
            
            lista_grupos.append({
                "indice": idx,
                "id": gid,
                "nome": nome,
                "qtd": participantes_qtd,
                "dados_brutos": g
            })
            
        return lista_grupos
    except Exception as e:
        print(f"Erro ao listar grupos para {instance_name}: {e}")
        return []

def extrair_participantes_de_grupos_especificos(grupos_selecionados):
    telefones_unicos = set()
    
    for g in grupos_selecionados:
        participantes = g.get("dados_brutos", {}).get("participants", [])
        for p in participantes:
            jid = p.get("id", "")
            numero = jid.split("@")[0]
            numero_limpo = re.sub(r'\D', '', numero)
            if len(numero_limpo) >= 9:
                telefones_unicos.add(numero_limpo)
                
    return list(telefones_unicos)

def executar_campanha_duas_etapas(instance_name, telefones, mensagem_saudacao):
    print(f"🚀 [CAMPANHA] A iniciar disparo em duas etapas para a instância: {instance_name}")
    contador = 0
    
    for phone in telefones:
        sucesso = send_whatsapp(phone, mensagem_saudacao, instance_name=instance_name)
        
        if sucesso:
            contador += 1
            db.collection("clientes_bot").document(instance_name).collection("campanha_leads").document(phone).set({
                "status": "saudacao_enviada",
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            print(f"📤 [ENVIO {contador}] Saudação enviada para {phone}")
        
        pausa = random.randint(25, 50)
        time.sleep(pausa)
        
        if contador > 0 and contador % 40 == 0:
            print("🛑 [ANTISPAM] Lote de 40 mensagens atingido. Pausa de segurança de 15 minutos ativada...")
            time.sleep(900)
            
    print(f"✅ [CAMPANHA] Concluída! {contador} mensagens de abordagem enviadas na instância {instance_name}.")
    send_whatsapp(instance_name, f"✅ *Campanha Concluída!* {contador} mensagens de abordagem foram enviadas com sucesso e em segurança.", instance_name=instance_name)

# ==========================================
#       📢 ROTINA AUTOMÁTICA DE LEMBRETES
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
            "**envie-nos aqui um documento em PDF ou folha Excel com todas as informações, catálogos e regras da sua empresa.**"
        )
        
        contador = 0
        for doc in clientes_ref:
            dados = doc.to_dict()
            phone_number = dados.get('phone_number')
            if phone_number:
                send_whatsapp(phone_number, mensagem_lembrete, instance_name=central_instance)
                contador += 1
                time.sleep(1.5)
                
        print(f"✅ [ROTINA] Lembretes concluídos. Total enviado: {contador}")
    except Exception as e:
        erro_msg = f"Erro na rotina de lembretes em massa: {e}"
        print(f"❌ {erro_msg}")
        notificar_erro_admin(erro_msg)

@app.route('/cron/lembretes', methods=['GET'])
def disparar_lembretes_via_url():
    periodo = request.args.get('periodo', 'manhã')
    threading.Thread(target=enviar_lembretes_em_massa, args=(periodo,)).start()
    return f"A rotina automatizada de lembretes da {periodo} foi disparada em segundo plano!", 200

# ==========================================
#   🎛 CONVERTOR DE WEBHOOKS
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

# ==========================================
#   🧠 MOTOR DE PROCESSAMENTO ASSÍNCRONO
# ==========================================
def processar_webhook_background(data):
    try:
        event_name = data.get('event', '').lower()
        if event_name != "messages.upsert" or "data" not in data:
            return

        msg_data = data['data']
        key = msg_data.get('key', {})
        
        msg_id = key.get('id')
        if msg_id:
            with processados_lock:
                agora_tempo = time.time()
                antigos = [k for k, v in PROCESSADOS.items() if agora_tempo - v > 60]
                for k in antigos:
                    del PROCESSADOS[k]
                
                if msg_id in PROCESSADOS:
                    print(f"⚠️ [DEDUPLICAÇÃO] Ignorando webhook duplicado: {msg_id}")
                    return
                PROCESSADOS[msg_id] = agora_tempo

        nome_instancia_atual = data.get('instance')
        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        if not nome_instancia_atual:
            return

        phone_number = key.get('remoteJid', '')
        if not phone_number or '@g.us' in phone_number:
            return
            
        if NUMERO_ASSISTANTE and NUMERO_ASSISTANTE in phone_number:
            return

        message = msg_data.get('message', {})
        message_text = message.get('conversation') or message.get('extendedTextMessage', {}).get('text', '')
        
        # Leitura de Anexos: Documentos e Imagens
        document_message = message.get('documentMessage') or message.get('documentWithCaptionMessage', {}).get('message', {}).get('documentMessage')
        image_message = message.get('imageMessage') or message.get('extendedTextMessage', {}).get('contextInfo', {}).get('quotedMessage', {}).get('imageMessage')

        if not message_text and image_message:
            message_text = image_message.get('caption', 'Analise o documento presente nesta imagem.')

        if not message_text and not document_message and not image_message:
            return

        msg_clean = message_text.lower().strip()
        agora = datetime.now(timezone.utc)

        from_me = key.get('fromMe')
        is_from_me = from_me is True or str(from_me).lower() == 'true'

        if is_from_me:
            if nome_instancia_atual != central_instance:
                conversa_ref = db.collection('clientes_bot').document(nome_instancia_atual).collection('conversas').document(phone_number)
                conversa_ref.set({
                    "status_atendimento": "bot",
                    "ultima_mensagem_por": "atendente",
                    "ultima_interacao": agora
                }, merge=True)
                
                conversa_ref.collection('historico').add({
                    "role": "atendente",
                    "text": message_text,
                    "timestamp": agora
                })
            return

        # =======================================================
        # 🏢 FLUXO A: MENSAGEM RECEBIDA PELA INSTÂNCIA CENTRAL
        # =======================================================
        if nome_instancia_atual == central_instance:
            
            if msg_clean.startswith('#status'):
                remetente_puro = phone_number.split('@')[0]
                if ADMIN_NUMBER and remetente_puro in ADMIN_NUMBER:
                    partes = message_text.split()
                    if len(partes) > 1:
                        numero_pesquisa = partes[1].strip()
                        jid_pesquisa = numero_pesquisa if "@" in numero_pesquisa else f"{numero_pesquisa}@s.whatsapp.net"
                            
                        doc_cliente = db.collection('clientes').document(jid_pesquisa).get()
                        if doc_cliente.exists:
                            c_dados = doc_cliente.to_dict()
                            c_status = c_dados.get('status', 'trial')
                            c_pago = c_dados.get('pago', False)
                            c_reg = c_dados.get('data_registro')
                            reg_formatado = c_reg.strftime('%d/%m/%Y às %H:%M') if c_reg else "N/A"
                            
                            resposta_status = (
                                f"📊 *DASHBOARD CENTRAL - NEGOBOT MOZ*\n\n"
                                f"• *Cliente:* {numero_pesquisa}\n"
                                f"• *Estado:* {c_status.upper()}\n"
                                f"• *Pago:* {'Sim ✅' if c_pago else 'Não ❌'}\n"
                                f"• *Registro:* {reg_formatado}"
                            )
                        else:
                            resposta_status = f"❌ *Erro:* O número `{numero_pesquisa}` não consta no Firebase."
                    else:
                        resposta_status = "💡 *Instrução de Uso:* Envie exatamente: `#status 25884xxxxxxx`"
                else:
                    resposta_status = "⛔ *Acesso Negado:* Comando restrito ao administrador."
                    
                send_whatsapp(phone_number, resposta_status, instance_name=central_instance)
                return

            if "recebeu" in msg_clean or "confirmado" in msg_clean or "transacao" in msg_clean:
                db.collection('clientes').document(phone_number).update({
                    "status": "active",
                    "pago": True,
                    "data_ativacao": agora
                })
                db.collection('clientes_bot').document(phone_number.split('@')[0]).set({
                    "status_plano": "active",
                    "data_ativacao": agora
                }, merge=True)
                
                criar_e_configurar_instancia_automatica(phone_number)
                time.sleep(2)
                send_whatsapp(phone_number, "🎉 *Pagamento Confirmado!* O seu Negobot Moz foi atualizado com sucesso para o modo ilimitado.", instance_name=central_instance)
                gerar_e_enviar_qrcode_central(phone_number)
                return
            
            gatilhos_teste = ["teste", "testar", "quero o bot", "começar", "criar bot"]
            if any(g in msg_clean for g in gatilhos_teste):
                cliente_ref = db.collection('clientes').document(phone_number)
                doc = cliente_ref.get()
                
                if not doc.exists or doc.to_dict().get('status') == 'prospect':
                    send_whatsapp(phone_number, "⏳ *Excelente! A preparar o seu ambiente do Negobot Moz para os 2 dias de teste gratuito...* Demora menos de 10 segundos! 🚀", instance_name=central_instance)
                    
                    sucesso_infra = criar_e_configurar_instancia_automatica(phone_number)
                    if sucesso_infra:
                        dados_cliente = {
                            "phone_number": phone_number,
                            "data_registro": agora,
                            "trial_start": agora,
                            "status": "trial",
                            "diretrizes_corporativas": "Atenda o cliente de forma séria e focado estritamente nos serviços comerciais e planos da empresa."
                        }
                        cliente_ref.set(dados_cliente)
                        
                        tenant_id = re.sub(r'\D', '', phone_number)
                        db.collection('clientes_bot').document(tenant_id).set({
                            "status_plano": "demonstracao",
                            "data_ativacao": agora,
                            "data_expiracao": agora + timedelta(days=2),
                            "diretrizes_corporativas": "Atenda o cliente de forma séria e focado estritamente nos serviços comerciais e planos da empresa."
                        })
                        time.sleep(3)
                        gerar_e_enviar_qrcode_central(phone_number)
                else:
                    status_atual = doc.to_dict().get('status', 'trial')
                    if status_atual == 'bloqueado':
                        send_whatsapp(phone_number, "⚠️ O seu período de teste de 2 dias terminou. Efetue o pagamento via M-Pesa (855000929) e envie o SMS de confirmação aqui.", instance_name=central_instance)
                    elif status_atual == 'active':
                        send_whatsapp(phone_number, "✅ O seu plano está Ativo! Se precisar de reconectar, digite *#qrcode*.", instance_name=central_instance)
                    elif status_atual == 'trial':
                        send_whatsapp(phone_number, "✅ O seu teste de 2 dias já está a decorrer! Se precisar do QR Code novamente, digite *#qrcode*.", instance_name=central_instance)
                return

            if msg_clean == "#qrcode":
                send_whatsapp(phone_number, "🔄 A gerar o seu QR Code de reconexão...", instance_name=central_instance)
                criar_e_configurar_instancia_automatica(phone_number)
                time.sleep(2)
                gerar_e_enviar_qrcode_central(phone_number)
                return

            raw_history = get_chat_history(phone_number)
            recent_history = raw_history[-10:]
            
            contents = []
            for msg in recent_history:
                role = "model" if msg.get('role') in ["assistant", "model", "atendente"] else "user"
                if msg.get('parts'):
                    parts = [types.Part.from_text(text=p.get('text', '')) for p in msg.get('parts', []) if isinstance(p, dict)]
                elif msg.get('text'):
                    parts = [types.Part.from_text(text=msg.get('text'))]
                else:
                    continue
                if parts:
                    contents.append(types.Content(role=role, parts=parts))
            
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message_text)]))

            sys_instruction_central = """Você é o assistente comercial oficial do Negobot Moz. Seu objetivo é sanar dúvidas sobre os planos e direcionar o cliente para testar a ferramenta. 
            
⚠️ REGRA CRÍTICA: Sempre que o cliente demonstrar interesse em iniciar, testar, ou obter o robô dele, oriente-o estritamente a digitar apenas a palavra-chave 'TESTAR' para que o sistema automatizado envie o QR Code dele. Não invente links de ativação.
Norma de comunicação: Português padrão de Moçambique, tom sério e corporativo.
Planos: Inicial (500 MT) e Avançado (1000 MT). Teste gratuito de 2 dias disponível.

📋 DADOS INSTITUCIONAIS GERAIS (NEGOBOT CENTRAL):
1. CRIADOR: Desenvolvido pelo empresário Abel Francisco, licenciado em Contabilidade e Auditoria.
2. PLANOS DISPONÍVEIS:
   - Plano Inicial (500 MT/mês): Atendimento automático para perguntas frequentes por texto manual, limite de 1.500 mensagens/mês, sem suporte humano.
   - Plano Avançado (1000 MT/mês): Mensagens ilimitadas, leitura de catálogos complexos via PDF e suporte humano integrado.
3. MÉTODO DE COBRANÇA: Pagamentos via M-Pesa pelo número 855000929 em nome de Abel Francisco."""

            config = types.GenerateContentConfig(system_instruction=sys_instruction_central, temperature=0.3)
            response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
            response_text = response.text if response.text else ""
            
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))
            save_chat_history(phone_number, [{"role": c.role, "parts": [{"text": p.text} for p in c.parts]} for c in contents[-10:]])
            send_whatsapp(phone_number, response_text, instance_name=central_instance)

        # =======================================================
        # 🤖 FLUXO B: MENSAGEM RECEBIDA PELA INSTÂNCIA DO CLIENTE
        # =======================================================
        else:
            client_doc_ref = db.collection('clientes_bot').document(nome_instancia_atual)
            conversa_ref = client_doc_ref.collection('conversas').document(phone_number)
            historico_ref = conversa_ref.collection('historico')

            client_doc = client_doc_ref.get()
            
            default_rules = (
                "És o assistente virtual oficial do promotor de vendas de crédito, super agente e embaixador da Thembane Digital em Manica. "
                "O teu objetivo é atender solicitantes de crédito, recolher documentos (como fotos do BI e dados de identificação) "
                "e orientar o cliente sobre simulações e pedidos de financiamento.\n\n"
                "Regras de Ouro:\n"
                "1. Se o cliente enviar fotos de documentos (BI) ou solicitar crédito, responda confirmando a recepção de imediato e peça os detalhes do valor pretendido.\n"
                "2. Nunca pergunte genericamente 'como posso ajudar nos negócios' quando o assunto for crédito ou envio de identificação.\n"
                "3. Comunicação estritamente profissional, culta e polida em português de Moçambique."
            )

            if not client_doc.exists:
                dados_cliente = {
                    "status_plano": "demonstracao",
                    "data_ativacao": agora,
                    "data_expiracao": agora + timedelta(days=2),
                    "diretrizes_corporativas": default_rules
                }
                client_doc_ref.set(dados_cliente)
            else:
                dados_cliente = client_doc.to_dict()

            status_plano = dados_cliente.get("status_plano", "demonstracao")
            data_expiracao = dados_cliente.get("data_expiracao")
            
            if data_expiracao and data_expiracao.tzinfo is None:
                data_expiracao = data_expiracao.replace(tzinfo=timezone.utc)

            if status_plano == "demonstracao" and agora > data_expiracao:
                print(f"⛔ [PAYWALL] Instância {nome_instancia_atual} com período experimental expirado.")
                msg_bloqueio = (
                    "⚠️ AVISO DE ATENDIMENTO ⚠️\n\n"
                    "Olá! O período de teste gratuito de 2 dias deste assistente virtual chegou ao fim. "
                    "Para continuar a interagir e ter acesso aos nossos serviços, por favor contacte o suporte comercial da empresa."
                )
                send_whatsapp(phone_number, msg_bloqueio, instance_name=nome_instancia_atual)
                return

            # -------------------------------------------------------------
            # 🎨 1. COMANDO /CRIAR-ARTE (GERAÇÃO DE IMAGENS P/ CAMPANHAS)
            # -------------------------------------------------------------
            if msg_clean.startswith("/criar-arte"):
                pedido = message_text.replace("/criar-arte", "").strip()
                if not pedido:
                    send_whatsapp(phone_number, "✍️ *Como usar:* Escreva a descrição após o comando.\nExemplo: `/criar-arte Banner publicitário de crédito rápido para professores em Chimoio`", instance_name=nome_instancia_atual)
                    return

                send_whatsapp(phone_number, "🎨 *O Gemini está a projetar e a desenhar a sua arte...* Aguarde uns segundos! 🚀", instance_name=nome_instancia_atual)
                
                prompt_ingles = criar_prompt_profissional_gemini(pedido)
                link_imagem = gerar_url_imagem_pollinations(prompt_ingles)
                
                headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
                payload = {
                    "number": phone_number,
                    "caption": f"✨ *Arte Gerada com Sucesso!*\n\n🎯 *Tema:* _{pedido}_",
                    "media": link_imagem,
                    "mediatype": "image",
                    "fileName": "campanha_negobot.jpg"
                }
                url = f"{os.getenv('EVOLUTION_API_URL')}/message/sendMedia/{nome_instancia_atual}"
                try:
                    requests.post(url, headers=headers, json=payload, timeout=25)
                except Exception as e:
                    print(f"❌ Erro ao enviar imagem gerada: {e}")
                return

            # -------------------------------------------------------------
            # 📄 2. PROCESSAMENTO DE DOCUMENTOS (PDF E EXCEL) ENVIADOS PELO DONO
            # -------------------------------------------------------------
            if document_message and phone_number.split('@')[0] in nome_instancia_atual:
                url_doc = document_message.get('url')
                file_name = document_message.get('fileName', '').lower()

                if file_name.endswith('.xlsx') or file_name.endswith('.xls'):
                    send_whatsapp(phone_number, "📊 *Excel Recebido!* A ler e extrair abas e tabelas...", instance_name=nome_instancia_atual)
                    texto_excel = extrair_texto_excel_url(url_doc)
                    if texto_excel:
                        diretrizes_anteriores = dados_cliente.get("diretrizes_corporativas", "")
                        novas_diretrizes = f"{diretrizes_anteriores}\n\n=== TABELA E SIMULADOR DE CRÉDITO (EXCEL) ===\n{texto_excel}"
                        
                        client_doc_ref.set({"diretrizes_corporativas": novas_diretrizes}, merge=True)
                        send_whatsapp(phone_number, "✅ *Tabelas em Excel integradas com sucesso!* O robô já consegue realizar simulações com base nestes dados.", instance_name=nome_instancia_atual)
                    else:
                        send_whatsapp(phone_number, "❌ Erro ao ler a folha de cálculo Excel. Verifique a estrutura do ficheiro.", instance_name=nome_instancia_atual)
                    return

                elif file_name.endswith('.pdf') or not file_name:
                    send_whatsapp(phone_number, "📄 *PDF Recebido!* A ler e extrair tabelas de simulação de crédito...", instance_name=nome_instancia_atual)
                    texto_pdf = extrair_texto_pdf_url(url_doc)
                    if texto_pdf:
                        diretrizes_anteriores = dados_cliente.get("diretrizes_corporativas", "")
                        novas_diretrizes = f"{diretrizes_anteriores}\n\n=== TABELA E SIMULADOR DE CRÉDITO (PDF) ===\n{texto_pdf}"
                        
                        client_doc_ref.set({"diretrizes_corporativas": novas_diretrizes}, merge=True)
                        send_whatsapp(phone_number, "✅ *Simulador de Crédito atualizado!* O robô já consegue responder com precisão sobre margens e prestações.", instance_name=nome_instancia_atual)
                    else:
                        send_whatsapp(phone_number, "❌ Não foi possível extrair o texto deste PDF. Certifique-se de que não é um documento digitalizado como imagem.", instance_name=nome_instancia_atual)
                    return

            # -------------------------------------------------------------
            # 🚀 3. COMANDOS DE SELEÇÃO E EXTRAÇÃO DE GRUPOS
            # -------------------------------------------------------------
            if msg_clean == "/grupos":
                send_whatsapp(phone_number, "🔍 A mapear os teus grupos de WhatsApp...", instance_name=nome_instancia_atual)
                grupos = listar_grupos_instancia(nome_instancia_atual)
                
                if not grupos:
                    send_whatsapp(phone_number, "❌ Não encontrei nenhum grupo ativo nesta conta.", instance_name=nome_instancia_atual)
                    return

                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").set({
                    "grupos": grupos,
                    "timestamp": firestore.SERVER_TIMESTAMP
                })

                texto_resposta = "📋 *SELECIONA OS GRUPOS PARA EXTRAIR* 🎯\n\n"
                for g in grupos:
                    texto_resposta += f"*{g['indice']}* - {g['nome']} _({g['qtd']} membros)_\n"
                    
                texto_resposta += "\n✍️ *Como escolher:* Responde aqui apenas com os números dos grupos separados por vírgula.\nExemplo: `1, 3` ou `2, 4, 5`"
                
                send_whatsapp(phone_number, texto_resposta, instance_name=nome_instancia_atual)
                return

            doc_mapeamento = db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").get()

            if doc_mapeamento.exists and re.match(r'^[\d\s,]+$', msg_clean):
                dados_temp = doc_mapeamento.to_dict()
                lista_grupos_mapeados = dados_temp.get("grupos", [])
                
                indices_escolhidos = [int(i.strip()) for i in msg_clean.split(",") if i.strip().isdigit()]
                grupos_filtrados = [g for g in lista_grupos_mapeados if g["indice"] in indices_escolhidos]
                
                if not grupos_filtrados:
                    send_whatsapp(phone_number, "⚠️ Nenhum número válido foi selecionado. Tenta novamente enviando ex: `1, 3`", instance_name=nome_instancia_atual)
                    return
                    
                telefones_extraidos = extrair_participantes_de_grupos_especificos(grupos_filtrados)
                
                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").set({
                    "telefones": telefones_extraidos,
                    "total": len(telefones_extraidos)
                })
                
                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").delete()
                
                nomes_grupos = ", ".join([f"*{g['nome']}*" for g in grupos_filtrados])
                send_whatsapp(
                    phone_number,
                    f"✅ Extração concluída!\n\n"
                    f"• **Grupos Selecionados:** {nomes_grupos}\n"
                    f"• **Contactos Únicos Encontrados:** *{len(telefones_extraidos)}*\n\n"
                    f"Desejas iniciar a campanha de abordagem automática para estes contactos?\nResponde com: *SIM*",
                    instance_name=nome_instancia_atual
                )
                return

            if msg_clean == "sim":
                temp_ref = db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").get()
                if temp_ref.exists:
                    info_lista = temp_ref.to_dict()
                    telefones = info_lista.get("telefones", [])
                    
                    if telefones:
                        send_whatsapp(phone_number, f"🚀 Perfeito! A campanha com {len(telefones)} contactos foi enquadrada e vai começar a ser disparada de forma segura em segundo plano.", instance_name=nome_instancia_atual)
                        
                        mensagem_saudacao = "Bom dia! Tudo bem?"
                        
                        threading.Thread(
                            target=executar_campanha_duas_etapas,
                            args=(nome_instancia_atual, telefones, mensagem_saudacao)
                        ).start()
                        
                        db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").delete()
                    else:
                        send_whatsapp(phone_number, "⚠️ Nenhuma lista encontrada. Envia o comando `/grupos` primeiro.", instance_name=nome_instancia_atual)
                    return
                else:
                    lead_ref = db.collection("clientes_bot").document(nome_instancia_atual).collection("campanha_leads").document(phone_number).get()
                    if lead_ref.exists:
                        lead_data = lead_ref.to_dict()
                        if lead_data.get("status") == "saudacao_enviada":
                            time.sleep(2)
                            resposta_venda = "Que bom ouvir isso! Caso precise de apoio financeiro, crédito rápido ou oportunidades para o seu negócio, diga-me como o posso ajudar!"
                            send_whatsapp(phone_number, resposta_venda, instance_name=nome_instancia_atual)
                            db.collection("clientes_bot").document(nome_instancia_atual).collection("campanha_leads").document(phone_number).update({"status": "convertido_em_conversa"})
                            return

            conversa_doc = conversa_ref.get()
            status_atendimento = "bot"
            if conversa_doc.exists:
                status_atendimento = conversa_doc.to_dict().get("status_atendimento", "bot")

            if status_atendimento == "humano":
                conversa_ref.set({"ultima_mensagem_por": "cliente_final", "ultima_interacao": agora}, merge=True)
                historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                threading.Thread(target=verificar_espera_humano_isolado, args=(nome_instancia_atual, phone_number)).start()
                return

            gatilhos_humano = ["falar com atendente", "suporte humano", "atendente", "falar com humano", "#suporte", "humano", "suporte"]
            if any(g in msg_clean for g in gatilhos_humano):
                conversa_ref.set({
                    "status_atendimento": "humano",
                    "ultima_mensagem_por": "cliente_final",
                    "ultima_interacao": agora
                }, merge=True)
                historico_ref.add({"role": "user", "text": message_text, "timestamp": agora})
                
                resposta_suporte = (
                    "🔔 *Pedido de Suporte Humano recebido!*\n\n"
                    "Vou chamar um dos nossos especialistas para dar continuidade ao seu atendimento. "
                    "Por favor, aguarde um momento que a equipa já o vai contactar aqui! 🤝"
                )
                send_whatsapp(phone_number, resposta_suporte, instance_name=nome_instancia_atual)
                threading.Thread(target=verificar_espera_humano_isolado, args=(nome_instancia_atual, phone_number)).start()
                return

            docs_historico = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
            
            lista_mensagens = []
            for d in docs_historico:
                lista_mensagens.append(d.to_dict())
            lista_mensagens.reverse()

            contents = []
            for m in lista_mensagens:
                role_bruto = m.get('role')
                role_gemini = "model" if role_bruto in ["assistant", "model", "atendente"] else "user"
                contents.append(types.Content(
                    role=role_gemini,
                    parts=[types.Part.from_text(text=m.get('text', ''))]
                ))
            
            partes_mensagem = []
            
            # -------------------------------------------------------------
            # 👁️ 4. ATENDIMENTO MULTIMODAL (ANÁLISE DE FOTOS DE BI / RECIBO)
            # -------------------------------------------------------------
            if image_message:
                url_imagem = image_message.get('url')
                send_whatsapp(phone_number, "👁️ *A analisar o documento/imagem...*", instance_name=nome_instancia_atual)
                img_bytes, mime_type = descarregar_imagem_bytes(url_imagem)
                if img_bytes:
                    partes_mensagem.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))

            partes_mensagem.append(types.Part.from_text(text=message_text if message_text else "Analise o documento presente nesta imagem."))
            contents.append(types.Content(role="user", parts=partes_mensagem))

            diretrizes_corporativas = dados_cliente.get("diretrizes_corporativas", "").strip()
            if not diretrizes_corporativas:
                diretrizes_corporativas = default_rules
            
            sys_instruction = f"""Você é um assistente comercial virtual altamente inteligente, profissional e estritamente focado em fechar negócios. Sua comunicação deve ser feita exclusivamente na norma padrão e culta da Língua Portuguesa (Língua Oficial de Moçambique), mantendo um tom sério, polido, claro e corporativo.

🎯 SUAS CAPACIDADES VISUAIS E DE ANÁLISE DE DOCUMENTOS:
1. **Fotografias de BI / NUIT:** Verifique a validade, extraia o Nome Completo e o Número de BI para prosseguir com a simulação de crédito.
2. **Recibos de Vencimento / Holerites:** Identifique o Salário Líquido, Salário Base e os Descontos em folha de pagamento.
3. **Simulações em Imagem, PDF ou Excel:** Consulte as tabelas integradas abaixo para responder sobre prestações, taxas e margens.

🚨 REGRAS CRÍTICAS DE COMPORTAMENTO HUMANO:
1. É EXPRESSAMENTE PROIBIDO utilizar terminologias tecnológicas, tais como: "Como uma inteligência artificial", "diretrizes de automação", "protocolos do sistema", "sou um modelo de linguagem" ou "sou um robô". Responda estritamente como um membro humano da equipa comercial.
2. Limite de Saída: Desenvolva mensagens curtas, ágeis e diretas ao ponto (máximo 2 a 3 linhas por bloco de resposta).
3. Tratamento de Repetições: Se o utilizador reclamar de repetição de falas, peça desculpas de forma simples e natural, alterando a abordagem de vendas imediatamente.
4. Assunto Restrito: Bloqueie qualquer assunto alheio ao escopo comercial da empresa. Proibido uso de dialetos locais ou gírias informais.

📋 INFORMAÇÕES ESPECÍFICAS DA EMPRESA E TABELAS CARREGADAS (PDF / EXCEL):
{diretrizes_corporativas}

📌 REGRA DE TRANSIÇÃO: Se o cliente voltar a insistir em falar com o suporte, pedir por um atendente humano, gerente, ou se a dúvida dele fugir completamente da base de conhecimento fornecida acima, confirme o encaminhamento de forma polida e termine a resposta adicionando EXATAMENTE a tag: [TRANSICAO_HUMANO]"""

            config = types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.2)
            response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
            response_text = response.text if response.text else ""
            
            historico_ref.add({"role": "user", "text": message_text if message_text else "[Imagem/Documento Enviado]", "timestamp": agora})

            if "[TRANSICAO_HUMANO]" in response_text:
                response_text = response_text.replace("[TRANSICAO_HUMANO]", "").strip()
                
                conversa_ref.set({
                    "status_atendimento": "humano",
                    "ultima_mensagem_por": "cliente_final",
                    "ultima_interacao": agora
                }, merge=True)
                
                if response_text:
                    send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
                else:
                    send_whatsapp(phone_number, "Entendido. Estou a transferir o seu atendimento para a nossa equipa de suporte humano agora mesmo. Por favor, aguarde.", instance_name=nome_instancia_atual)
                    
                historico_ref.add({
                    "role": "model",
                    "text": response_text if response_text else "Encaminhado para o suporte humano.",
                    "timestamp": agora
                })
                
                threading.Thread(target=verificar_espera_humano_isolado, args=(nome_instancia_atual, phone_number)).start()
                return

            if response_text:
                send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
                historico_ref.add({"role": "model", "text": response_text, "timestamp": agora})
                conversa_ref.set({"ultima_mensagem_por": "bot", "ultima_interacao": agora}, merge=True)

    except Exception as e:
        erro_completo = f"Erro na rota Webhook Universal (Instância: {data.get('instance')}): {e}"
        print(f"❌ {erro_completo}")
        notificar_erro_admin(erro_completo)

# ==========================================
#       ⏰ SINCRO DE LOOP INTERNO (CRON)
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
                if agora.hour == 9 and agora.minute == 30:
                    enviar_lembretes_em_massa("manhã")
                    ultima_execucao_chave = chave_atual
                elif agora.hour == 17 and agora.minute == 0:
                    enviar_lembretes_em_massa("tarde")
                    ultima_execucao_chave = chave_atual
                    
        except Exception as e:
            print(f"❌ Erro no loop secundário de lembretes: {e}")
            
        time.sleep(30)

# Inicializa o monitor de lembretes no escopo global para compatibilidade total com WSGI/Gunicorn
def iniciar_servicos_background():
    threading.Thread(target=loop_interno_lembretes, daemon=True).start()

iniciar_servicos_background()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
