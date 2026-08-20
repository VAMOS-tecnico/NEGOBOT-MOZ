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
