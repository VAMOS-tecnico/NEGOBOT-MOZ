# Relatório de integração e publicação do painel do cliente

**Projecto:** NEGOBOT-MOZ  
**Data:** 21 de Agosto de 2026  
**Autor:** Manus AI

## Resultado executivo

O painel do cliente foi actualizado para mostrar, de forma tenant-scoped e sem expor segredos, o estado das ligações que sustentam o workspace: WhatsApp/Evolution, Redis, automação de campanhas, pagamentos locais e internacionais, além dos workers de IA, imagem, áudio, social, email, vídeo e campanhas.

O `Campaign Worker` passou a publicar um heartbeat e um indicador não secreto de configuração do n8n no Redis. O backend lê estes estados através da fila partilhada, enquanto os segredos continuam isolados nos serviços proprietários. O frontend apresenta os estados em português ou inglês conforme o selector do painel.

## Causa encontrada durante a publicação

O primeiro redeploy do Site reiniciou o contentor, mas o cartão `NEGOBOT Site` no Boomploy não tinha a definição de `build_context` e sincronização de origem. Consequentemente, o contentor arrancava com uma imagem anterior e o novo bundle React não aparecia no domínio `app-negobotmoz.duckdns.org`.

A definição do serviço foi corrigida para sincronizar o repositório autorizado, reconstruir com contexto GitHub e executar um build sem cache para o Site. Depois da correcção, o bundle publicado passou de um hash antigo para `index-CYVngV2u.js`, contendo a marca `SERVICE CONNECTIONS` da nova interface.

## Commits publicados

| Repositório | Commit | Alteração |
|---|---|---|
| `VAMOS-tecnico/NEGOBOT-MOZ` | `e649f2f` | Estado das integrações no painel e heartbeat do Campaign Worker |
| `VAMOS-tecnico/NEGOBOT-MOZ` | `0aaa751` | Relatório de auditoria das integrações |
| `VAMOS-tecnico/boomploy-infra-recovered` | `c380d24` | Sincronização e build do NEGOBOT Site no redeploy |
| `VAMOS-tecnico/boomploy-infra-recovered` | `ad843b1` | Build do Site sem cache para impedir imagens antigas |

## Redeploy executado

O redeploy foi feito faseadamente pelo Boomploy. Foram actualizados o Backend, o Campaign Worker e o Site. O controlador Boomploy foi reconstruído automaticamente pelo sincronizador GitHub após as alterações no repositório privado. Não foram reiniciados PostgreSQL, Redis, Evolution API ou n8n durante esta correcção, e não foram alterados volumes persistentes.

## Validação final

| Verificação | Resultado |
|---|---|
| Backend `/healthz` | `{"status":"ok"}` |
| Backend `/readyz` | `ready`; Firebase e Redis `online` |
| Painel `/plataforma/login` | HTTP 200 |
| Site público `negobotmoz.duckdns.org` | HTTP 200 |
| Bundle React live | Novo bundle com `SERVICE CONNECTIONS` presente |
| Webhook n8n | HTTP 200; workflow iniciado |
| Testes backend | 130/130 aprovados |
| TypeScript | `tsc --noEmit` aprovado |
| Build React | Vite build aprovado |
| Isolamento de segredos | Mantido; o painel recebe apenas estados derivados |

A validação visual autenticada de um workspace de cliente não foi executada porque este navegador não tinha uma sessão de cliente disponível. A entrega pública do bundle, o login do painel e os contratos de backend foram verificados; o cartão completo aparece depois de um cliente autenticado carregar o dashboard.

## Limitações externas mantidas deliberadamente

Meta, TikTok, X e LinkedIn continuam dependentes de OAuth, aprovação do fornecedor, permissões e eventos reais por conta do cliente. O Social Poster mantém o estado de revisão pendente quando o adaptador externo não está configurado. O WhatsApp continua a ser o canal de referência via Evolution API. O n8n recebe campanhas e responde correctamente, mas a entrega final em cada rede continua sujeita ao adaptador e às credenciais autorizadas desse canal.
