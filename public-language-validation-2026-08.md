# Validação PT/EN do site público

Data: 17 de agosto de 2026.

O build React foi executado com `pnpm exec tsc --noEmit` e `pnpm build`, sem erros. A pré-visualização foi aberta no browser em PT e o botão `EN` foi acionado.

Em inglês, foram confirmadas a navegação `Capabilities`, `Plans`, `How it works`, `Contact`, o CTA `Talk to an assistant`, o hero `More answers. More business.`, capacidades, planos, benefícios, fluxo de funcionamento e chamadas finais. O seletor mostra `PT / EN` e o idioma é guardado em `localStorage` com a chave `negobot-public-language`.

O mesmo seletor foi adicionado à página pública `/assistente`. A preferência é aplicada também ao atributo `document.documentElement.lang`, permitindo melhor acessibilidade e indexação.

## Publicação

O seletor bilingue foi publicado no commit `fd1c7ad` da branch `main`. O redeploy foi iniciado exclusivamente no cartão `NEGOBOT Site` do Boomploy. Evolution API, n8n, backend, PostgreSQL, Redis e volumes persistentes não foram redeployados nesta etapa.

## Correção do sincronizador

Foi identificada e corrigida a decisão de rebuild em `deploy/sync-main.sh`: quando `services/negobot-backend/source/` muda, o comando passa a reconstruir `negobot-backend` e `negobot-site`. A alteração foi aplicada no editor CodeMirror e verificada no texto completo do script.

O commit do `sync-main.sh` foi submetido diretamente na branch `main` através do editor autenticado do GitHub. A próxima verificação confirmará a revisão remota antes do timer de sincronização.

A página de leitura do GitHub apresentou temporariamente o erro Unicorn/"No server is currently available". A confirmação remota do commit ficou pendente de nova tentativa; não foram executadas novas alterações durante a indisponibilidade.

A verificação do editor carregado a partir da branch `main` confirmou `hasSite: true` para `--build negobot-backend negobot-site` e não encontrou a linha antiga. O commit da infraestrutura está efetivamente gravado; falta aguardar a próxima sincronização automática e validar o domínio.

## Diagnóstico do build final

O projeto `prj_negobot_moz` foi clonado com sucesso e terminou `live` na porta temporária 5001. Contudo, o domínio público continuou a devolver a página antiga, indicando que o `negobot-site` ainda estava a construir a partir de `/opt/infra/services/negobot-backend/source`, que não foi atualizado pelo timer. A correção seguinte aponta o contexto do site para o checkout persistente do projeto Boomploy, que já recebe a `main` atualizada.

## Contexto persistente do site

O Compose foi alterado de `./services/negobot-backend/source` para `/opt/boomploy/data/runtime/projects/prj_negobot_moz/source` apenas no serviço `negobot-site`. Esse diretório é o checkout persistente que o projeto Boomploy atualiza através da branch `main`; a alteração foi verificada no editor antes do commit.

A alteração do Compose foi submetida no GitHub. Após a submissão, a instância CodeMirror deixou de estar disponível para leitura no DOM, pelo que a confirmação final será feita pela página remota do ficheiro e pelo comportamento do redeploy.

A leitura da branch `main` confirmou `hasPersistent: true` e `hasOld: false` no Compose. O `negobot-site` agora constrói a partir do checkout persistente `prj_negobot_moz`, que contém o React bilingue atualizado.

O primeiro caminho absoluto não era acessível ao cliente Docker. Foi ajustado para `/var/lib/boomploy/projects/prj_negobot_moz/source`, correspondente ao volume persistente configurado pelo Boomploy. A substituição foi aplicada e verificada no editor remoto.

O commit do caminho `/var/lib/boomploy/projects/prj_negobot_moz/source` foi submetido diretamente na branch `main`. A validação seguinte confirmará a versão carregada e depois será feito o redeploy apenas do site.

Após o commit, o DOM do editor deixou de expor a instância CodeMirror; a confirmação operacional será feita pelo redeploy e pelos logs do serviço, que são a validação efetiva do Compose aplicado.

## Resolução definitiva do contexto de build

O contexto de build foi alterado para o URL remoto do repositório `https://github.com/VAMOS-tecnico/NEGOBOT-MOZ.git#main`, eliminando a dependência de qualquer caminho local ou volume do servidor. O sincronizador `sync-main.sh` foi corrigido para executar `docker compose up -d --build negobot-backend negobot-site negobot-worker negobot-autopay-sync` quando o Compose ou o código NEGOBOT muda. A definição do serviço `negobot-site` foi marcada com `build_context=true` no `boomploy/app/services.py`, fazendo com que o botão de re-deploy do painel passe `--build`.

## Resultado final em produção

Após o re-deploy forçado com `--build`, `https://negobotmoz.duckdns.org/` passou a responder com a aplicação React (`#root`), sem o HTML legado. A página foi aberta no navegador e mostrou o seletor `PT / EN`, os planos e os CTAs. O botão `EN` foi testado e mudou o conteúdo para inglês, incluindo `More answers. More business.`, `Capabilities`, `Plans` e os planos Basic/Growth/Premium. O endpoint `/health` respondeu `{"service":"negobot-site","status":"online"}`.

Todos os serviços persistentes (Evolution API, n8n, PostgreSQL, Redis e volumes Docker) permaneceram intactos durante todo o processo.

## Porta do projeto Boomploy

A configuração de `prj_negobot_moz` foi restaurada para `port=5000`. A API confirmou HTTP 200, `project_status=live` e `managed_service=negobot-backend`; nenhum novo deploy do projeto foi iniciado por esta alteração.
