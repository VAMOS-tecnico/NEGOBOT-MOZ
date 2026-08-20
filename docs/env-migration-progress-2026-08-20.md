# Progresso da migração de ambientes — 20 de Agosto de 2026

## Estado intermédio

- AI Worker: contrato próprio com fornecedores de IA duplicados temporariamente; redeploy final confirmado em `running`, com log de arranque do perfil `ai`.
- Mailer Worker: contrato SMTP próprio duplicado temporariamente; redeploy final confirmado em `running`, com log de arranque do perfil `mailer`.
- Compose/infra: commit `74cfc4e` publicado em `boomploy-infra-recovered`, apontando Incoming, Campaign, Channel Publication e AutoPay para `.env.example` + `.env` próprios, e adicionando os dois cartões ausentes ao catálogo Boomploy.
- Channel Publication Worker: cartão criado pelo catálogo, ambiente preenchido, redeploy confirmado em `running`, sem traceback detectado.
- AutoPay Sync: cartão criado pelo catálogo, ambiente preenchido, redeploy confirmado em `running`, sem traceback detectado.
- Incoming Worker: ambiente reposto após a sincronização do catálogo, redeploy confirmado em `running`, sem traceback detectado.
- Backend, Evolution API, PostgreSQL e Redis: observados como `running` depois da sincronização; o endpoint público `/readyz` confirmou anteriormente Firebase e Redis `online`.
- Campaign Worker: depois do redeploy do ambiente isolado, permanece em `restarting`; ainda não foi feita remoção de variáveis do Backend nem novo redeploy adicional.

## Nota de segurança

Durante a primeira operação de cópia via interface, a associação dos campos foi inicialmente identificada como incorrecta. A escrita foi corrigida usando a estrutura real `label > input`, os valores foram restaurados a partir das variáveis correspondentes do Backend e AI/Mailer foram redeployados novamente antes da validação final. Nenhum valor de segredo foi incluído neste relatório.

## Diagnóstico e correcção adicional

Após o primeiro redeploy dos quatro workers legados, o Campaign e o AutoPay entraram em `restarting` porque os campos `FIREBASE_CONFIG` e algumas variáveis Evolution tinham sido preenchidos inicialmente com o nome da variável, não com o valor correspondente. A causa foi identificada no painel: a estrutura correcta é `label > input`, e não `label.parentElement > input`.

Os valores reais de Firebase/Evolution foram então recarregados do Backend depois de esperar pelo carregamento completo do cartão. Os defaults de perfil, Redis, filas, AutoPay e n8n foram definidos explicitamente; nenhum cartão mantém agora o nome da variável como valor. Os workers afectados estão a ser redeployados novamente, um por um. O Backend não foi apagado nem alterado, e os volumes persistentes não foram tocados.

## Estado após a segunda correcção

Depois de actualizar a observabilidade, o AutoPay Sync regressou a `running` e o cartão deixou de mostrar a falha de Firebase. Campaign e Channel Publication continuam em `restarting`; o painel já não detecta `FIREBASE_CONFIG` literal nesses cartões, pelo que a causa restante precisa de ser lida nos logs actuais antes de qualquer nova alteração.

## Recuperação parcial confirmada

Com os valores corrigidos, o AutoPay Sync arrancou com Firebase via JSON e registou `AutoPay Sync Worker iniciado`. O Channel Publication Worker também regressou a `running`, sem traceback ou erro de Firebase detectado.

O Campaign Worker continua em `restarting` mesmo após o redeploy corrigido. O painel não apresenta ainda um novo erro de Firebase no conteúdo actualizado; a próxima leitura deve confirmar se existe uma dependência adicional ou se o log apresentado é anterior ao processo actual.

## Verificação final desta etapa

No painel Boomploy (`https://boomploy.duckdns.org/`), o AutoPay Sync apresenta o arranque confirmado às 22:27:34 UTC com Firebase inicializado via JSON e o worker iniciado. O Channel Publication Worker apresenta o arranque confirmado às 22:28:58 UTC e está `running`. O Campaign Worker regressou a `running` após o redeploy corrigido; o painel ainda mostra “Sem logs” para o processo actual, mas não apresenta traceback no estado corrente.

O Incoming Worker continua em `restarting`. O log mostrado pelo painel termina às 22:24:55 UTC e corresponde ao processo anterior, que falhou ao interpretar `FIREBASE_CONFIG`; o cartão actual já não contém valores literais e precisa de um redeploy/refresh final para confirmar o processo corrigido.

## Health checks finais

Os endpoints públicos confirmaram `GET /healthz -> {"status":"ok"}` e `GET /readyz -> {"status":"ready","checks":{"firebase":"online","redis":"online"}` após os redeploys isolados. Não foram reiniciados volumes persistentes, Evolution API, PostgreSQL ou Redis por uma acção manual de migração.

## Início da migração permanente de IA

