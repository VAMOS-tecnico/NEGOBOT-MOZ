import logging
import re
from datetime import datetime, timedelta, timezone
import extensions

logger = logging.getLogger(__name__)

# Número oficial de recebimento M-Pesa (Negobot Moz)
NUMERO_RECEBEDOR_OFICIAL = "855000929"

# Catálogo central de planos: mantém IDs e preços compatíveis com pagamentos existentes.
from services.plan_service import TABELA_PLANOS


def identificar_plano_por_valor(valor_pago):
    """Mapeia o valor transferido via M-Pesa para o plano correspondente."""
    valores_ordenados = sorted(TABELA_PLANOS.keys(), reverse=True)
    for val_minimo in valores_ordenados:
        if valor_pago >= val_minimo:
            return TABELA_PLANOS[val_minimo]
    return None


def validar_e_ativar_extra_mpesa(tenant_id, client_phone, message_text, addon_id):
    """Valida um extra mensal via AutoPay sem alterar o plano base do tenant."""
    from services.plan_service import ADDONS

    addon = ADDONS.get(str(addon_id or "").strip().lower())
    if not addon:
        return "Extra não encontrado."
    tx_id = extrair_codigo_mpesa(message_text)
    if not tx_id:
        return "Código M-Pesa não identificado. Cole o SMS completo ou o ID da transacção."
    dados_sms = extrair_dados_sms_cliente_transferiste(message_text)
    if dados_sms and NUMERO_RECEBEDOR_OFICIAL not in dados_sms.get("destino_telefone", ""):
        return "A transferência não foi feita para o número oficial 855000929."
    pagamento_ref, dados_pago = _buscar_registo_autopay(tx_id)
    if pagamento_ref is None or dados_pago is None:
        return f"A aguardar confirmação do AutoPay para a transacção {tx_id}. Aguarde 30 segundos e tente novamente."
    if dados_pago.get("status") not in {"pago", "paid", "confirmado", "confirmed"}:
        return f"O AutoPay ainda não confirmou a transacção {tx_id}."
    if dados_pago.get("usado") is True:
        return f"A transacção M-Pesa {tx_id} já foi utilizada."
    sender_phone = re.sub(r"\D", "", str(dados_pago.get("remetente_telefone") or ""))
    requested_phone = re.sub(r"\D", "", str(client_phone or ""))
    if sender_phone and requested_phone and sender_phone[-9:] != requested_phone[-9:]:
        return "O número do pagador não coincide com o número indicado."
    amount = float(dados_pago.get("valor", 0))
    if amount < float(addon["price_mt"]):
        return f"Valor insuficiente: o extra {addon['name']} requer pelo menos {addon['price_mt']:.0f} MT."
    now = datetime.now(timezone.utc)
    pagamento_ref.set({"usado": True, "usado_por_tenant": tenant_id, "usado_por_extra": addon_id, "data_ativacao": now}, merge=True)
    extensions.db.collection("tenants").document(tenant_id).collection("addons").document(addon_id).set({
        "addon_id": addon_id,
        "name": addon["name"],
        "status": "active",
        "provider": "mpesa_autopay",
        "transaction_id": tx_id,
        "amount_mt": amount,
        "activated_at": now,
        "updated_at": now,
    }, merge=True)
    return f"Extra {addon['name']} activado com sucesso através do M-Pesa AutoPay."


def extrair_dados_sms_cliente_transferiste(sms_texto):
    """Extrai os dados da mensagem 'Transferiste...' colada pelo cliente no WhatsApp."""
    if not sms_texto or not isinstance(sms_texto, str):
        return None

    # Aceita 'as' ou 'às' com/sem acento
    padrao = (
        r"Confirmado\s+(?P<tx_id>[A-Z0-9]+)\.\s*"
        r"Transferiste\s+(?P<valor>[\d,.]+)\s*MT.*?\s+para\s+"
        r"(?P<destino>\d+)\s*-\s*"
        r"(?P<nome_destino>.*?)\s+aos\s+"
        r"(?P<data_hora>\d{1,2}/\d{1,2}/\d{2,4}\s+[aà]s\s+\d{1,2}:\d{2}(?:\s*[AP]M)?)"
    )

    match = re.search(padrao, sms_texto, re.IGNORECASE)
    if match:
        dados = match.groupdict()
        valor_raw = dados['valor']
        
        # Tratamento seguro de decimais e milhar
        if ',' in valor_raw and '.' in valor_raw:
            valor_clean = valor_raw.replace(',', '')
        elif ',' in valor_raw:
            valor_clean = valor_raw.replace(',', '.')
        else:
            valor_clean = valor_raw

        try:
            valor_float = float(valor_clean)
        except ValueError:
            valor_float = 0.0

        return {
            "transaction_id": dados['tx_id'].upper(),
            "valor": valor_float,
            "destino_telefone": re.sub(r'^\+?258', '', dados['destino']),
            "destino_nome": dados['nome_destino'].strip(),
            "data_transacao": dados['data_hora'].strip()
        }
    return None


