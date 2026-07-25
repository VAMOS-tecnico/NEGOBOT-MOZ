import os
import json
import time
import requests
import threading
import re
import random
import io
from flask import Flask, request
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import credentials, firestore
from pypdf import PdfReader

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    return "🚀 Negobot Moz - Servidor Multimodal, Leitor de PDF e Gestor de Campanhas está Online!", 200

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
        print(f"⚠️ [SISTEMA] Falha ao carregar FIREBASE_CONFIG: {e}")
        try:
            firebase_admin.initialize_app()
        except Exception as ex:
            print(f"❌ [SISTEMA] Erro ao inicializar Firebase: {ex}")
else:
    try:
        firebase_admin.initialize_app()
        print("📦 [SISTEMA] Firebase inicializado com configurações padrão.")
    except Exception as e:
        print(f"❌ [SISTEMA] Erro na inicialização padrão do Firebase: {e}")

db = firestore.client()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
MODEL_NAME = 'gemini-2.5-flash'

NUMERO_ASSISTANTE = os.getenv('ASSISTANT_NUMBER')
ADMIN_NUMBER = os.getenv('ADMIN_NUMBER')

# ==========================================
#   🛡️ CONTROLO DE DUPLICADOS DE MENSAGENS
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
            "text": f"⚠️ *[ALERTA CRÍTICO - NEGOBOT]*\n\nFalha no servidor:\n❌ `{erro_msg}`"
        }
        try:
            requests.post(url, headers=headers, json=payload, timeout=10)
        except Exception as e:
            print(f"Falha ao notificar admin: {e}")

# ==========================================
#   📄 MÓDULOS DE EXTRAÇÃO (PDF E IMAGEM)
# ==========================================
def extrair_texto_pdf_url(pdf_url):
    """Descarrega um PDF via URL e extrai todo o texto/tabelas para string"""
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

def descarregar_imagem_bytes(image_url):
    """Descarrega uma imagem da URL e devolve os bytes e o mime_type"""
    try:
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY')}
        response = requests.get(image_url, headers=headers, timeout=20)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', 'image/jpeg')
            return response.content, content_type
    except Exception as e:
        print(f"❌ Erro ao descarregar imagem: {e}")
    return None, None

def send_whatsapp(to, text, instance_name=None):
    if not instance_name:
        instance_name = os.getenv('EVOLUTION_INSTANCE_NAME')
    headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
    
    try:
        requests.post(f"{os.getenv('EVOLUTION_API_URL')}/chat/sendPresence/{instance_name}", headers=headers, json={"number": to, "presence": "composing"}, timeout=5)
        time.sleep(1.5)
        res = requests.post(f"{os.getenv('EVOLUTION_API_URL')}/message/sendText/{instance_name}", headers=headers, json={"number": to, "text": text}, timeout=10)
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"ERRO ao enviar mensagem por {instance_name}: {e}")
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
        return True
    except Exception as e:
        notificar_erro_admin(f"Erro na criação para {phone_number}: {e}")
        return False

def gerar_e_enviar_qrcode_central(phone_number):
    try:
        client_instance = re.sub(r'\D', '', phone_number)
        headers = {"apikey": os.getenv('EVOLUTION_API_KEY'), "Content-Type": "application/json"}
        
        res = requests.get(f"{os.getenv('EVOLUTION_API_URL')}/instance/connect/{client_instance}", headers=headers, timeout=10)
        res.raise_for_status()
        dados = res.json()
        
        if dados.get("instance", {}).get("state") == "open":
            send_whatsapp(phone_number, "✅ O seu assistente virtual já se encontra ativo e operacional!")
            return True
            
        base64_qrcode = dados.get("base64")
        if not base64_qrcode:
            return False

        if "," in base64_qrcode:
            base64_qrcode = base64_qrcode.split(",")[1]

        central_instance = os.getenv('EVOLUTION_INSTANCE_NAME')
        caption_text = (
            "🤖 *Aqui está o seu QR Code do Negobot Moz!* 🚀\n\n"
            "1️⃣ Abra o WhatsApp do atendimento.\n"
            "2️⃣ Vá a *Aparelhos Conectados* -> *Conectar um aparelho*.\n"
            "3️⃣ Escaneie este QR Code."
        )
        payload_media = {
            "number": phone_number,
            "caption": caption_text,
            "media": base64_qrcode,
            "mediatype": "image",
            "fileName": "qrcode.png"
        }
        requests.post(f"{os.getenv('EVOLUTION_API_URL')}/message/sendMedia/{central_instance}", headers=headers, json=payload_media, timeout=15)
        return True
    except Exception as e:
        print(f"Erro QR Code: {e}")
        return False