O commit `64f589a` substitui as chamadas directas de geração de texto por jobs em `negobot:ai_jobs`, com resultados em `negobot:ai:result:<job_id>` e validação de `tenant_id`. O Backend continua a usar temporariamente chaves de IA para transcrição de áudio e compatibilidade, mas já não há chamadas directas de geração de texto nos fluxos WhatsApp, grupos, cliente, Assistente público ou helper de prompts de imagem.

Antes do redeploy do AI Worker, o painel Boomploy mostrou Backend, AI Worker, Incoming, Campaign, Channel Publication, AutoPay, Mailer, Image, Audio, Social, Video Service e Video Worker em `running`; PostgreSQL, Redis, Evolution e n8n também estavam `running`. O próximo passo operacional é redeployar apenas o AI Worker para carregar a versão que consome o contrato de jobs.

## Smoke test da fila AI

Foi executado um POST para `https://negobot-api.duckdns.org/api/platform/public/assistant/chat` com uma pergunta não determinística sobre o NEGOBOT-MOZ. O endpoint devolveu HTTP bem-sucedido com uma resposta gerada, indicando que o Backend publicou o job, o AI Worker processou a mensagem e o resultado foi devolvido ao cliente. O teste não expôs chaves nem valores de ambiente.

## Remoção de SMTP do Backend

Depois do commit `9fb0da9`, a auditoria do cartão Backend no Boomploy encontrou as sete variáveis SMTP (`SMTP_FROM`, `SMTP_HOST`, `SMTP_PASSWORD`, `SMTP_PORT`, `SMTP_TIMEOUT_SECONDS`, `SMTP_USER`, `SMTP_USE_TLS`). O cartão não apresenta botão individual de remoção. Não será feita uma gravação destrutiva por manipulação visual até confirmar, no código do painel, se “Guardar variáveis” substitui o ficheiro completo ou apenas faz merge; o objectivo é não apagar variáveis não relacionadas.

## SMTP removido do Backend

O painel confirmou 53 variáveis carregadas, todas com valor, sendo 46 não-SMTP e 7 SMTP. Foi guardado no cartão `negobot-backend` exactamente o mapa não-SMTP. A resposta do painel confirmou `saved=true`, `keyCount=46` e `removedSmtp=true`; a operação não marcou `applied` porque o endpoint de guardar apenas escreve o `.env` e pede reinício separado. O Mailer Worker mantém o seu contrato SMTP próprio.

## Validação após remoção de SMTP

O redeploy do Backend foi concluído pelo cartão Boomploy. Os endpoints confirmaram `GET /healthz -> {"status":"ok"}` e `GET /readyz -> {"status":"ready","checks":{"firebase":"online","redis":"online"}}`. A recuperação de palavra-passe agora apenas publica jobs para o Mailer Worker; o Backend não lê nem envia SMTP directamente.

## IA removida do Backend e Incoming

Depois da migração de texto e áudio, o Boomploy guardou o Backend sem as chaves/modelos de Groq, Cerebras, SambaNova, Gemini, GitHub Models, Mistral e OpenRouter. O cartão confirmou `saved=true`, `keyCount=30` e nenhuma das chaves-alvo permaneceu. O Incoming Worker foi guardado sem `GROQ_API_KEY` e `OPENROUTER_API_KEY`, com `keyCount=8`; ambos aguardam apenas o redeploy automático/separado para carregar os novos ambientes.

O AI Worker continua a ser o único serviço com as chaves de fornecedores de IA. As chaves SMTP continuam exclusivamente no Mailer Worker.

## Pós-redeploy de IA

O Backend e o Incoming Worker regressaram a `running` sem `EnvironmentContractError`. O Backend não apresenta traceback. O painel ainda sinaliza `traceback=true` no cartão Incoming; esse indicador pode incluir linhas antigas, por isso o log actual será lido antes de qualquer rollback ou nova alteração.

## Diagnóstico do traceback do Incoming

A linha de traceback apresentada pelo painel era anterior ao redeploy (`22:36:05Z`). O final do log actual contém uma inicialização normal às `23:03:47Z`, com Firebase inicializado e consumidor online nas filas `whatsapp_incoming_queue,omnichannel_incoming_queue`; o cartão permanece `running`. Não foi necessária alteração de Redis nem rollback.

## Validação final da migração permanente

A suite completa terminou com `130 tests ... OK`. Em produção, `/healthz` devolveu `{"status":"ok"}` e `/readyz` devolveu `{"status":"ready","checks":{"firebase":"online","redis":"online"}}`. O Assistente público respondeu depois de o Backend ficar sem as chaves dos fornecedores, confirmando o percurso Backend -> `negobot:ai_jobs` -> AI Worker.

O AI Worker foi redeployado depois do commit `343299b` para carregar o handler `audio_transcription`; o cartão Boomploy está `running` e o log actual não contém `Traceback` nem `EnvironmentContractError`. Os artefactos não relacionados que estavam no working tree não foram incluídos nos commits desta migração.
