# Runbook de confiabilidade e modularização do NEGOBOT MOZ

## Princípio operacional

Uma alteração de código não deve reiniciar todos os serviços. O serviço afectado deve ser reconstruído isoladamente, deve passar o healthcheck e só depois os workers dependentes devem ser actualizados. Evolution API, PostgreSQL, Redis e volumes persistentes ficam fora da operação salvo quando a alteração os afectar directamente.

## Perfis de ambiente

Cada processo tem um contrato próprio em `services/service_config.py`. O contrato verifica apenas presença de variáveis e nunca escreve valores nos logs. O API usa `NEGOBOT_SERVICE_PROFILE=api` no Compose; os workers validam directamente os perfis `whatsapp_ingress`, `campaign`, `channel_publication`, `billing` e `video` antes de iniciar.

Quando uma variável obrigatória falta, o processo termina com uma mensagem de nomes, não com uma tentativa parcial. Isto evita que um processo pareça saudável enquanto rejeita eventos em segundo plano.

## Health checks

O API expõe `/healthz` para liveness e `/readyz` para readiness. `/healthz` responde apenas se o processo Flask está vivo. `/readyz` verifica presença de Firebase inicializado e conectividade Redis, devolvendo `503` quando não está pronto. O Compose do Backend executa `/healthz` como healthcheck Docker com período inicial de 30 segundos, cinco tentativas e intervalo de 15 segundos.

Workers não expõem portas públicas. O seu estado deve ser verificado pelos logs sanitizados do processo e pela presença de consumidores nas filas. Nenhum teste de produção deve criar contas, pagamentos ou mensagens reais.

## Filas e idempotência

`campaign_worker.py` é o consumidor único de `negobot:campaigns`. `platform_worker.py` foi aposentado e falha explicitamente se alguém tentar iniciá-lo, evitando uma execução histórica duplicada com regras diferentes. O worker de entrada consome as filas WhatsApp e omnichannel, enquanto o worker de publicações mantém a fila de Channels separada.

As mensagens e campanhas continuam a ser filtradas por `tenant_id`. Os locks de campanha e os estados de destinatário devem ser mantidos; não remover locks, validações de `opt_in`, consentimento STOP/PARAR/SAIR ou autorização de grupos.

## Procedimento de publicação

Antes da publicação, executar a suite Python completa, a compilação Python, `git diff --check`, o build React quando houver alteração de frontend e a validação YAML do Compose. Confirmar que a fila afectada tem um único consumidor. Criar o commit e publicar no GitHub.

No Boomploy, reconstruir apenas o serviço alterado. Para o API e workers NEGOBOT, confirmar o catálogo de serviços antes da acção; se um worker não aparecer no painel, não usar o cartão do Site como substituto. Actualizar o catálogo do Boomploy separadamente e só depois disponibilizar o worker como cartão próprio.

Depois do redeploy, aguardar o estado `running`, consultar `/healthz` e `/readyz`, observar logs de arranque e validar os estados dos serviços não afectados. Se o Backend ou um worker não ficar saudável, parar a promoção seguinte e fazer rollback para o último commit conhecido, sem apagar volumes.

## Rollback

O rollback deve restaurar o último commit estável e reconstruir apenas os serviços alterados. Não remover contentores de PostgreSQL, Redis, Evolution ou vídeo se a alteração não for deles. Não substituir `.env` por uma cópia antiga sem confirmar a origem e a validade dos segredos; variáveis de ambiente são restauradas através do gestor do Boomploy, nunca pelo Git.

## Estado actual da primeira etapa

A primeira etapa está publicada nos commits `5156a3c`, `ad43274` e `f83e775` do NEGOBOT-MOZ, no commit `e2012fb` da infraestrutura e no commit `dd9dabd` do catálogo Boomploy. A suite passou com 119 testes depois dos health checks. O Backend foi validado como `running`; a disponibilização dos cartões dos workers depende da reconstrução do próprio painel Boomploy, que não possui um endpoint de redeploy para o serviço `boomploy`.