def extrair_codigo_mpesa(texto):
    """Extrai o ID da transação M-Pesa garantindo que não confunda palavras em maiúsculas."""
    texto = (texto or "").strip().upper()

    dados_envio = extrair_dados_sms_cliente_transferiste(texto)
    if dados_envio:
        return dados_envio["transaction_id"]

    # Exige combinação de Letras e Números (Evita palavras como OBRIGADO, PROBLEMA, etc.)
    match = re.search(r'\b(?=.*[0-9])(?=.*[A-Z])[A-Z0-9]{8,12}\b', texto)
    if match:
        return match.group(0)

    return None


def _valor_autopay(raw_value):
    text = str(raw_value or "").strip().replace(" MT", "").replace("MT", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _buscar_registo_autopay(tx_id):
    """Lê o contrato real do AutoPay e normaliza-o para o motor de planos."""
    if not extensions.db:
        return None, None
    candidates = [("transacoes_sucesso", "id"), ("pagamentos_mpesa", "transaction_id")]
    for collection_name, id_field in candidates:
        direct_ref = extensions.db.collection(collection_name).document(tx_id)
        direct_doc = direct_ref.get()
        if direct_doc.exists:
            data = direct_doc.to_dict() or {}
            return direct_ref, {
                "transaction_id": str(data.get("id") or data.get("transaction_id") or direct_doc.id).upper(),
                "valor": _valor_autopay(data.get("amount", data.get("valor"))),
                "remetente_nome": data.get("sender_name", data.get("remetente_nome", "Cliente")),
                "remetente_telefone": data.get("sender_phone", data.get("remetente_telefone", "")),
                "status": str(data.get("status", "pago")).lower(),
                "usado": bool(data.get("usado", False)),
                "source_collection": collection_name,
                "raw": data,
            }
        matches = extensions.db.collection(collection_name).where(id_field, "==", tx_id).limit(1).get()
        if matches:
            matched_doc = matches[0]
            data = matched_doc.to_dict() or {}
            return matched_doc.reference, {
                "transaction_id": str(data.get("id") or data.get("transaction_id") or tx_id).upper(),
                "valor": _valor_autopay(data.get("amount", data.get("valor"))),
                "remetente_nome": data.get("sender_name", data.get("remetente_nome", "Cliente")),
                "remetente_telefone": data.get("sender_phone", data.get("remetente_telefone", "")),
                "status": str(data.get("status", "pago")).lower(),
                "usado": bool(data.get("usado", False)),
                "source_collection": collection_name,
                "raw": data,
            }
    return None, None


def validar_e_ativar_pagamento_mpesa(tenant_id, client_phone, message_text):
    """
    Valida a transação M-Pesa capturada pelo Auto Pay e ativa a conta no plano correspondente.
    """
    try:
        agora = datetime.now(timezone.utc)

        # 1. Extrair ID M-Pesa
        tx_id = extrair_codigo_mpesa(message_text)

        if not tx_id:
            return (
                "⚠️ *Código M-Pesa Não Identificado!*\n\n"
                "Não conseguimos ler o código do seu pagamento.\n"
                "Por favor, envie o **Código da Transação** (Ex: `DGU1L0KF9I3`) ou cole o SMS completo do M-Pesa."
            )

        # 2. Verificar destinatário (caso o cliente tenha colado o SMS completo)
        dados_sms_cliente = extrair_dados_sms_cliente_transferiste(message_text)
        if dados_sms_cliente:
            num_destino = dados_sms_cliente.get("destino_telefone", "")
            if NUMERO_RECEBEDOR_OFICIAL not in num_destino:
                return (
                    f"⚠️ *Número Destino Incorreto!*\n\n"
                    f"A transferência foi realizada para `{num_destino}`.\n"
                    f"Os pagamentos do Negobot Moz devem ser feitos para o número **855000929** (Abel Francisco)."
                )

        # 3. Buscar no Firestore o registo real inserido pelo AutoPay Android.
        pagamento_ref, dados_pago = _buscar_registo_autopay(tx_id)
        if pagamento_ref is None or dados_pago is None:
            return (
                f"⌛ *A aguardar confirmação do sistema...* (`{tx_id}`)\n\n"
                "O seu pagamento ainda não foi sincronizado pelo AutoPay.\n"
                "Por favor, aguarde **30 segundos** e envie novamente o código M-Pesa."
            )

        if dados_pago.get("source_collection") == "transacoes_sucesso" and dados_pago.get("status") not in {"pago", "paid", "confirmado", "confirmed"}:
            return (
                f"⌛ *A aguardar confirmação do sistema...* (`{tx_id}`)\n\n"
                "O AutoPay ainda não marcou esta transação como paga."
            )

        # 4. Anti-fraude: impede reaproveitamento do comprovativo.
        if dados_pago.get('usado') is True:
            return (
                f"⚠️ *Código Já Utilizado!*\n\n"
                f"A transação M-Pesa `{tx_id}` já foi resgatada anteriormente."
            )

        # 5. Confirmar que o comprovativo pertence ao número que pede a ativação.
        sender_phone = re.sub(r"\D", "", str(dados_pago.get("remetente_telefone") or ""))
        requested_phone = re.sub(r"\D", "", str(client_phone or ""))
        if sender_phone and requested_phone and sender_phone[-9:] != requested_phone[-9:]:
            return (
                "⚠️ *Número do pagador não coincide.*\n\n"
                "O AutoPay recebeu a transferência de outro número. Entra com o número que efetuou o pagamento ou contacta o administrador."
            )

        # 6. Mapear valor pago para o plano correto
        valor_pago = float(dados_pago.get('valor', 0))
        plano = identificar_plano_por_valor(valor_pago)

        if not plano:
            return (
                f"⚠️ *Valor Insuficiente!*\n\n"
                f"Recebemos o código `{tx_id}` no valor de *{valor_pago:.2f} MT*.\n"
                f"O plano mínimo (*Plano Básico*) custa *500.00 MT*.\n"
                "Por favor, complete o valor restante para ativar a sua licença."
            )

        # 6. Cálculo inteligente de validade (preserva dias em caso de renovação antecipada)
        dias_validade = plano["dias_validade"]
        tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
        tenant_doc = tenant_ref.get()
        tenant_dados = tenant_doc.to_dict() if tenant_doc.exists else {}

        data_expiracao_atual = tenant_dados.get('data_expiracao')
        if data_expiracao_atual:
            if data_expiracao_atual.tzinfo is None:
                data_expiracao_atual = data_expiracao_atual.replace(tzinfo=timezone.utc)
            
            # Se ainda não expirou, acumula os 30 dias na data de expiração existente
            base_calculo = max(agora, data_expiracao_atual)
        else:
            base_calculo = agora

        data_expiracao = base_calculo + timedelta(days=dias_validade)
        nome_pagador = dados_pago.get('remetente_nome', 'Cliente')

        # 7. ATIVAÇÃO E ATUALIZAÇÃO NO FIRESTORE
        pagamento_ref.set({
            "usado": True,
            "usado_por_tenant": tenant_id,
            "usado_por_telefone": client_phone,
            "data_ativacao": agora
        }, merge=True)

        tenant_ref.set({
            "plano": plano["id"],
            "nome_plano": plano["nome"],
            "status_plano": "ativo",
            "disparo_liberado": plano["disparo_liberado"],
            "limite_conversas": plano["limite_conversas"],
            "data_ativacao": agora,
            "data_expiracao": data_expiracao,
            "ultimo_tx_id": tx_id,
            "metodo_pagamento": "M-Pesa AutoPay",
            "plan_rules_version": "2026-08-v2",
        }, merge=True)

        logger.info(f"✅ Conta {tenant_id} ativada no {plano['nome']} via M-Pesa {tx_id}")

        recurso_disparo_str = "✅ *Disparos em Massa Liberados!*" if plano["disparo_liberado"] else "ℹ️ *Disparos em Massa:* Indisponível neste plano (exclusivo do Plano Premium)."

        return (
            f"🎉 *PAGAMENTO CONFIRMADO E PLANO ATIVADO!*\n\n"
            f"• *ID M-Pesa:* `{tx_id}`\n"
            f"• *Valor:* {valor_pago:.2f} MT\n"
            f"• *Titular:* {nome_pagador}\n"
            f"• *Plano Ativo:* ⭐ **{plano['nome']}**\n"
            f"• *Validade:* até {data_expiracao.strftime('%d/%m/%Y')}\n\n"
            f"{recurso_disparo_str}\n\n"
            f"A sua conta já está pronta a utilizar. Obrigado por confiar no **Negobot Moz**! 🚀"
        )

    except Exception as e:
        logger.error(f"Erro ao validar SMS M-Pesa do cliente: {e}", exc_info=True)
        return "❌ Erro ao processar o pagamento. Tente novamente em instantes."
