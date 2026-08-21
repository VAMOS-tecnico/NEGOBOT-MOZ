# Auditoria de integração do painel do cliente — 21-08-2026

## Estado publicado

- `https://negobot-api.duckdns.org/healthz` respondeu `{"status":"ok"}`.
- `https://negobot-api.duckdns.org/readyz` respondeu `{"status":"ready","checks":{"firebase":"online","redis":"online"}`.
- `https://negobotmoz.duckdns.org/` respondeu HTTP 200.
- `https://app-negobotmoz.duckdns.org/plataforma` respondeu HTTP 200 e carregou a página de autenticação com selector PT/EN.
- A autenticação do painel usa os endpoints `/api/platform/auth/*`, com isolamento declarado por `tenant_id`.

## Ligações reais já existentes

- WhatsApp/Evolution: QR Code e estado de ligação por tenant; campanhas e grupos próprios usam a instância do tenant, verificam estado `open` e revalidam grupos administrados.
- Contactos: CRUD, importação CSV/XLSX, filtros e opt-in são tenant-scoped.
- Campanhas: criadas pelo painel, persistidas em Firestore e enfileiradas em `negobot:campaigns`; WhatsApp/grupos próprios são enviados pelo Campaign Worker com limites, atrasos, janela de silêncio e revalidação de opt-in/admin.
- Grupos próprios: sincronização via Evolution, verificação de administrador, automação por menção/keywords/boas-vindas e whitelist para campanhas.
- IA/assistente: definições do tenant são persistidas; processamento de IA foi migrado para AI Worker.
- M-Pesa: validação de comprovativo/SMS no painel e associação com AutoPay através de `payment_intents`.
- Lemon Squeezy: checkout internacional, addons, webhook assinado em `/api/platform/webhooks/lemonsqueezy` e aplicação tenant-scoped.
- Telegram: ligação via token, validação Bot API, webhook com `secret_token`, token cifrado no Firestore e estado persistido.
- OAuth: fluxos Meta/Instagram/Facebook, TikTok, X e LinkedIn existem, mas dependem de credenciais, permissões e aprovação do fornecedor.
- n8n: Campaign Worker encaminha canais não-WhatsApp para `POST /webhook/evolution` com `X-NEGOBOT-Signature`; teste publicado respondeu HTTP 200.

## Bloqueios honestos

- WhatsApp Channels nativos: o painel permite criar/agendar drafts, mas o adaptador de entrega está deliberadamente desactivado. `channel_capability()` responde `pending_authorization`, `adapter_configured=false` e `can_publish=false`. O worker marca a publicação como `blocked` com `outbound_adapter_not_configured` e não tenta uma chamada Evolution não documentada.
- Campanhas não-WhatsApp: o Campaign Worker encaminha eventos para n8n; isso não equivale a entrega directa em Instagram, Facebook, TikTok, X, LinkedIn, Telegram ou Email. O estado de orquestração pode ficar `not_configured` ou `failed` se o workflow/adaptador por canal não estiver implementado.
- Estado de canais OAuth: a UI deriva grande parte do estado de campos persistidos em `tenant.channels`; `connected` só é honesto quando o callback OAuth completou e o evento/conta foi persistido. A revisão do fornecedor continua necessária.
- O painel não deve expor chaves ou marcar canal como activo apenas por existir um cartão React.

## Verificações locais

- Backend: 130 testes passaram.
- Frontend: `pnpm run check` passou.
- Frontend: `pnpm run build` passou.
- A execução dos testes locais mostra fallback de thread quando a biblioteca Redis não está instalada no ambiente de testes; isso não afecta o `readyz` de produção, que confirmou Redis online.

## Decisão de implementação

Antes de qualquer alteração de código ou redeploy, separar melhorias de ligação segura (estados honestos, chamadas já suportadas, n8n, pagamentos, QR, canais com credenciais) de integrações que exigem aprovação/adaptador externo (Channels nativos e entrega directa multicanal). Não reiniciar serviços nem tocar em volumes persistentes sem confirmação explícita do utilizador.

Autor: Manus AI
Data: 2026-08-21
