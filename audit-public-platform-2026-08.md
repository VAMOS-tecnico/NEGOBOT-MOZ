# Auditoria do percurso público e da plataforma — 18/08/2026

## Estado encontrado

O site público carregava a landing page React, com planos e assistente comercial, mas os botões dos planos apenas abriam o diálogo do assistente; não existia registo de cliente nem encaminhamento para a criação de conta. A página pública permitia idioma PT/EN e ligação ao assistente WhatsApp.

A plataforma privada apresentava o carregamento inicial e não tinha rota de registo de cliente. O backend expunha login, APIs de cliente, planos, M-Pesa, Lemon Squeezy e QR apenas depois de uma conta ser criada pelo administrador.

## Alterações implementadas no commit 6454409

Foi criado `POST /api/platform/auth/register`, que cria um tenant isolado, uma conta de cliente com password hash, grava `trial_status=trial_pending_connection`, guarda a região de pagamento e o plano de interesse, e inicia a sessão.

O site público agora liga cada botão de plano a `https://app-negobotmoz.duckdns.org/plataforma/register?plan=...`, e os CTAs da plataforma abrem o registo real. O formulário recolhe empresa, email, password, região de pagamento e plano. O login também aponta para a demonstração de 2 dias.

A plataforma passou a ter `/plataforma/register`, uma rota de timeout para não ficar indefinidamente em “A carregar a plataforma…”, e estados visíveis no módulo de pagamentos: trial pendente de ligação, trial activo, trial expirado ou plano activo.

O backend e a interface aplicam a região: Moçambique usa M-Pesa/AutoPay; internacional usa Lemon Squeezy. Foram adicionados testes de registo e duplicação de email.

## Validação

Backend: 62 testes passaram.
Frontend: `pnpm run check` e `pnpm run build` passaram.

## Próximo passo

Reconstruir os serviços geridos `NEGOBOT Backend` e `NEGOBOT Site` no Boomploy a partir do branch `main`, depois validar publicamente `/`, `/plataforma/`, `/plataforma/login` e `/plataforma/register`.


## Redeploy confirmado — Boomploy

O painel Boomploy foi autenticado com sucesso. Foram accionadas as acções de force re-deploy para os cartões `NEGOBOT Backend` e `NEGOBOT Site` após confirmação do utilizador. O cartão do Site mostra Gunicorn a arrancar novamente e os serviços permanecem `running`. Nenhum volume persistente foi alterado.


## Validação pública pós-deploy

O site `https://negobotmoz.duckdns.org/` já mostra `Create your platform space`/`Criar espaço na plataforma` e os três botões de planos apontam para `/plataforma/register` com `plan=basico`, `plan=medio` ou `plan=premium`.

A rota `https://app-negobotmoz.duckdns.org/plataforma/register?plan=premium&lang=pt` carregou o formulário real, com Premium pré-seleccionado, opção Moçambique/M-Pesa para `855000929`, opção internacional/cartão-PayPal via Lemon Squeezy e instrução de trial iniciado apenas depois da ligação WhatsApp.

A entrada `https://app-negobotmoz.duckdns.org/plataforma/` deixou de ficar presa no carregamento e apresenta o login com o link `Começa a demonstração de 2 dias`.

Smoke test seguro em produção: `POST /api/platform/auth/register` com dados inválidos respondeu HTTP 400 com a validação esperada; `GET /api/platform/auth/me` respondeu `authenticated=false`. Nenhum tenant de teste foi criado.
