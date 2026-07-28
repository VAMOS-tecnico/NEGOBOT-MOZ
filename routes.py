import os
import time
import re
import threading
import requests
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request
from firebase_admin import firestore
from config import db, NUMERO_ASSISTANTE, TIMEOUT_HUMANO_MINUTOS, PROCESSADOS, processados_lock
from utils import (
    chamar_groq_rest, transcrever_audio_groq, analisar_imagem_groq,
    extrair_texto_pdf_url, extrair_texto_excel_url,
    criar_prompt_profissional_groq, gerar_url_imagem_pollinations
)
from services import (
    send_whatsapp, criar_e_configurar_instancia_automatica,
    gerar_e_enviar_qrcode_central, checar_timeout_atendimento_humano,
    get_chat_history, save_chat_history, notificar_erro_admin
)

api_blueprint = Blueprint('api', __name__)

@api_blueprint.route('/', methods=['GET'])
def health_check():
    return "O ecossistema Negobot 100% Automático está online! 🚀", 200

@api_blueprint.route('/webhook-global', methods=['POST'])
@api_blueprint.route('/webhook-cliente', methods=['POST'])
@api_blueprint.route('/webhook', methods=['POST'])
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
