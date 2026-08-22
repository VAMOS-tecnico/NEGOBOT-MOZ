# Diagnóstico do QR Code — 2026-08-22

Os logs da Evolution API mostraram HTTP 400 ao configurar o webhook do Backend porque a lista enviada continha o evento inválido `GROUPS_UPDATE`. A enumeração da Evolution v2 aceita `GROUP_UPDATE`. O Backend abortava a função `criar_e_configurar_instancia_automatica` ao receber este erro e a rota do painel devolvia 502 antes de chamar `obter_qrcode_instancia`, impedindo a apresentação do QR Code.

Correcção aplicada em `services/evolution_service.py`: `GROUPS_UPDATE` foi substituído por `GROUP_UPDATE`. Foi acrescentado teste de regressão; a suite passou com 143 testes. Commit publicado: `172db7a`.

O redeploy foi autorizado pelo utilizador e accionado no cartão `NEGOBOT Backend` do Boomploy. Ainda falta confirmar o healthcheck e testar novamente a rota de conexão.

## Validação após redeploy

O Backend foi redeployado pelo Boomploy às 14:12 e ficou `running`, `healthy`, com zero reinícios. O código activo contém `GROUP_UPDATE` e já não contém `GROUPS_UPDATE`.

A consulta à instância previamente observada em estado `connecting` devolveu `HTTP 200` no endpoint `/instance/connect/...`, com um campo de QR Code presente e resposta de 13.559 bytes. O conteúdo do QR não foi impresso nem guardado. Falta confirmar a transformação na rota autenticada do painel.
