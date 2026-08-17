# Validação do deploy de normalização de áudio

Data da validação: 2026-08-17.

## Publicação

- Commit GitHub: `64d2402` — `feat: validate and normalize inbound audio before Whisper`.
- GitHub Actions: workflow `NEGOBOT automated tests` concluído com sucesso.
- Testes no CI: instalação de FFmpeg, compilação Python, verificação de whitespace e suíte completa executados com sucesso.
- Redeploy: iniciado pelo cartão visual do Boomploy para apenas `negobot-backend`, através de `/api/services/negobot-backend/actions/redeploy`, com HTTP 200.
- Os serviços Evolution API, n8n, PostgreSQL, Redis e NEGOBOT Site não foram alvo do redeploy.

## Estado pós-redeploy

O Boomploy mostrou `redeploy concluído.`. Os logs do `negobot-backend` mostram novo arranque do Gunicorn às `2026-08-17T09:15:23Z`, com workers 7 e 8 inicializados. O cartão do serviço permaneceu em estado `running`.

O endpoint público `https://negobot-api.duckdns.org/health` respondeu HTTP 200 com:

```json
{"service":"negobot-moz","status":"online"}
```

## Limites da validação

Ainda não foi enviada uma nova mensagem de voz real depois deste deploy. A validação confirma build, arranque, saúde HTTP e testes automatizados; o teste final de OGG/Opus exige enviar uma voz pelo WhatsApp e observar os logs do backend e a resposta do bot.

## Teste real de voz

A voz enviada chegou ao backend e gerou eventos `messages.upsert` e resposta `send.message`, mas o log mostrou o caminho antigo: `magic=acb812...` e MIME `audio/ogg; codecs=opus`, seguido de HTTP 400 do Groq. A nova mensagem `Áudio preparado para Whisper` não mostrou `RIFF/WAVE`, portanto a camada FFmpeg ainda não está em execução na imagem ativa.

Diagnóstico operacional: o cartão de projeto `negobot-moz` no Boomploy está configurado para a branch `main`, enquanto o commit `64d2402` foi publicado na branch `react-platform-preview`. O redeploy HTTP 200 foi concluído, mas reconstruíu a versão da `main`, não a correção recém-publicada. A próxima ação segura é integrar a branch testada em `main` após o CI e repetir o redeploy pelo Boomploy.

## Redeploy final a partir da `main`

- Pull Request #2 foi mergeado com sucesso para `main` no commit `80f4299753e0cff3ec7fbaae30e1c0f0235c4668`.
- O workflow da `main` passou com sucesso, incluindo instalação de FFmpeg e os 26 testes.
- O segundo redeploy visual do `negobot-backend` devolveu HTTP 200, chamou `/api/services/negobot-backend/actions/redeploy` e mostrou `redeploy concluído.`
- Os logs mostram novo arranque do Gunicorn às `2026-08-17T09:19:36Z`, com os workers inicializados e o serviço `running`.
- A voz anterior foi enviada antes deste redeploy final; portanto, ainda é necessário repetir o teste de voz para validar a camada FFmpeg da imagem atualmente ativa.

## Causa do segundo bloqueio

A definição do serviço no Compose usa `context: ./services/negobot-backend` e `dockerfile: Dockerfile`, enquanto o projeto GitHub é tratado como `managed_service`. O endpoint do cartão chama `service_action("negobot-backend", "redeploy")`, que executa `docker compose up -d --pull always --force-recreate` sobre o serviço gerido; portanto, não usa o Dockerfile raiz recém-adicionado ao repositório NEGOBOT.

O serviço aparece com `build_context=true` e `source_kind=repo` no painel, mas o caminho efetivo do Compose continua a ser o contexto local `/opt/infra/services/negobot-backend`. Isso explica o log `FFmpeg/ffprobe não estão instalados no backend` mesmo depois de o CI ter construído corretamente a imagem Docker do repositório.

A correção definitiva deve ligar o redeploy do cartão ao deploy GitHub do projeto ou sincronizar explicitamente o source GitHub para o contexto do serviço antes do `docker compose build`. Não será feita alteração manual de volume nem de credenciais.

## Bloqueio de publicação da infraestrutura

A alteração necessária no wrapper `/opt/infra/services/negobot-backend/Dockerfile` foi criada localmente em `/home/ubuntu/boomploy-infra` e commitada como `5fd9684`, mas o push para `https://github.com/VAMOS-tecnico/boomploy-infra.git` devolveu HTTP 403. A API da conta atual não consegue resolver o repositório, embora o nome esteja reservado no GitHub; as duas credenciais configuradas nesta sessão também não têm acesso de leitura ao repositório.

Nenhuma alteração foi aplicada na VPS pelo caminho alternativo. Para promover esta correção de forma segura, é necessário recuperar o acesso à conta/repositório original ou fornecer um repositório de infraestrutura acessível; não será usada uma edição manual de Dockerfile via SSH nem será recriado o serviço com risco para os volumes.
