# Configuração Lemon Squeezy

A integração é híbrida: o M-Pesa/AutoPay continua disponível para pagamentos locais e a Lemon Squeezy fornece checkout online para os clientes que preferirem cartão ou PayPal.

## Variáveis protegidas no Boomploy

Adicionar no ambiente isolado do serviço `NEGOBOT Backend`:

```env
LEMONSQUEEZY_STORE_ID=
LEMONSQUEEZY_API_KEY=
LEMONSQUEEZY_WEBHOOK_SECRET=
LEMONSQUEEZY_VARIANT_BASICO=
LEMONSQUEEZY_VARIANT_MEDIO=
LEMONSQUEEZY_VARIANT_PREMIUM=
LEMONSQUEEZY_CURRENCY=USD
```

Os valores devem ser preenchidos na conta Lemon Squeezy e nunca devem ser colocados no GitHub ou enviados na conversa. Os Variant IDs devem corresponder às três subscrições mensais do NEGOBOT-MOZ.

## Webhook

Configurar na Lemon Squeezy o seguinte endpoint:

```text
https://negobot-api.duckdns.org/api/platform/webhooks/lemonsqueezy
```

Usar o mesmo signing secret colocado em `LEMONSQUEEZY_WEBHOOK_SECRET`. Ativar, no mínimo, estes eventos:

- `subscription_created`
- `subscription_updated`
- `subscription_cancelled`
- `subscription_expired`
- `subscription_payment_success`
- `subscription_payment_failed`
- `subscription_payment_recovered`
- `order_refunded`

## Segurança e ativação

O checkout é criado pelo backend com `tenant_id`, `payment_intent_id` e `plan_id` em `checkout_data.custom`. O webhook valida `X-Signature` com HMAC-SHA256, rejeita assinaturas inválidas, verifica que a intenção pertence ao tenant e guarda uma chave idempotente para não processar o mesmo evento duas vezes.

O plano só fica ativo depois de `subscription_created`, `subscription_payment_success` ou `subscription_payment_recovered`. Cancelamentos, expirações, falhas e reembolsos ficam registados no histórico por tenant.

A integração permanece desligada até que Store ID, API Key, Webhook Secret e os três Variant IDs estejam configurados no Boomploy.
