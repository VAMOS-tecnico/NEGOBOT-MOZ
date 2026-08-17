# Validação do site público React — 2026-08

## Implementação

O site público React foi implementado em `platform-react/src/pages/PublicSite.tsx`, com estilos isolados em `platform-react/src/styles/public.css`. O router em `platform-react/src/App.tsx` mantém `/plataforma` e `/plataforma-react` privados e usa React para `/` e `/assistente`.

O servidor `site_server.py` foi ajustado para servir o bundle React em `/` e `/assistente`, além dos assets Vite em `/assets/<path>`. O `workflows/Site.Dockerfile` passou a compilar o frontend dentro de uma etapa Node e servi-lo numa imagem Python/Gunicorn.

## Validação local

- Pré-visualização Vite renderizou a landing page completa.
- Navegação para Capacidades, Planos, Como funciona e Contacto está presente.
- Modal do assistente comercial abriu corretamente.
- O formulário do assistente usa `POST /api/platform/public/assistant/chat`.
- `pnpm exec tsc --noEmit`: passou.
- `pnpm build`: passou.
- `python3 -m py_compile site_server.py`: passou.
- Suíte backend: 37 testes passaram.

## Publicação

Commit publicado na `main`: `c6d3301 feat: migrate public site to robust React experience`.

Pré-visualização temporária: `https://4173-i7it3xqq972u66krpauoy-54970c67.us1.manus.computer/`

## Bloqueio de produção

O redeploy do cartão `NEGOBOT Site` no Boomploy falhou antes de construir a nova imagem porque a infraestrutura em produção ainda referencia `ghcr.io/REPLACE_OWNER/negobot-site:latest`. A mensagem observada foi `invalid reference format: repository name (REPLACE_OWNER/negobot-site) must be lowercase`.

O cartão mostra `NEGOBOT Site` como `running`, mas a imagem pública ainda não foi substituída. O serviço público continua dependente do Compose/configuração do repositório privado `boomploy-infra`, que está inacessível nesta sessão. Evolution API, n8n, PostgreSQL, Redis e backend não foram alterados neste redeploy falhado.
