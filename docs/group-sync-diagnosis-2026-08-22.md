# Diagnóstico de sincronização de grupos — 2026-08-22

A instância observada ainda está em estado `connecting`; enquanto não estiver `open`, a Evolution não tem sessão WhatsApp completa para devolver todos os grupos. Mesmo assim, foi encontrado um gargalo independente: o Incoming Worker CPX32 reiniciou 153 vezes e falhou num `CONNECTION_UPDATE` ao chamar `.set()` num `DocumentSnapshot`. A correcção converte os snapshots em `DocumentReference` antes da gravação, inclui teste de regressão e passou com 144 testes. Commit publicado: `2a8ed91`.

O utilizador autorizou o redeploy controlado do Incoming Worker CPX32 e do NEGOBOT Backend. O próximo passo é aplicar a imagem actualizada e confirmar que os reinícios cessam.

O cartão exacto foi localizado no Boomploy como `Negobot Incoming Worker (CPX32)` (`negobot-incoming-worker-cpx32`, actualmente `running`). A identificação foi feita pelo DOM para evitar seleccionar outro worker.

O Boomploy accionou o redeploy do `negobot-incoming-worker-cpx32` e do `negobot-backend`. Os cartões foram identificados pelo nome e pelo `data-service`, evitando afectar outros serviços. Falta confirmar os estados após o arranque.

Após o redeploy, o Backend ficou `running/healthy` com zero reinícios e o Incoming Worker CPX32 ficou `running` com zero reinícios desde 14:29. As filas Redis estavam vazias. A causa do crash foi corrigida.

A consulta final mostrou que a instância observada está actualmente em estado `close`; o endpoint `group/fetchAllGroups` devolveu HTTP 500 e nenhum grupo. Assim, a sincronização não está bloqueada por uma fila acumulada: a sessão WhatsApp precisa primeiro de voltar ao estado `open` através de um novo QR Code. Depois da leitura do QR, a sincronização inicial deve ser executada novamente.
