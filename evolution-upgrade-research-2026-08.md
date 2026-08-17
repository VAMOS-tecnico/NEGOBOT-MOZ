# Pesquisa para atualização da Evolution API — 2026-08

## Fontes oficiais consultadas

1. Releases: https://github.com/evolution-foundation/evolution-api/releases
2. Issue #2550: https://github.com/evolution-foundation/evolution-api/issues/2550

## Conclusões verificadas

- A instalação atual usa Evolution API v2.3.7.
- A release 2.4.0-rc2 continua identificada pelo projeto como pre-release candidate, construída a partir de `develop` e não fundida em `main`; a própria nota recomenda validação e não autoriza colocá-la diretamente em produção sem testes.
- A release 2.4.0 introduz uma alteração importante: ativação/licenciamento obrigatório para servir tráfego da API, além de uma migração de base de dados que cria a tabela `RuntimeConfig`; a nota indica `npm run db:deploy` como etapa obrigatória.
- O issue #2550 confirma que o erro ocorre em áudio recebido de iOS com `ptt: true` e MIME `audio/ogg; codecs=opus`, ao chamar `POST /chat/getBase64FromMediaMessage/{instance}`. O erro observado é `Cannot read properties of undefined (reading 'ephemeralMessage')` e o download direto devolve um ficheiro `.enc` encriptado.
- O issue #2550 foi associado aos Pull Requests #2551 e #2552, descritos como correções para tratar `ephemeralMessage` indefinido em áudio PTT de iOS. A issue permanece aberta na fonte consultada, portanto a existência desses PRs não deve ser tratada como prova de uma release estável já validada.
- A release 2.4.0-rc2 menciona correções de áudio no envio (`sendWhatsAppAudio` com `quoted`), mas isso é diferente do problema de recuperação/base64 de áudio recebido que afeta a transcrição do NEGOBOT-MOZ.

## Decisão provisória

Não atualizar diretamente a produção para `2.4.0-rc2`. Primeiro é necessário confirmar uma release estável posterior, verificar se ela inclui os commits #2551/#2552 ou uma correção equivalente, criar backup verificável, testar numa instância isolada e só depois executar uma migração controlada com rollback preparado.

## Estado dos PRs relacionados

- PR #2551: https://github.com/evolution-foundation/evolution-api/pull/2551 — **Closed**, direcionado para `evolution-foundation:develop`, com o commit `bef8c81`. A alteração adiciona guarda para `msg.message` falso e optional chaining em `msg.message[subtype]?.message`.
- PR #2552: https://github.com/evolution-foundation/evolution-api/pull/2552 — **Open**, também direcionado para `develop`, com a mesma linha de correção para o endpoint de recuperação de base64.
- O estado dos PRs não prova, por si só, que a correção esteja numa imagem Docker estável. É necessário localizar uma tag/release posterior que contenha o commit e validar a imagem efetivamente publicada antes do upgrade.

## Catálogo Docker consultado

Fonte: https://hub.docker.com/r/evoapicloud/evolution-api/tags

No momento da consulta, o catálogo mostra `homolog`, `2.4.0-rc2`, `2.4.0-rc1`, `latest`, `v2.3.7` e versões anteriores. Não foi observada uma tag estável numerada posterior à `v2.3.7`. A tag `latest` aparece separada dos releases nomeados e não deve ser usada em produção sem fixar e validar o digest. A imagem `2.4.0-rc2` tem digest `sha256:0589281d448736759b98d11071066a3b9be3a1f19724802dd5867d9608a9584b` para amd64, mas continua sendo release candidate e a documentação da própria release desaconselha produção sem validação.

## Diagnóstico Groq versus Evolution — 2026-08

Foi executado um probe temporário dentro do container `negobot-backend` usando a chave já existente no ambiente, sem imprimir o seu valor. O probe gerou um WAV PCM mono válido a 16 kHz e chamou o endpoint Whisper com `whisper-large-v3`, `language=pt` e multipart `file`.

Resultado: `HTTP_STATUS=200`, resposta JSON válida e sem erro (`error: null`). O texto devolvido foi praticamente vazio, como esperado para um tom sem fala, mas a aceitação HTTP confirma que a autenticação, o endpoint, o modelo e o formato multipart do Groq estão operacionais.

Conclusão provisória: a falha das mensagens de voz reais não é um problema geral da chave ou do endpoint Groq. O ponto provável continua a ser a recuperação/decodificação do áudio pela Evolution antes de o ficheiro chegar ao Whisper. O Groq pode devolver HTTP 400 quando recebe bytes que não correspondem a um formato de áudio válido, mesmo que o webhook indique `audio/ogg; codecs=opus`.

Foi executado um segundo probe com bytes OGG inválidos e o mesmo endpoint/modelo: `HTTP_STATUS=400`, com `invalid_request_error` e a mensagem `could not process file - is it a valid media file?`. A diferença entre `200` para o WAV válido e `400` para bytes inválidos reproduz exatamente o padrão esperado quando a Evolution entrega conteúdo corrompido/encriptado ao backend.
