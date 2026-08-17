# Validação da plataforma React — 2026-08

## Estado observado

- `https://app-negobotmoz.duckdns.org/plataforma/` carregou a página de login React `NEGOBOT-MOZ | Plataforma`, com campos de identificador/email, palavra-passe e botão de entrada.
- `https://app-negobotmoz.duckdns.org/plataforma-react/` carregou o bundle React e mostrou inicialmente `A carregar a plataforma...`; o conteúdo extraído também identificou a mesma página de login React.
- O acesso foi feito sem credenciais e nenhuma alteração foi efetuada.

## Próxima verificação

Aguardar a hidratação completa do alias `/plataforma-react/` e confirmar a proteção do domínio público `negobotmoz.duckdns.org` contra rotas administrativas.

## Confirmação adicional

- `https://negobotmoz.duckdns.org/plataforma/` redirecionou para o domínio institucional `https://negobotmoz.duckdns.org/`, sem expor login administrativo.
- O site público apresenta foco comercial, planos Básico/Médio/Premium, valores 500/1000/1500 MT e chamadas para falar pelo WhatsApp ou pela plataforma.
- O alias `https://app-negobotmoz.duckdns.org/plataforma-react/` foi normalizado para `/plataforma-react/login` e mostrou a mesma tela de login React que o endereço principal.

## Conclusão da fase 1

A migração React está publicada no subdomínio administrativo, com `/plataforma/` como rota principal, `/plataforma-react/` como alias e bloqueio/redirecionamento das rotas administrativas no domínio público.

## Deploy da primeira entrega SaaS

- O Pull Request #5 foi integrado na `main` no commit `5a0b78b7d0135b7b679e9925eb40086a3468e90b`; CI, build Docker e 33 testes passaram.
- O painel Boomploy mostra `negobot-moz` como projeto `main/live`.
- A consulta autenticada a `/api/projects` devolveu `[]`, apesar do cartão visual existir; não foi acionado nenhum deploy porque o identificador efetivo do projeto ainda não foi confirmado.

## Deploy da entrega CRM

- A expansão CRM foi integrada na `main` pelo PR #7 no commit `593582da49c9c0a18074e6654aea8a6f75b1d84f`; o PR #6 conflituoso foi fechado.
- O cartão de projeto GitHub `prj_negobot_moz` foi redeployado pelo Boomploy; a leitura autenticada de `/api/projects/prj_negobot_moz/logs?tail=300` respondeu HTTP 200.
- Os logs pós-deploy mostram Gunicorn a iniciar na porta 5000 com dois workers.
- O botão de redeploy do serviço wrapper `negobot-site` continua a falhar com a imagem placeholder `ghcr.io/REPLACE_OWNER/negobot-site:latest`; não foi repetido para evitar ações às cegas.
