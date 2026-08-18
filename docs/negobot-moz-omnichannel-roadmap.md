# Roteiro de evolução omnichannel — NEGOBOT-MOZ

## 1. Objectivo

A NEGOBOT-MOZ evoluirá de uma plataforma centrada em WhatsApp para um SaaS omnichannel de atendimento, CRM e campanhas. O cliente poderá acompanhar canais, conversas, contactos, campanhas, pagamentos e métricas num único espaço privado, mantendo o isolamento por tenant e a execução assíncrona através de Redis, workers e Boomploy.

A evolução não muda a stack existente. O backend continua em Flask/Python, o frontend em React/Vite, os dados em Firebase/Firestore, a fila em Redis, o WhatsApp em Evolution API e a infraestrutura em Boomploy/Caddy. A referência de deploy é **Boomploy**, não Dokploy.

## 2. Estado actual e fronteira de entrega

| Canal ou função | Estado actual | Próximo tratamento |
|---|---|---|
| WhatsApp | Integrado via Evolution API, QR Code, `CONNECTION_UPDATE`, incoming worker e trial dependente da ligação | Preservar e usar como canal de referência |
| M-Pesa/AutoPay | Integrado para clientes de Moçambique | Preservar; activar plano somente após validação |
| Lemon Squeezy | Checkout, webhook assinado e activação preparados; variantes configuradas | Testar checkout e webhook com conta internacional controlada |
| Instagram/Facebook | Arquitectura e documentação previstas; dependem de Meta App, permissões, Business Verification e tokens por cliente | Criar adaptador Meta isolado e estado de ligação |
| Telegram | API oficial com webhook HTTPS e secret token | Criar adaptador por bot/tenant |
| TikTok | Business Messaging API disponível para contas Business autorizadas, sujeita a acesso e revisão | Criar adaptador opcional e estado `pending_review` |
| X | DMs e webhooks disponíveis com OAuth, CRC e assinatura | Criar adaptador opcional com OAuth por tenant |
| LinkedIn | Acesso a mensagens e programas profissionais depende de aprovação/partner access | Não prometer DM universal; começar com publicação e estado `pending_review` |
| Email | Não existe ainda um fornecedor de inbound/outbound fechado no código | Definir SMTP ou provedor transaccional antes de implementar envio |
| n8n | Orquestração omnichannel documentada, dependente de URL e segredo reais | Usar para campanhas externas, com retries, correlação e idempotência |

## 3. Contratos técnicos corrigidos

O webhook Lemon Squeezy correcto é:

```text
https://negobot-api.duckdns.org/api/platform/webhooks/lemonsqueezy
```

O caminho `/api/webhook/lemonsqueezy` não pertence ao backend actual e devolve `404`. O endpoint verifica `X-Signature`, grava eventos de forma idempotente, associa o pagamento através de `tenant_id`, `payment_intent_id` e variante, e activa ou expira o plano conforme o evento.

As variantes Lemon Squeezy devem ser **IDs numéricos**, não URLs de checkout nem UUIDs de slug:

```text
LEMONSQUEEZY_VARIANT_BASICO=<ID numérico>
LEMONSQUEEZY_VARIANT_MEDIO=<ID numérico>
LEMONSQUEEZY_VARIANT_PREMIUM=<ID numérico>
```

Os links `/checkout/buy/...` continuam a ser links de pagamento para clientes, não valores de configuração do backend.

## 4. Arquitectura de canais

Cada canal será implementado através de um adaptador com o mesmo contrato lógico:

```text
InboundEvent -> validação de assinatura -> normalização -> tenant resolver
             -> Redis queue -> processamento IA/roteiro -> outbound adapter
             -> delivery result -> métricas/auditoria
```

O evento normalizado deve conter, no mínimo, `tenant_id`, `channel`, `external_account_id`, `conversation_id`, `contact_id`, `message_id`, `direction`, `text`, `media`, `received_at`, `idempotency_key` e `raw_provider_event` redigido de segredos. Cada adaptador deve devolver estados `received`, `queued`, `processed`, `sent`, `failed` ou `manual_review`.

Nenhum tenant poderá reutilizar tokens de outro tenant. Segredos serão guardados no ambiente seguro ou em referências protegidas, nunca no frontend, nos prompts ou em documentos públicos. Os endpoints de webhook devem responder rapidamente e fazer o trabalho pesado através da fila persistente.

## 5. Experiência do cliente

A landing page deverá explicar que a NEGOBOT-MOZ centraliza WhatsApp, Instagram, Facebook, Telegram, TikTok, LinkedIn, X e email, mas deve distinguir claramente **canais disponíveis**, **canais em ligação** e **canais que exigem aprovação do fornecedor**. Os logótipos serão apresentados como elementos de interface, sem sugerir que uma integração está activa quando ainda não foi autorizada.

O registo continuará a começar com uma demonstração única de dois dias. O contador só inicia depois de o WhatsApp ficar ligado. Na primeira etapa serão pedidos apenas os dados necessários para criar o tenant e seleccionar a região de pagamento; o perfil empresarial e os canais serão completados no onboarding. A confirmação de password pode ser mantida como validação de segurança no frontend ou substituída por validação equivalente, mas nunca deve reduzir a segurança do endpoint.

O painel do cliente terá uma área **Canais** com cartões independentes. Cada cartão mostrará estado, última sincronização, permissões, acção de ligar/desligar e mensagens de erro accionáveis. Um canal pendente ou não configurado não bloqueará o WhatsApp nem as campanhas de outros canais.

## 6. Fases de implementação

| Fase | Entrega | Critério de aceitação |
|---|---|---|
| 1 | Auditoria e contratos corrigidos | Roteiro alinhado com Boomploy, webhook real e capacidades verificadas |
| 2 | Modelo de canais e permissões | Estados por tenant, segredos separados, isolamento e feature flags |
| 3 | Backend/adaptadores | Endpoints de verificação, webhooks, normalização, fila, retries e auditoria |
| 4 | React omnichannel | Hero, registo, cartões de canais, conversas unificadas, campanhas e estados claros |
| 5 | Testes e validação | Testes de isolamento, assinaturas, idempotência, pagamentos e regressões WhatsApp |
| 6 | Publicação | Commit GitHub, redeploy visual no Boomploy, smoke tests e rollback documentado |

## 7. Dependências que o proprietário terá de fornecer

Para activar canais além de WhatsApp e email, serão necessários tokens e aprovações próprios: Meta App ID/Secret, contas profissionais e Business Verification; Telegram Bot Token; TikTok Business App e autorização; X Project/App e OAuth; LinkedIn app e eventual aprovação de produto; e um fornecedor SMTP/inbound para email. Estes valores serão solicitados apenas quando o adaptador correspondente estiver pronto.

## 8. Referências oficiais

[1]: https://developers.facebook.com/documentation/instagram-platform/webhooks "Meta — Setup Webhooks Subscriptions"
[2]: https://core.telegram.org/bots/api "Telegram Bot API"
[3]: https://business-api.tiktok.com/portal/bm-api/education-hub "TikTok Business Messaging API"
[4]: https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access "LinkedIn — Getting Access to APIs"
[5]: https://docs.x.com/x-api/direct-messages/manage/introduction "X API — Manage Direct Messages"
[6]: https://docs.x.com/x-api/webhooks/introduction "X API — V2 Webhooks"
[7]: https://docs.lemonsqueezy.com/guides/developer-guide/taking-payments "Lemon Squeezy — Taking Payments"
