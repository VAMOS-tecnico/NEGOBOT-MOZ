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


## Verificação adicional do domínio público

Em 18/08/2026, `https://negobotmoz.duckdns.org/` abriu correctamente a landing page React. O idioma inicial apareceu em inglês, mas o botão `PT` mudou imediatamente toda a interface para Português, incluindo os preços, benefícios e CTAs.

Os botões `Criar espaço na plataforma`, `Escolher Básico`, `Escolher Médio` e `Escolher Premium` apontam para o subdomínio privado `app-negobotmoz.duckdns.org/plataforma/register`, com o plano e o idioma pré-seleccionados.


## Verificação Lemon Squeezy no Boomploy

O cartão `NEGOBOT Backend` está autenticado e `running`. Os nomes das variáveis Lemon Squeezy estão presentes e os logs mostram um arranque recente do Gunicorn depois da configuração.

Foi detectada uma correcção necessária: `LEMONSQUEEZY_VARIANT_PREMIUM` está preenchida com um URL de checkout, mas o backend espera o **ID da variante**, normalmente um UUID. Os campos Basic e Médio aparecem no formato de ID de variante. O URL de checkout não deve ser usado como valor de `LEMONSQUEEZY_VARIANT_PREMIUM`.

Não foram guardados neste relatório valores de API keys, tokens ou segredos.


## Confirmação final das variantes Lemon Squeezy

Após recarregar o Boomploy e autenticar novamente, o cartão `NEGOBOT Backend` mostrou os três campos `LEMONSQUEEZY_VARIANT_BASICO`, `LEMONSQUEEZY_VARIANT_MEDIO` e `LEMONSQUEEZY_VARIANT_PREMIUM` preenchidos com valores numéricos. O Backend permanece `running`. A configuração está agora no formato esperado por `variant_for_plan()`.


## Auditoria omnichannel — fontes oficiais iniciais

A documentação Meta do Instagram, actualizada em 03/03/2026, confirma que contas profissionais podem receber webhooks para comentários, menções, expiração de Stories e mensagens. A integração exige endpoint HTTPS com verificação GET (`hub.mode`, `hub.challenge`, `hub.verify_token`), subscrição de campos no App Dashboard, conta Instagram profissional ligada à aplicação e app em Live. Para comentários e `live_comments`, a Meta indica Advanced Access e Business Verification.

A documentação oficial do Telegram Bot API confirma que bots podem receber updates por webhook HTTPS. O endpoint deve devolver um código HTTP 2xx; o Telegram repete pedidos que falhem. O webhook pode usar `secret_token`, enviado no cabeçalho `X-Telegram-Bot-Api-Secret-Token`, e permite limitar `allowed_updates` e controlar `max_connections`.

Conclusão inicial: Instagram/Facebook e Telegram podem ter adaptadores com webhooks isolados por tenant, mas exigem credenciais, IDs de conta/página, revisão/permissões e segredos próprios; não devem ser activados globalmente apenas pela interface.


## Auditoria omnichannel — TikTok, LinkedIn e X

A documentação oficial do TikTok Business Messaging confirma suporte a mensagens directas para contas Business autorizadas, com interfaces para conversas, envio de mensagens, imagens, mensagens automáticas e webhooks de Business Messaging. O acesso depende de conta Business, autorização, aplicação TikTok for Business e eventuais revisões de segurança/privacidade e disponibilidade regional; não deve ser tratado como uma integração livre sem aprovação.

A documentação oficial do LinkedIn indica que a maioria das permissões e programas exige aprovação explícita. As permissões abertas cobrem autenticação/partilha de conteúdo, enquanto produtos de vendas e acesso a dados profissionais dependem de programas parceiros. O catálogo menciona mensagens no contexto de Sales Display, mas não autoriza presumir DMs gerais para qualquer aplicação SaaS.

A documentação oficial do X confirma endpoints OAuth para criar conversas e enviar DMs, lookup de eventos e webhooks. Webhooks exigem HTTPS público, resposta rápida 2xx, CRC challenge-response, verificação de assinatura e conta/app aprovados. A integração deve ser opcional e activada somente quando o cliente conceder OAuth e o projecto X tiver acesso compatível.

Conclusão: a primeira versão omnichannel deve separar `connected`, `pending_review`, `not_configured`, `error` e `disabled`, mostrando no painel quais canais estão realmente activos. Instagram/Facebook, Telegram, TikTok e X têm caminhos técnicos claros; LinkedIn deve começar como publicação/gestão autorizada ou canal “aguarda aprovação”, não como promessa de DM universal.


## 2026-08-18 — Publicação omnichannel

O commit `44153ac` foi publicado no GitHub e o redeploy do `NEGOBOT Backend` e do `NEGOBOT Site` foi concluído no Boomploy. O Site iniciou às 21:14:58 UTC e permanece `running`. O site público foi validado em `https://negobotmoz.duckdns.org/`: depois da renderização inicial, apresentou o hero `Automação omnichannel`, a mensagem sobre WhatsApp, Instagram, Facebook, Telegram, TikTok, LinkedIn, X e email, a faixa visual de marcas, os planos e os CTAs de registo. Nenhum volume persistente foi alterado.


A entrada privada `https://app-negobotmoz.duckdns.org/plataforma/` continua a apresentar o login e não expõe o painel sem sessão. A rota `register?plan=premium&region=international` carregou o formulário React depois da renderização inicial, com `Outro país · cartão/PayPal via Lemon Squeezy` e `Premium · 1.500 MT / 30 dias` pré-seleccionados. Não foi criada nenhuma conta de teste.


O redeploy autorizado do `NEGOBOT Incoming Worker` foi iniciado pelo cartão Boomploy e o serviço permanece em estado `running`. A validação final dos logs será feita após abrir o cartão, sem alterar variáveis ou volumes.


A validação do cartão `NEGOBOT Incoming Worker` confirmou Firebase inicializado e o log `Consumidor online queues=whatsapp_incoming_queue,omnichannel_incoming_queue` às 21:16:04 UTC. O Worker permanece `running` e continua a processar eventos WhatsApp; a segunda fila omnichannel está activa no mesmo processo persistente.
