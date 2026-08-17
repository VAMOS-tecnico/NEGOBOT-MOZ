# n8n e campanhas omnichannel

## Objetivo

O backend e o worker do NEGOBOT-MOZ continuam a gravar campanhas e destinatários no Firestore e a executar a fila Redis fora do browser. Quando uma campanha inclui canais além de WhatsApp, o worker emite o evento `campaign.dispatch` para o webhook de produção do n8n.

O n8n deve usar um **Webhook node** publicado em produção com autenticação Header Auth. A documentação oficial do n8n confirma que o Webhook node suporta Header Auth, Basic Auth e JWT Auth, além de URLs distintas para teste e produção [1]. O workflow pode responder imediatamente ou usar o nó Respond to Webhook para controlar o código e corpo da resposta [2].

## Variáveis do backend

| Variável | Valor |
|---|---|
| `N8N_CAMPAIGN_WEBHOOK_URL` | URL de produção do Webhook node n8n |
| `N8N_WEBHOOK_SECRET` | Segredo partilhado entre backend/worker e a credencial Header Auth do n8n |
| `N8N_WEBHOOK_TIMEOUT` | Timeout em segundos; padrão 12 |
| `N8N_WEBHOOK_RETRIES` | Número máximo de tentativas; padrão 3 |

O segredo não deve ser colocado no GitHub nem no frontend. Deve ser guardado no `.env` isolado do serviço NEGOBOT Backend através do Boomploy.

## Headers enviados

| Header | Conteúdo |
|---|---|
| `X-NEGOBOT-Event` | `campaign.dispatch` |
| `X-NEGOBOT-Request-ID` | ID da campanha, usado para correlação e idempotência |
| `X-NEGOBOT-Signature` | HMAC-SHA256 hexadecimal do corpo JSON |

O n8n deve verificar o header configurado na credencial Header Auth. Dentro do workflow, o campo `request_id` deve ser usado para evitar publicação duplicada. Os canais recebidos estão no array `channels`, que pode conter `facebook`, `instagram`, `tiktok`, `x`, `linkedin`, `telegram` e `email`.

## Contrato de payload

```json
{
  "event": "campaign.dispatch",
  "request_id": "campaign-document-id",
  "tenant_id": "tenant-document-id",
  "campaign_id": "campaign-document-id",
  "channels": ["instagram", "telegram"],
  "message": "Mensagem base da campanha",
  "offer": "Plano Premium por 1.500 MT",
  "language": "pt-MZ",
  "tone": "profissional",
  "scheduled_at": null
}
```

O workflow deve ramificar pelos canais autorizados, aplicar as credenciais próprias do tenant ou da plataforma, devolver os resultados por canal e preservar os estados de erro. A ausência de `N8N_CAMPAIGN_WEBHOOK_URL` ou `N8N_WEBHOOK_SECRET` não interrompe campanhas apenas de WhatsApp; campanhas omnichannel ficam com `orchestration_status=not_configured` até a configuração ser concluída.

## Referências

[1]: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook "n8n Webhook node"
[2]: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.respondtowebhook "n8n Respond to Webhook node"
