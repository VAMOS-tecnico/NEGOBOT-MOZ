# Plano de modularização segura do NEGOBOT MOZ

## Objectivo

A modularização será feita no Boomploy actualmente usado em produção, sem migração imediata para Dokploy. O objectivo não é criar microserviços por moda; é reduzir o blast radius, impedir que uma credencial ou falha de um domínio derrube todos os processos e tornar explícito que cada worker tem uma responsabilidade única.

Ter muitas variáveis num processo não torna, por si só, o Python pesado. O problema real é a combinação de segredos desnecessários, inicializações partilhadas, dependências opcionais tratadas como obrigatórias, filas com consumidores duplicados e redeploys que afectam serviços que não mudaram.

## Arquitectura alvo incremental

| Serviço | Responsabilidade | Filas | Variáveis permitidas, por grupo |
|---|---|---|---|
| `negobot-api` | HTTP, autenticação, tenants, planos, billing commands, OAuth start/callback, health e enqueue | Redis para controlos e enqueue | Firebase, Redis, sessão/plataforma, URLs públicas, configuração de billing/OAuth apenas enquanto as rotas ainda não forem extraídas |
| `whatsapp-ingress` | Consumo de eventos Evolution, deduplicação persistente, CONNECTION_UPDATE, trial, grupos, áudio e fluxo central/cliente | `WHATSAPP_INCOMING_QUEUE` | Firebase, Redis, Evolution, IA de conversação, números e filas WhatsApp |
| `campaign-worker` | Única implementação de campanhas, opt-in, STOP/PARAR/SAIR, limites, atrasos, grupos autorizados e agendamento | `negobot:campaigns`, fila scheduled e locks | Firebase, Redis, Evolution e n8n opcional |
| `channel-publication-worker` | Publicações agendadas em Channels/canais autorizados | `CHANNEL_PUBLICATIONS_QUEUE` e scheduled | Firebase, Redis e adaptadores de publicação |
| `omnichannel-worker` | Eventos normalizados de Meta, TikTok, X, LinkedIn e Telegram; nunca afirmar envio sem adapter confirmado | `OMNICHANNEL_INCOMING_QUEUE` e fila omnichannel de saída | Firebase, Redis e OAuth/segredos dos canais |
| `billing-worker` | AutoPay/M-Pesa e webhooks Lemon Squeezy | fila de pagamentos | Firebase, Redis, M-Pesa/AutoPay e Lemon Squeezy |
| `video-service` + `video-worker` | Criação e processamento de jobs de vídeo | `VIDEO_QUEUE` | Redis, `VIDEO_SERVICE_TOKEN`, `VIDEO_OUTPUT_DIR` e callback interno |

## Regra para filas

Cada fila de produção terá um consumidor principal. O `platform_worker.py` é legado e não pode continuar a consumir `negobot:campaigns` em paralelo com `campaign_worker.py`, porque as duas implementações têm regras diferentes para consentimento, estado, limites e destinatários. A primeira alteração operacional será tornar `campaign_worker.py` a única implementação autorizada; o ficheiro legado permanecerá temporariamente no repositório apenas para facilitar rollback de código, mas não será referenciado pelo Compose.

Os envelopes Redis devem continuar a carregar `tenant_id`, `event_id`, `request_id`, `channel`, `conversation_id` e `received_at`. O worker deve persistir o evento antes do processamento demorado e usar locks/ids idempotentes; uma falha ou retry não pode produzir uma segunda mensagem para o mesmo evento.

## Variáveis e segredos

O `.env` actual do Backend será tratado como fonte de migração, não como ambiente final de todos os serviços. Será criado um allowlist por serviço. Variáveis comuns como `REDIS_URL` e Firebase só serão replicadas quando o serviço realmente precisar delas. Segredos de Evolution ficam no ingress/campaign worker; OAuth fica no omnichannel worker; pagamentos ficam no billing worker; vídeo fica no video-service/worker; SMTP fica apenas no API de recuperação de palavra-passe até ser extraído.

Nenhum valor será versionado. O repositório conterá apenas nomes, defaults não sensíveis, validação e documentação. A geração dos `.env` isolados ocorrerá no servidor/Dokploy/Boomploy a partir do gestor de variáveis, com permissões restritas e sem imprimir valores nos logs.

## Ordem de implementação

A primeira etapa é de baixo risco: padronizar o Compose para um único consumidor de campanhas, adicionar contratos de configuração e documentar a matriz. A segunda etapa cria health checks e validação de ambiente por processo. A terceira extrai o gateway de webhook para apenas validar, normalizar e enfileirar; o processamento continua no worker WhatsApp existente. A quarta separa billing, omnichannel e vídeo com filas próprias. A quinta remove variáveis não utilizadas de cada serviço, depois de uma janela de observação e rollback.

