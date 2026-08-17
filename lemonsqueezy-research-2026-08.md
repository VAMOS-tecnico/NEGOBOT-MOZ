# Lemon Squeezy — notas de integração

## Fontes oficiais consultadas

- Webhooks: https://docs.lemonsqueezy.com/guides/developer-guide/webhooks
- Assinatura de webhooks: https://docs.lemonsqueezy.com/help/webhooks/signing-requests
- Métodos de pagamento: https://docs.lemonsqueezy.com/help/checkout/payment-methods
- Países suportados: https://docs.lemonsqueezy.com/help/getting-started/supported-countries

## Factos relevantes

A Lemon Squeezy envia webhooks POST em JSON para eventos como `order_created`, `subscription_created`, `subscription_updated`, `subscription_cancelled`, `subscription_expired`, `subscription_payment_failed`, `subscription_payment_success`, `subscription_payment_recovered` e `order_refunded`.

As notificações incluem `meta.event_name`, o objeto `data` e podem incluir `meta.custom_data`, que é adequado para transportar um identificador do tenant. A documentação recomenda guardar eventos localmente, responder HTTP 200 rapidamente e processar de forma idempotente.

A autenticidade é validada pelo cabeçalho `X-Signature`, calculando HMAC-SHA256 sobre o corpo bruto com o signing secret configurado no webhook.

Os métodos gerais incluem cartões, PayPal, Apple Pay, Google Pay, Alipay, WeChat Pay, Cash App Pay e débitos bancários. Para subscrições, a documentação indica suporte a cartões, Apple Pay, Google Pay e PayPal.

Moçambique aparece na lista oficial de países com pagamentos bancários suportados para comerciantes. A aprovação depende da verificação e configuração da conta Lemon Squeezy.

## Arquitetura escolhida

Manter pagamentos híbridos: Lemon Squeezy para checkout online e clientes internacionais; M-Pesa/AutoPay para clientes locais. Não guardar API keys ou webhook secrets no repositório nem na conversa. Usar variáveis protegidas no Boomploy.
