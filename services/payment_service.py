import re
import logging
from datetime import datetime, timezone
import extensions

logger = logging.getLogger(__name__)

# Valor oficial do Plano Premium
VALOR_PLANO_PREMIUM = 1500.0  # em Meticais (MT)


def extrair_codigo_mpesa(texto):
    """
    Extrai o código/ID da transação M-Pesa a partir da mensagem enviada pelo cliente.
    Suporta códigos típicos M-Pesa em Moçambique (ex: 10B1234567, B12345678, etc.).
    """
    texto = (texto or "").upper()
    
    # Procura por padrões comuns de ID M-Pesa (alfanumérico de 8 a 12 caracteres)
    match = re.search(r'\b[A-Z0-9]{8,12}\b', texto)
    if match:
        return match.group(0)
    return None


def validar_e_ativar_pagamento_mpesa(tenant_id, client_phone, message_text):
    """
    Cruza o código/comprovativo M-Pesa enviado pelo cliente com a coleção 
    'pagamentos_mpesa' alimentada em tempo real pelo app 'Negobot Auto Pay'.
    """
    try:
        agora = datetime.now(timezone.utc)
        
        # 1. Extrair o código M-Pesa da mensagem do cliente
        tx_id = extrair_codigo_mpesa(message_text)
        
        if not tx_id:
            return (
                "⚠️ *Código de Transação Não Identificado!*\n\n"
                "Não conseguimos encontrar o código M-Pesa na sua mensagem.\n"
                "Por favor, envie a **mensagem de confirmação do M-Pesa** ou digite apenas o **Código** (Exemplo: *10B1234567*)."
            )

        # 2. Buscar a transação no Firestore (capturada pelo Negobot Auto Pay)
        pagamento_ref = extensions.db.collection('pagamentos_mpesa').document(tx_id)
        pagamento_doc = pagamento_ref.get()

        # Fallback: Se o documento não usar o tx_id como ID da coleção, faz query pelo campo
        if not pagamento_doc.exists:
            docs = extensions.db.collection('pagamentos_mpesa')\
                .where('transaction_id', '==', tx_id)\
                .limit(1).get()
            if docs:
                pagamento_doc = docs[0]
                pagamento_ref = pagamento_doc.reference

        if not pagamento_doc.exists:
            return (
                f"❌ *Transação Não Encontrada!* (`{tx_id}`)\n\n"
                "O pagamento ainda não deu entrada no nosso sistema automático.\n"
                "• Confirme se a transferência foi feita para **855000929** (Abel Francisco).\n"
                "• Aguarde cerca de 1 a 2 minutos para sincronização da mensagem e tente novamente."
            )

        dados_pagamento = pagamento_doc.to_dict() or {}

        # 3. Proteção Anti-Fraude: Verificar se o código já foi utilizado
        if dados_pagamento.get('usado') is True:
            return (
                f"⚠️ *Transação Já Utilizada!*\n\n"
                f"O código M-Pesa `{tx_id}` já foi resgatado para ativar um plano anteriormente.\n"
                "Se considera que isto é um erro, entre em contacto com a nossa central de suporte."
            )

        # 4. Validar o valor transferido
        valor_pago = float(dados_pagamento.get('valor', 0))
        if valor_pago < VALOR_PLANO_PREMIUM:
            return (
                f"⚠️ *Valor Insuficiente!*\n\n"
                f"Confirmámos a entrada do código `{tx_id}` no valor de *{valor_pago:.2f} MT*.\n"
                f"O valor para o *Plano Premium* é de *{VALOR_PLANO_PREMIUM:.2f} MT*.\n"
                "Por favor, faça o complemento do valor ou fale com o suporte."
            )

        # 5. ATIVAÇÃO DO PLANO E BLOQUEIO DA TRANSAÇÃO
        # A) Marca a transação M-Pesa como USADA
        pagamento_ref.set({
            "usado": True,
            "usado_por_tenant": tenant_id,
            "usado_por_telefone": client_phone,
            "data_resgate": agora
        }, merge=True)

        # B) Atualiza a conta da empresa no Firestore para PLANO PREMIUM
        tenant_ref = extensions.db.collection('clientes_bot').document(tenant_id)
        tenant_ref.set({
            "plano": "premium",
            "status_plano": "premium",
            "data_ultima_renovacao": agora,
            "metodo_pagamento": "M-Pesa AutoPay",
            "ultimo_tx_id": tx_id
        }, merge=True)

        logger.info(f"🎉 Plano Premium ativado com sucesso para {tenant_id} via M-Pesa ID: {tx_id}")

        return (
            f"🎉 *PAGAMENTO CONFIRMADO E PLANO ATIVADO!*\n\n"
            f"• *ID M-Pesa:* `{tx_id}`\n"
            f"• *Valor:* {valor_pago:.2f} MT\n"
            f"• *Novo Plano:* ⭐ **Premium (Ativo)**\n\n"
            f"Todas as ferramentas avançadas (incluindo **Disparos em Massa** `#disparo`) já estão **100% desbloqueadas**!\n\n"
            f"Obrigado por utilizar o **Negobot Moz**! 🚀"
        )

    except Exception as e:
        logger.error(f"Erro ao validar pagamento M-Pesa para {tenant_id}: {e}", exc_info=True)
        return "❌ Ocorreu um erro interno ao processar a validação do seu pagamento."
