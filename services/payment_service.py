import re
import logging
from datetime import datetime, timedelta, timezone
import extensions

logger = logging.getLogger(__name__)

# Número oficial de recebimento M-Pesa (Negobot Moz)
NUMERO_RECEBEDOR_OFICIAL = "855000929"

# 🎯 TABELA OFICIAL DE PLANOS NEGOBOT MOZ
TABELA_PLANOS = {
    500.0: {
        "id": "basico",
        "nome": "Plano Básico",
        "dias_validade": 30,
        "disparo_liberado": False,
        "limite_conversas": 1500
    },
    1000.0: {
        "id": "medio",
        "nome": "Plano Médio",
        "dias_validade": 30,
        "disparo_liberado": False,
        "limite_conversas": None  # Ilimitadas
    },
    1500.0: {
        "id": "premium",
        "nome": "Plano Premium",
        "dias_validade": 30,
        "disparo_liberado": True,  # Disparos em massa liberados
        "limite_conversas": None  # Ilimitadas
    }
}


def identificar_plano_por_valor(valor_pago):
    """Mapeia o valor transferido via M-Pesa para o plano correspondente."""
    valores_ordenados = sorted(TABELA_PLANOS.keys(), reverse=True)
    for val_minimo in valores_ordenados:
        if valor_pago >= val_minimo:
            return TABELA_PLANOS[val_minimo]
    return None


def extrair_dados_sms_cliente_transferiste(sms_texto):
    """Extrai os dados da mensagem 'Transferiste...' colada pelo cliente no WhatsApp."""
    if not sms_texto or not isinstance(sms_texto, str):
        return None

    padrao = (
        r"Confirmado\s+(?P<tx_id>[A-Z0-9]+)\.\s*"
        r"Transferiste\s+(?P<valor>[\d,.]+)\s*MT.*?\s+para\s+"
        r"(?P<destino>\d+)\s*-\s*"
        r"(?P<nome_destino>.*?)\s+aos\s+"
        r"(?P<data_hora>\d{1,2}/\d{1,2}/\d{2,4}\s+as\s+\d{1,2}:\d{2}(?:\s*[AP]M)?)"
    )

    match = re.search(padrao, sms_texto, re.IGNORECASE)
    if match:
        dados = match.groupdict()
        valor_clean = dados['valor'].replace(',', '')
        return {
            "transaction_id": dados['tx_id'].upper(),
            "valor": float(valor_clean),
            "destino_telefone": re.sub(r'^258', '', dados['destino']),
            "destino_nome": dados['nome_destino'].strip(),
            "data_transacao": dados['data_hora'].strip()
        }
    return None


def extrair_codigo_mpesa(texto):
    """Extrai o ID da transação M-Pesa de qualquer mensagem."""
    texto = (texto or "").strip().upper()

    dados_envio = extrair_dados_sms_cliente_transferiste(texto)
    if dados_envio:
        return dados_envio["transaction_id"]

    match = re.search(r'\b[A-Z0-9]{8,12}\b', texto)
    if match:
        return match.group(0)

    return None


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
                "Por favor, envie o **Código da Transação** (Ex: `DGU1L0KF9I3`) ou cole o SMS do M-Pesa."
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

        # 3. Buscar no Firestore o registo inserido pelo Negobot Auto Pay
        pagamento_ref = extensions.db.collection('pagamentos_mpesa').document(tx_id)
        pagamento_doc = pagamento_ref.get()

        if not pagamento_doc.exists:
            docs = extensions.db.collection('pagamentos_mpesa')\
                .where('transaction_id', '==', tx_id)\
                .limit(1).get()
            if docs:
                pagamento_doc = docs[0]
                pagamento_ref = pagamento_doc.reference

        if not pagamento_doc.exists:
            return (
                f"⌛ *A aguardar confirmação do sistema...* (`{tx_id}`)\n\n"
                "O seu pagamento ainda não foi sincronizado pelo sistema automático.\n"
                "Por favor, aguarde **30 segundos** e envie novamente o código M-Pesa."
            )

        dados_pago = pagamento_doc.to_dict() or {}

        # 4. Anti-fraude: impede reaproveitamento do comprovativo
        if dados_pago.get('usado') is True:
            return (
                f"⚠️ *Código Já Utilizado!*\n\n"
                f"A transação M-Pesa `{tx_id}` já foi resgatada anteriormente."
            )

        # 5. Mapear valor pago para o plano correto
        valor_pago = float(dados_pago.get('valor', 0))
        plano = identificar_plano_por_valor(valor_pago)

        if not plano:
            return (
                f"⚠️ *Valor Insuficiente!*\n\n"
                f"Recebemos o código `{tx_id}` no valor de *{valor_pago:.2f} MT*.\n"
                f"O plano mínimo (*Plano Básico*) custa *500.00 MT*.\n"
                "Por favor, complete o valor restante para ativar a sua licença."
            )

        # Cálculo da validade de 30 dias
        dias_validade = plano["dias_validade"]
        data_expiracao = agora + timedelta(days=dias_validade)
        nome_pagador = dados_pago.get('remetente_nome', 'Cliente')

        # 6. ATIVAÇÃO E ATUALIZAÇÃO NO FIRESTORE
        pagamento_ref.set({
            "usado": True,
            "usado_por_tenant": tenant_id,
            "usado_por_telefone": client_phone,
            "data_ativacao": agora
        }, merge=True)

        tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
        tenant_ref.set({
            "plano": plano["id"],
            "nome_plano": plano["nome"],
            "status_plano": "ativo",
            "disparo_liberado": plano["disparo_liberado"],
            "limite_conversas": plano["limite_conversas"],
            "data_ativacao": agora,
            "data_expiracao": data_expiracao,
            "ultimo_tx_id": tx_id,
            "metodo_pagamento": "M-Pesa AutoPay"
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