Cada etapa terá testes unitários, testes de contrato dos envelopes, teste de isolamento por tenant, teste de duplicação/idempotência, validação de sintaxe, `git diff --check`, build React e smoke test HTTP. A publicação será feita por serviço; Evolution, PostgreSQL, Redis e volumes persistentes não serão redeployados quando não forem afectados.

## Condições de segurança

A modularização não altera a regra de trial único, não cria QR adicional, não permite campanhas sem `opt_in`, não relaxa STOP/PARAR/SAIR e não permite grupos sem autorização e privilégio de administrador. Todos os webhooks continuam a exigir assinatura/secret próprio e os dados continuam filtrados por `tenant_id`.

A migração para Dokploy só será feita como projecto separado, depois de a arquitectura estabilizar no Boomploy. Fazer as duas mudanças ao mesmo tempo dificultaria distinguir falhas de aplicação de falhas da plataforma de deploy.


## Extensão da arquitectura para os domínios de produto solicitados

A divisão seguinte é uma extensão progressiva do desenho anterior. Um serviço só será activado quando existir um entrypoint funcional, uma fila ou API interna definida, um contrato de ambiente e um health check. Não serão criados containers “decorativos” que apenas mantêm um processo Python ocioso.

| Serviço alvo | Responsabilidade isolada | Entrada principal | Variáveis exclusivas | Estado inicial |
|---|---|---|---|---|
| `negobot-core` | API Gateway, autenticação, tenants, planos, comandos e health | HTTP público | Firebase, Redis, sessão, URLs públicas e contratos internos | migrar primeiro |
| `negobot-campaign-worker` | Campanhas, opt-in, STOP/PARAR/SAIR, limites, atrasos e agendamento | `negobot:campaigns` | Firebase, Redis, Evolution, n8n opcional | existente |
| `negobot-incoming-worker` | Webhooks Evolution, deduplicação, CONNECTION_UPDATE e normalização WhatsApp | `whatsapp_incoming_queue`, `omnichannel_incoming_queue` | Firebase, Redis, Evolution e IA de conversação durante a transição | existente |
| `negobot-ai-worker` | Pool LLM, respostas assistidas e roteiros | `negobot:ai_jobs` | Redis, modelos/chaves de IA e limites | criar com feature flag |
| `negobot-image-worker` | Jobs de imagens e edição | `negobot:image_jobs` | Redis e credenciais de fornecedor configuradas | disabled até existir adapter |
| `negobot-video-worker` | API e renderização de vídeo/avatar | `negobot:video_jobs` | Redis, token interno, output e FFmpeg | código existente; ligar depois |
| `negobot-audio-worker` | TTS e áudio | `negobot:audio_jobs` | Redis, Edge TTS ou fornecedor de voz configurado | criar após contrato |
| `negobot-social-poster` | Publicações autorizadas em redes sociais | `negobot:social_jobs` | Redis, OAuth cifrado/adaptadores e scopes | pending approval |
| `negobot-mailer` | E-mail transaccional e alertas | `negobot:mail_jobs` | Redis, SMTP e TTL de reset | extrair depois de estabilizar reset |

Durante a transição, o Core poderá conservar temporariamente uma variável de integração que ainda seja necessária pelas rotas existentes. A redução para aproximadamente dez variáveis só será declarada concluída depois de as chamadas directas a Evolution, IA, vídeo e SMTP terem sido substituídas por comandos internos ou jobs idempotentes.

### Contrato comum de jobs

Cada job deve conter `job_id`, `tenant_id`, `request_id`, `idempotency_key`, `created_at`, `attempt`, `kind`, `payload` e `callback`. O worker deve validar o tenant antes de ler ou escrever dados, persistir o estado `queued` antes do processamento, usar uma chave de deduplicação e publicar estados `processing`, `completed` ou `failed` sem revelar segredos. Jobs desconhecidos são rejeitados e enviados para uma fila de erro, nunca executados silenciosamente.

### Política de activação

Os novos serviços serão adicionados inicialmente com `profiles: ["microservices-stage"]` ou equivalente, sem serem iniciados no deploy normal. Depois de os `.env` isolados serem preenchidos no Boomploy e os testes de contrato passarem, cada serviço será activado individualmente. O Core, Redis, PostgreSQL, Evolution e volumes persistentes não serão reiniciados por causa de um worker que ainda esteja em validação.

### Dimensionamento conservador

A VPS actual tem 2 vCPU e aproximadamente 3,7 GiB de RAM. A arquitectura não deve iniciar nove processos concorrentes por defeito. Os workers CPU-heavy terão concorrência 1, os workers de I/O terão um processo com polling bloqueante e os jobs de vídeo/imagem serão limitados por fila. A primeira versão deve preferir serviços sob demanda e limites explícitos a uma multiplicação indiscriminada de containers.