# ==========================================
#   🚀 SELEÇÃO E EXTRAÇÃO DEDUPLICADA DE GRUPOS
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
            lista_grupos.append({
                "indice": idx,
                "id": g.get("id", ""),
                "nome": g.get("subject", "Grupo sem nome"),
                "qtd": len(g.get("participants", [])),
                "dados_brutos": g
            })
        return lista_grupos
    except Exception as e:
        print(f"Erro listar grupos: {e}")
        return []

def extrair_participantes_de_grupos_especificos(grupos_selecionados):
    telefones_unicos = set()
    for g in grupos_selecionados:
        for p in g.get("dados_brutos", {}).get("participants", []):
            numero = p.get("id", "").split("@")[0]
            numero_limpo = re.sub(r'\D', '', numero)
            if len(numero_limpo) >= 9:
                telefones_unicos.add(numero_limpo)
    return list(telefones_unicos)

def executar_campanha_duas_etapas(instance_name, telefones, mensagem_saudacao):
    contador = 0
    for phone in telefones:
        if send_whatsapp(phone, mensagem_saudacao, instance_name=instance_name):
            contador += 1
            db.collection("clientes_bot").document(instance_name).collection("campanha_leads").document(phone).set({
                "status": "saudacao_enviada",
                "timestamp": firestore.SERVER_TIMESTAMP
            })
        # Intervalo anti-banimento entre envios (25 a 50 segundos)
        time.sleep(random.randint(25, 50))
        # Pausa mais longa a cada 40 mensagens
        if contador > 0 and contador % 40 == 0:
            time.sleep(900)
    send_whatsapp(instance_name, f"✅ *Campanha Concluída!* {contador} mensagens enviadas com sucesso.", instance_name=instance_name)

