# Publicação permanente do site React — 2026-08-17

## Resultado

O site público React do NEGOBOT-MOZ está publicado permanentemente em:

- https://negobotmoz.duckdns.org/
- https://negobotmoz.duckdns.org/assistente

## Alterações versionadas

- NEGOBOT-MOZ: `c6d3301` — `feat: migrate public site to robust React experience`
- boomploy-infra: `4866566` — `fix: publish NEGOBOT React site from repository`

O Compose passou a construir `negobot-site` a partir de `./services/negobot-backend/source`, usando `workflows/Site.Dockerfile`, com a imagem local `boomploy-negobot-site:latest`. O placeholder `ghcr.io/REPLACE_OWNER/negobot-site:latest` foi removido.

## Validação de produção

- `/`: HTTP 200; título `NEGOBOT-MOZ | Atendimento inteligente para negócios`.
- `/assistente`: HTTP 200; título `Assistente | NEGOBOT-MOZ`.
- `/health`: `{"service":"negobot-site","status":"online"}`.
- O navegador confirmou a landing page React com navegação, planos, CTAs, assistente e layout responsivo.
- A plataforma privada continua separada em `https://app-negobotmoz.duckdns.org/plataforma/`.

## Infraestrutura

O projeto NEGOBOT-MOZ foi redeployado para sincronizar a fonte atualizada no VPS; o backend terminou `live`. O redeploy posterior foi limitado ao `negobot-site`. Evolution API, n8n, PostgreSQL e Redis não foram redeployados nem tiveram volumes removidos.