# ==========================================
#   🎛 WEBHOOK UNIVERSAL MULTIMODAL
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
        if data.get('event', '').lower() != "messages.upsert" or "data" not in data:
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
        message_text = message.get('conversation') or message.get('extendedTextMessage', {}).get('text', '')
        
        # Detetar Ficheiros PDF e Imagens
        document_message = message.get('documentMessage') or message.get('documentWithCaptionMessage', {}).get('message', {}).get('documentMessage')
        image_message = message.get('imageMessage') or message.get('extendedTextMessage', {}).get('contextInfo', {}).get('quotedMessage', {}).get('imageMessage')
        
        if not message_text and image_message:
            message_text = image_message.get('caption', 'Analise o documento presente nesta imagem.')

        agora = datetime.now(timezone.utc)
        is_from_me = key.get('fromMe') is True or str(key.get('fromMe')).lower() == 'true'

        if is_from_me:
            if nome_instancia_atual != central_instance:
                conversa_ref = db.collection('clientes_bot').document(nome_instancia_atual).collection('conversas').document(phone_number)
                conversa_ref.set({"status_atendimento": "bot", "ultima_mensagem_por": "atendente", "ultima_interacao": agora}, merge=True)
                conversa_ref.collection('historico').add({"role": "atendente", "text": message_text, "timestamp": agora})
            return

        # =======================================================
        # 🏢 FLUXO A: INSTÂNCIA CENTRAL (GESTÃO DE CLIENTES)
        # =======================================================
        if nome_instancia_atual == central_instance:
            msg_clean = message_text.lower().strip()
            
            if "recebeu" in msg_clean or "confirmado" in msg_clean:
                db.collection('clientes').document(phone_number).update({"status": "active", "pago": True, "data_ativacao": agora})
                db.collection('clientes_bot').document(phone_number.split('@')[0]).set({"status_plano": "active", "data_ativacao": agora}, merge=True)
                criar_e_configurar_instancia_automatica(phone_number)
                time.sleep(2)
                send_whatsapp(phone_number, "🎉 *Pagamento Confirmado!* O seu Negobot Moz está ativado.", instance_name=central_instance)
                gerar_e_enviar_qrcode_central(phone_number)
                return

            if any(g in msg_clean for g in ["teste", "testar", "quero o bot"]):
                cliente_ref = db.collection('clientes').document(phone_number)
                if not cliente_ref.get().exists:
                    send_whatsapp(phone_number, "⏳ *A preparar o seu Negobot Moz...* Aguarde 10 segundos! 🚀", instance_name=central_instance)
                    if criar_e_configurar_instancia_automatica(phone_number):
                        cliente_ref.set({"phone_number": phone_number, "data_registro": agora, "status": "trial"})
                        tenant_id = re.sub(r'\D', '', phone_number)
                        db.collection('clientes_bot').document(tenant_id).set({
                            "status_plano": "demonstracao",
                            "data_ativacao": agora,
                            "data_expiracao": agora + timedelta(days=2),
                            "diretrizes_corporativas": ""
                        })
                        time.sleep(3)
                        gerar_e_enviar_qrcode_central(phone_number)
                return

            send_whatsapp(phone_number, "Olá! Para testar o robô de vendas por 2 dias grátis, escreva apenas a palavra *TESTAR*.", instance_name=central_instance)

        # =======================================================
        # 🤖 FLUXO B: INSTÂNCIA DO CLIENTE (PROMOTOR DE CRÉDITO)
        # =======================================================
        else:
            client_doc_ref = db.collection('clientes_bot').document(nome_instancia_atual)
            conversa_ref = client_doc_ref.collection('conversas').document(phone_number)
            historico_ref = conversa_ref.collection('historico')

            client_doc = client_doc_ref.get()
            dados_cliente = client_doc.to_dict() if client_doc.exists else {}

            # -------------------------------------------------------------
            # 📄 1. PROCESSADOR DE PDF ENVIADO PELO DONO DO BOT
            # -------------------------------------------------------------
            if document_message and phone_number.split('@')[0] in nome_instancia_atual:
                url_pdf = document_message.get('url')
                send_whatsapp(phone_number, "📄 *PDF Recebido!* A ler e extrair tabelas de simulação de crédito...", instance_name=nome_instancia_atual)
                
                texto_pdf = extrair_texto_pdf_url(url_pdf)
                if texto_pdf:
                    diretrizes_anteriores = dados_cliente.get("diretrizes_corporativas", "")
                    novas_diretrizes = f"{diretrizes_anteriores}\n\n=== TABELA E SIMULADOR DE CRÉDITO (PDF) ===\n{texto_pdf}"
                    
                    client_doc_ref.set({"diretrizes_corporativas": novas_diretrizes}, merge=True)
                    send_whatsapp(phone_number, "✅ *Simulador de Crédito atualizado!* O robô já consegue responder com precisão sobre margens, descontos e prestações.", instance_name=nome_instancia_atual)
                else:
                    send_whatsapp(phone_number, "❌ Não foi possível extrair o texto deste PDF. Certifique-se de que não é um documento digitalizado como imagem.", instance_name=nome_instancia_atual)
                return

            msg_clean = message_text.lower().strip()

            # -------------------------------------------------------------
            # 📋 2. COMANDO /GRUPOS E CAMPANHA DEDUPLICADA
            # -------------------------------------------------------------
            if msg_clean == "/grupos":
                send_whatsapp(phone_number, "🔍 A mapear os teus grupos de WhatsApp...", instance_name=nome_instancia_atual)
                grupos = listar_grupos_instancia(nome_instancia_atual)
                if not grupos:
                    send_whatsapp(phone_number, "❌ Nenhum grupo encontrado.", instance_name=nome_instancia_atual)
                    return

                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").set({"grupos": grupos})
                texto_resposta = "📋 *SELECIONA OS GRUPOS PARA EXTRAIR* 🎯\n\n"
                for g in grupos:
                    texto_resposta += f"*{g['indice']}* - {g['nome']} _({g['qtd']} membros)_\n"
                texto_resposta += "\n✍️ Responde com os números separados por vírgula (ex: `1, 3`)."
                send_whatsapp(phone_number, texto_resposta, instance_name=nome_instancia_atual)
                return

            doc_mapeamento = db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").get()
            if doc_mapeamento.exists and re.match(r'^[\d\s,]+$', msg_clean):
                lista_grupos_mapeados = doc_mapeamento.to_dict().get("grupos", [])
                indices_escolhidos = [int(i.strip()) for i in msg_clean.split(",") if i.strip().isdigit()]
                grupos_filtrados = [g for g in lista_grupos_mapeados if g["indice"] in indices_escolhidos]
                
                telefones_extraidos = extrair_participantes_de_grupos_especificos(grupos_filtrados)
                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").set({"telefones": telefones_extraidos})
                db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_grupos").document("mapeamento").delete()
                
                send_whatsapp(phone_number, f"✅ Extraídos *{len(telefones_extraidos)}* contactos únicos (sem duplicados).\n\nDesejas iniciar a campanha? Responde com: *SIM*", instance_name=nome_instancia_atual)
                return

            if msg_clean == "sim":
                temp_ref = db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").get()
                if temp_ref.exists:
                    telefones = temp_ref.to_dict().get("telefones", [])
                    send_whatsapp(phone_number, f"🚀 A iniciar campanha para {len(telefones)} contactos em segundo plano.", instance_name=nome_instancia_atual)
                    threading.Thread(target=executar_campanha_duas_etapas, args=(nome_instancia_atual, telefones, "Bom dia! Tudo bem?")).start()
                    db.collection("clientes_bot").document(nome_instancia_atual).collection("temp_listas").document("dados").delete()
                    return

            # -------------------------------------------------------------
            # 👁️ 3. ATENDIMENTO MULTIMODAL (TEXTO + VISÃO + TABELA PDF)
            # -------------------------------------------------------------
            docs_historico = historico_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
            lista_mensagens = [d.to_dict() for d in docs_historico]
            lista_mensagens.reverse()

            contents = []
            for m in lista_mensagens:
                role_gemini = "model" if m.get('role') in ["assistant", "model", "atendente"] else "user"
                contents.append(types.Content(role=role_gemini, parts=[types.Part.from_text(text=m.get('text', ''))]))

            partes_mensagem = []
            
            # Análise de Imagem (BI, Recibo de Salário, etc.)
            if image_message:
                url_imagem = image_message.get('url')
                send_whatsapp(phone_number, "👁️ *A analisar o documento/imagem...*", instance_name=nome_instancia_atual)
                img_bytes, mime_type = descarregar_imagem_bytes(url_imagem)
                if img_bytes:
                    partes_mensagem.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))

            partes_mensagem.append(types.Part.from_text(text=message_text if message_text else "Analise o documento enviado na imagem."))
            contents.append(types.Content(role="user", parts=partes_mensagem))

            tabelas_simulacao = dados_cliente.get("diretrizes_corporativas", "Promotor de crédito para funcionários públicos e professores.")

            sys_instruction = f"""Você é o Negobot Moz, especialista em análise documental, crédito consignado e simulações para funcionários públicos e professores em Moçambique.

🎯 SUAS CAPACIDADES VISUAIS E DE ANÁLISE:
1. **Fotografias de BI / NUIT:** Verifique a validade, extraia o Nome Completo e o Número de BI para prosseguir com o processo.
2. **Recibos de Vencimento / Holerites:** Identifique o Salário Líquido, Salário Base e os Descontos já existentes em folha.
3. **Simulações em Imagem ou PDF:** Consulte as tabelas abaixo para responder sobre prestações mensais, margem consignável e taxas.

📋 TABELA DE CRÉDITO E REGRAS DE SIMULAÇÃO CARREGADAS (PDF):
{tabelas_simulacao}

🚨 REGRAS CRÍTICAS DE RESPOSTA:
- Responda em tom profissional, atencioso e direto (máximo de 3 a 4 linhas).
- Se a imagem enviada estiver desfocada ou cortada, peça educadamente uma nova fotografia com boa iluminação.
- Nunca invente dados que não estejam presentes na imagem ou nas tabelas do PDF."""

            config = types.GenerateContentConfig(system_instruction=sys_instruction, temperature=0.2)
            response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
            response_text = response.text if response.text else ""

            if response_text:
                send_whatsapp(phone_number, response_text, instance_name=nome_instancia_atual)
                historico_ref.add({"role": "user", "text": message_text if message_text else "[Imagem Enviada]", "timestamp": agora})
                historico_ref.add({"role": "model", "text": response_text, "timestamp": agora})

    except Exception as e:
        print(f"❌ Erro no webhook: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
