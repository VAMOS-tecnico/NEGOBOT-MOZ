# Matriz de auditoria de variáveis e chaves — NEGOBOT-MOZ

**Data:** 20 de Agosto de 2026  
**Objectivo:** definir exactamente a propriedade operacional de cada variável sem alterar ou apagar segredos.

> **Regra de segurança:** esta auditoria contém apenas nomes de variáveis. Nenhum valor de `.env`, token, API key, password ou conteúdo Firebase foi incluído.

## 1. Conclusão executiva

A arquitectura já possui contratos isolados para AI, Image, Audio, Social, Mailer e Video. Contudo, o Compose de produção ainda monta o `.env` do Backend nos workers legados **Incoming, Campaign, Channel Publication e AutoPay**. Além disso, o Backend ainda lê directamente os fornecedores de IA e o SMTP para recuperação de palavra-passe. Por isso, a matriz distingue entre **destino final** e **estado actual**.

A recomendação é não apagar variáveis agora. Primeiro devem ser adicionadas ao serviço de destino, depois o fluxo deve ser mudado para usar esse serviço, em seguida devem ser executados testes e só então a variável antiga pode ser removida do Backend.

### Estados usados

| Estado | Significado |
|---|---|
| **Manter** | A variável pertence ao serviço indicado e já é necessária nesse processo. |
| **Migrar** | A variável deve sair do Backend depois de o fluxo passar a usar o serviço de destino. |
| **Duplicar temporariamente** | A variável deve existir nos dois serviços durante a transição e só depois ser removida do Backend. |
| **Remover** | A variável é legado, alias não utilizado ou segredo colocado no serviço errado. |
| **Condicional** | Só deve ser adicionada quando a integração ou fornecedor estiver realmente activado. |

## 2. Backend Core — variáveis que devem permanecer

Estas variáveis suportam o núcleo Flask, autenticação, Firebase, tenant isolation, pagamentos/webhooks, controlos administrativos e compatibilidade de rotas que ainda não foram extraídas.

| Variáveis exactas | Estado | Justificação |
|---|---|---|
| `NEGOBOT_SERVICE_PROFILE` (`api`) | Manter | Selecciona o contrato do processo API. |
| `PORT` | Manter | Porta interna do processo Flask/Gunicorn. |
| `PLATFORM_SECRET_KEY` | Manter | Assinatura da plataforma e derivação de cifragem quando não existe chave Telegram dedicada. |
| `ADMIN_TOKEN` | Manter temporariamente | Fallback de autenticação administrativa e compatibilidade do painel Boomploy. Deve ser substituído por um mecanismo administrativo dedicado no futuro. |
| `FIREBASE_CONFIG` **ou** `FIREBASE_BASE64` **ou** `FIREBASE_CONFIG_B64` | Manter, escolher um formato | Credencial de Firebase/Firestore. Não manter os três formatos preenchidos ao mesmo tempo. |
| `REDIS_URL` | Manter | Health checks, filas, idempotência, campanhas, pagamentos e operações tenant-scoped do Backend. |
| `PASSWORD_RESET_TTL_MINUTES` | Manter | TTL dos tokens de recuperação de palavra-passe. |
| `MAX_UPLOAD_BYTES` | Manter | Limite de uploads HTTP do Backend. |
| `PUBLIC_APP_BASE_URL` | Manter | Links de recuperação de palavra-passe e links da plataforma enviados aos clientes. |
| `PUBLIC_API_BASE_URL` | Manter | Redirects OAuth e callbacks públicos da API. |
| `ADMIN_NUMBER` | Manter | Alertas administrativos e operações autorizadas. |
| `ASSISTANT_NUMBER` | Manter | Identidade do assistente central e regras de trial/WhatsApp. |
| `EVOLUTION_API_URL` | Manter temporariamente | Ainda usado por rotas de QR, estado de conexão, grupos e operações WhatsApp do Backend. |
| `EVOLUTION_API_KEY` | Manter temporariamente | Ainda usado pelas mesmas rotas e pelo adaptador Evolution do Backend. |
| `EVOLUTION_INSTANCE_NAME` | Manter | Distingue a instância central de instâncias de clientes em webhooks e operações WhatsApp. |
| `WEBHOOK_URL` | Manter | Configuração de webhook Evolution usada pelo adaptador WhatsApp. |
| `TIMEOUT_HUMANO_MINUTOS` | Manter | Regras de transferência para atendimento humano. |
| `TELEGRAM_TOKEN_ENCRYPTION_KEY` | Manter condicional | Chave dedicada para cifrar tokens Telegram no Firestore. Se ausente, o código deriva a chave de `PLATFORM_SECRET_KEY`/`ADMIN_TOKEN`; o formato dedicado é recomendado. |
| `META_VERIFY_TOKEN` | Manter condicional | Verificação de webhooks Meta enquanto os endpoints forem propriedade do Backend. |
| `X_CONSUMER_SECRET` | Manter condicional | CRC/validação de webhook X enquanto o endpoint estiver no Backend. |
| `TELEGRAM_WEBHOOK_SECRET` e `*_WEBHOOK_SECRET` por canal | Manter condicional | Secrets de verificação dos webhooks inbound; nunca colocar no frontend. |

## 3. Backend Core — pagamentos e billing

| Variáveis exactas | Estado | Destino final |
|---|---|---|
| `LEMONSQUEEZY_API_KEY` | Manter | Backend Billing/Webhooks. |
| `LEMONSQUEEZY_STORE_ID` | Manter | Backend Billing. |
| `LEMONSQUEEZY_WEBHOOK_SECRET` | Manter | Validação de assinatura do webhook Lemon Squeezy. |
| `LEMONSQUEEZY_CURRENCY` | Manter | Catálogo/checkout apresentado pela plataforma. |
| `LEMONSQUEEZY_VARIANT_BASICO` | Manter | Variante do plano Básico. |
| `LEMONSQUEEZY_VARIANT_MEDIO` | Manter | Variante do plano Médio/Growth. |
| `LEMONSQUEEZY_VARIANT_PREMIUM` | Manter | Variante do plano Premium. |
| `LEMONSQUEEZY_VARIANT_ADDON_CANAIS_PLUS` | Condicional — adicionar no Backend | Variante do extra Canais+. |
| `LEMONSQUEEZY_VARIANT_ADDON_CAMPANHAS_AVANCADAS` | Condicional — adicionar no Backend | Variante do extra Campanhas Avançadas. |
| `LEMONSQUEEZY_VARIANT_ADDON_UTILIZADOR_ADICIONAL` | Condicional — adicionar no Backend | Variante do extra Utilizador Adicional. |

As três variáveis de extras devem ser configuradas apenas no Backend. Não devem ser copiadas para Site, AI Worker, Mailer ou qualquer worker que não crie checkout ou valide webhook.

## 4. AI Worker — destino final das chaves de IA

O `ai_worker.py` usa `services.ai_pool_service.generate_text()`. O roteador actualmente lê directamente os fornecedores a partir do ambiente do processo que o executa. Durante a transição, estas chaves devem ser **duplicadas temporariamente** no AI Worker; depois de a recepção WhatsApp e as rotas de assistente passarem a enfileirar jobs, podem ser removidas do Backend.

| Variáveis exactas | Estado | Observação |
|---|---|---|
| `NEGOBOT_SERVICE_PROFILE=ai` | Manter no AI Worker | Contrato do worker. |
| `REDIS_URL` | Manter no AI Worker | Fila e resultados. |
| `AI_QUEUE` | Manter no AI Worker | Nome da fila de IA. |
| `AI_PRIMARY_TIMEOUT` | Duplicar temporariamente; destino AI Worker | Timeout dos fornecedores primários. |
| `AI_FALLBACK_TIMEOUT` | Duplicar temporariamente; destino AI Worker | Timeout do fallback OpenRouter. |
| `AI_QUEUE_MAX_PER_SECOND` | Duplicar temporariamente; destino AI Worker | Limitação de throughput. |
| `GROQ_API_KEY`, `GROQ_MODEL` | Duplicar temporariamente; destino AI Worker | Groq. `GROQ_MODEL` pode permanecer no Backend apenas enquanto for mostrado no estado da plataforma. |
| `CEREBRAS_API_KEY`, `CEREBRAS_MODEL` | Duplicar temporariamente; destino AI Worker | Cerebras. |
| `SAMBANOVA_API_KEY`, `SAMBANOVA_MODEL` | Duplicar temporariamente; destino AI Worker | SambaNova. |
| `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_MODEL`, `GEMINI_MODEL_2` | Duplicar temporariamente; destino AI Worker | Gemini primário/secundário. |
| `GITHUB_MODELS_TOKEN`, `GITHUB_MODELS_MODEL` | Duplicar temporariamente; destino AI Worker | GitHub Models. `GITHUB_TOKEN` é apenas alias compatível, não deve ser criado sem necessidade. |
| `MISTRAL_API_KEY`, `MISTRAL_MODEL` | Duplicar temporariamente; destino AI Worker | Mistral. |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Duplicar temporariamente; destino AI Worker | Fallback do pool. |

**Acção posterior:** migrar as chamadas directas do Backend para `negobot:ai_jobs`, validar `job_id`/`tenant_id` e só depois remover as API keys de IA do `.env` do Backend. Actualmente ainda não é seguro removê-las porque `services/ai_pool_service.py` também é chamado por rotas e fluxos do monólito.

## 5. Incoming Worker — destino final do ingresso WhatsApp/omnichannel

| Variáveis exactas | Estado | Justificação |
|---|---|---|
| `NEGOBOT_SERVICE_PROFILE=whatsapp_ingress` | Manter no Incoming Worker | Contrato de ingresso. |
| `REDIS_URL` | Manter no Incoming Worker | Enfileiramento de eventos. |
| `FIREBASE_CONFIG` | Manter temporariamente | O worker e os módulos importados persistem eventos/trial. Deve sair apenas quando o worker chamar uma API interna dedicada. |
| `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE_NAME` | Duplicar temporariamente | Necessários para validar e normalizar o evento e tratar a instância central/tenant. |
| `WHATSAPP_INCOMING_QUEUE`, `OMNICHANNEL_INCOMING_QUEUE` | Manter no Incoming Worker | Filas de entrada. |
| `GROQ_API_KEY`, `OPENROUTER_API_KEY` | Remover do Incoming Worker após migração | O ingresso não deve chamar LLM directamente; deve entregar jobs ao AI Worker. |

O Compose actual ainda monta `./services/negobot-backend/.env` no Incoming Worker. Esta é uma das principais razões pelas quais o Backend continua a parecer concentrar todas as chaves.

## 6. Campaign Worker — destino final de campanhas

| Variáveis exactas | Estado | Destino |
|---|---|---|
| `NEGOBOT_SERVICE_PROFILE=campaign` | Manter no Campaign Worker | Contrato de campanhas. |
| `REDIS_URL` | Manter no Campaign Worker | Agendamento e fila. |
| `FIREBASE_CONFIG` | Duplicar temporariamente | Leitura tenant-scoped, planos e estado de campanhas; migrar depois para API/serviço de dados dedicado. |
| `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE_NAME` | Duplicar temporariamente | Envio WhatsApp e validação de instância. |
| `N8N_CAMPAIGN_WEBHOOK_URL`, `N8N_WEBHOOK_SECRET`, `N8N_WEBHOOK_TIMEOUT`, `N8N_WEBHOOK_RETRIES` | Migrar para Campaign Worker | Configuração do adaptador n8n/HMAC. |
| `CHANNEL_PUBLICATIONS_QUEUE` | Manter no Campaign/Publication producer | Fila de publicação. |

O worker de campanhas só deve enviar para contactos autorizados e respeitar os limites/entitlements do tenant. A migração de chaves não altera as regras anti-spam ou de grupos administrados.

## 7. Channel Publication Worker — publicações agendadas

| Variáveis exactas | Estado | Justificação |
|---|---|---|
| `NEGOBOT_SERVICE_PROFILE=channel_publication` | Manter no worker | Contrato de publicações. |
| `REDIS_URL` | Manter no worker | Filas e estado. |
| `FIREBASE_CONFIG` | Duplicar temporariamente | Estado tenant-scoped das publicações. |
| `CHANNEL_PUBLICATIONS_QUEUE` | Manter no worker | Fila imediata. |
| `CHANNEL_PUBLICATIONS_SCHEDULED_QUEUE` | Manter no worker | Fila agendada. |
| `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` | Condicional | Só quando a entrega Evolution de Channels estiver autorizada e implementada; actualmente não deve ser usada para fingir entrega nativa. |

## 8. AutoPay Sync Worker — M-Pesa

| Variáveis exactas | Estado | Justificação |
|---|---|---|
| `AUTOPAY_COLLECTION` | Manter no AutoPay Worker | Colecção de transacções sincronizadas. |
| `MPESA_RECEIVER_PHONE` | Manter no AutoPay Worker | Número receptor usado na confirmação. |
| `AUTOPAY_GROQ_ENABLED` | Manter no AutoPay Worker; preferir `false` | Feature flag legada; não deve chamar IA no worker de pagamentos. |
| `REDIS_URL` | Manter no AutoPay Worker | Coordenação/fila se usada pelo fluxo. |
| `FIREBASE_CONFIG` | Duplicar temporariamente | Leitura das transacções e tenants. |
| `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`, `EVOLUTION_INSTANCE_NAME`, `ADMIN_NUMBER` | Duplicar temporariamente | Notificações e confirmação operacional; remover depois de introduzir um adaptador de notificação dedicado. |

## 9. Image Worker

| Variáveis exactas | Estado |
|---|---|
| `NEGOBOT_SERVICE_PROFILE=image` | Manter no Image Worker |
| `REDIS_URL` | Manter no Image Worker |
| `IMAGE_QUEUE` | Manter no Image Worker |
| `IMAGE_PROVIDER` | Manter no Image Worker |
| `IMAGE_CALLBACK_URL` | Condicional; adicionar apenas se callback real for implementado |

O adaptador Pollinations actualmente não exige uma API key. Não colocar chaves de Groq, Gemini, Firebase ou Evolution neste worker.

## 10. Audio Worker

| Variáveis exactas | Estado |
|---|---|
| `NEGOBOT_SERVICE_PROFILE=audio` | Manter no Audio Worker |
| `REDIS_URL` | Manter no Audio Worker |
| `AUDIO_QUEUE` | Manter no Audio Worker |
| `AUDIO_PROVIDER` | Manter no Audio Worker |
| `AUDIO_OUTPUT_DIR` | Manter no Audio Worker |
| `ELEVENLABS_API_KEY` | Condicional; apenas se ElevenLabs for activado |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Condicional; apenas se Azure Speech for activado |

O Edge TTS actualmente não exige estas chaves. A falha `403` observada no teste de vídeo deve ser tratada no adaptador, não resolvida copiando chaves do Backend para o Audio Worker.

## 11. Social Poster Worker e OAuth

| Variáveis exactas | Estado | Serviço final |
|---|---|---|
| `NEGOBOT_SERVICE_PROFILE=social` | Manter no Social Poster | Contrato do worker. |
| `REDIS_URL`, `SOCIAL_QUEUE` | Manter no Social Poster | Fila de publicação e revisão manual. |
| `SOCIAL_CALLBACK_URL` | Condicional | Apenas se callback persistente for implementado. |
| `META_INSTAGRAM_CLIENT_ID`, `META_INSTAGRAM_CLIENT_SECRET`, `META_INSTAGRAM_REDIRECT_URI`, `META_INSTAGRAM_SCOPES` | Manter no Backend por agora | O Backend inicia/completa OAuth e cifra tokens no Firestore. Migrar só depois de criar um OAuth Gateway/worker dedicado. |
| `META_CLIENT_ID`, `META_CLIENT_SECRET`, `META_REDIRECT_URI`, `META_SCOPES` | Manter no Backend por agora | Facebook/Meta OAuth server-side. |
| `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`, `TIKTOK_SCOPES` | Manter no Backend por agora | TikTok OAuth server-side; pendente de aprovação/availability. |
| `X_CLIENT_ID`, `X_CLIENT_SECRET`, `X_REDIRECT_URI`, `X_SCOPES` | Manter no Backend por agora | OAuth PKCE e callback server-side. |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_REDIRECT_URI`, `LINKEDIN_SCOPES` | Manter no Backend por agora | OAuth server-side; não prometer capacidades não autorizadas. |
| `META_VERIFY_TOKEN`, `X_CONSUMER_SECRET`, `*_WEBHOOK_SECRET` | Manter no Backend | Verificação dos webhooks inbound. |

O Social Poster deve continuar a enviar jobs para `manual_review` enquanto os adaptadores OAuth/outbound não estiverem aprovados. As credenciais OAuth não devem ser colocadas no frontend nem no `.env` do Social Poster neste estágio.

## 12. Mailer Worker e SMTP

| Variáveis exactas | Estado | Justificação |
|---|---|---|
| `NEGOBOT_SERVICE_PROFILE=mailer` | Manter no Mailer Worker | Contrato do worker. |
| `REDIS_URL`, `MAIL_QUEUE` | Manter no Mailer Worker | Fila transaccional. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`, `SMTP_TIMEOUT_SECONDS` | Duplicar temporariamente | O Mailer Worker já sabe enviar e-mail, mas `password_reset_service.py` ainda envia directamente pelo Backend. |

**Migração necessária:** encaminhar recuperação de palavra-passe e alertas para `negobot:mail_jobs`; observar entregas; depois remover as sete variáveis SMTP do Backend. Até essa migração, não apagar as variáveis SMTP do Backend.

## 13. Video Service e Video Worker

| Variáveis exactas | Estado | Serviço |
|---|---|---|
| `NEGOBOT_SERVICE_PROFILE=video` | Manter | Video Service e Video Worker. |
| `REDIS_URL` | Manter | Video Service e Video Worker. |
| `VIDEO_QUEUE` | Manter | Video Service e Video Worker. |
| `VIDEO_SERVICE_TOKEN` | Manter separado | O mesmo contrato de serviço interno, guardado no cartão de cada serviço; nunca expor no frontend. |
| `VIDEO_OUTPUT_DIR` | Manter | Worker/volume de vídeo; o Service só precisa dele se o código de API o usar. |

O Video Service e o Video Worker já possuem `.env` próprios e limites de recursos. O token não deve regressar ao `.env` geral do Backend excepto durante uma compatibilidade transitória explicitamente testada.

## 14. Site público React/Flask

| Variáveis exactas | Estado | Justificação |
|---|---|---|
| `PLATFORM_API_URL` | Manter no Site | `site_server.py` usa esta URL para o proxy do assistente. |
| `ASSISTANT_NUMBER` | Manter no Site | Link `/falar-whatsapp`. Não é uma API key. |
| `PORT` | Manter no Site | Porta interna do Gunicorn. |
| `PUBLIC_DOMAIN` | Remover ou tornar informativa | O runtime actual não a lê. Pode ficar apenas se o servidor passar a usá-la para canonical URLs. |
| `PUBLIC_API_URL` | Normalizar | O template anuncia este nome, mas o código lê `PLATFORM_API_URL`. Escolher um nome canónico e actualizar template/código antes de remover o alias. |
| `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_SCOPES` | Remover do Site | OAuth é server-side no Backend; estas chaves não devem estar no Site. |

## 15. Infraestrutura externa ao Backend

| Serviço | Variáveis exactas | Estado |
|---|---|---|
| **Evolution API** | `AUTHENTICATION_API_KEY`, `DATABASE_PROVIDER`, `DATABASE_CONNECTION_URI`, `CACHE_REDIS_ENABLED`, `CACHE_REDIS_URI`, `WEBHOOK_GLOBAL_ENABLED`, `WEBHOOK_GLOBAL_URL` | Permanecem exclusivamente em `/opt/infra/services/evolution/.env`. Não confundir `AUTHENTICATION_API_KEY` com `EVOLUTION_API_KEY` do cliente Backend. |
| **n8n** | `N8N_HOST`, `N8N_PROTOCOL`, `WEBHOOK_URL`, `N8N_EDITOR_BASE_URL`, `DB_TYPE`, `DB_POSTGRESDB_HOST`, `DB_POSTGRESDB_DATABASE`, `DB_POSTGRESDB_USER`, `DB_POSTGRESDB_PASSWORD`, `N8N_ENCRYPTION_KEY` | Permanecem exclusivamente no `.env` do n8n. O Backend recebe apenas `N8N_CAMPAIGN_WEBHOOK_URL`, `N8N_WEBHOOK_SECRET`, timeout e retries para chamar o webhook. |
| **PostgreSQL** | Usar apenas as variáveis efectivamente definidas no `.env` do cartão PostgreSQL, normalmente o contrato nativo `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Permanecem exclusivamente no PostgreSQL. O seu template não está versionado em `boomploy-infra/services/postgres`; não inventar nem copiar valores para o Backend. |
| **Redis** | Não requer API key própria no Compose actual; os clientes usam `REDIS_URL` | Permanecer como infraestrutura. Não criar `REDIS_PASSWORD` sem activar autenticação Redis de forma coordenada em todos os clientes. |

## 16. Variáveis legadas ou aliases a investigar

| Variável | Decisão recomendada |
|---|---|
| `EVOLUTION_GLOBAL_APIKEY` | Remover depois de confirmar que `workflows/client_flow.py` aposentado não é executado; usar `EVOLUTION_API_KEY` no adaptador activo. |
| `ADMIN_PHONES` | Remover depois de confirmar que `disparo_service.py` e o fluxo legado não estão publicados; substituir por configuração tenant/admin explícita. |
| `AUTHENTICATION_API_KEY` no Backend | Remover se existir no Backend; pertence à Evolution API, não ao Flask. |
| `SERVER_URL` e `AUTHENTICATION_API_KEY` em `disparo_service.py` | Manter apenas no serviço legado se este continuar publicado; caso contrário remover após desligamento controlado. |
| `DATABASE_URL` | Não adicionar ao Backend; o projecto usa Firebase/Firestore, conforme o template actual. |
| `NEGOBOT_ENV_FILE` | Manter apenas como mecanismo interno opcional dos workers; nunca apontar para o `.env` geral do Backend em produção. |

## 17. Ordem segura de migração

A migração deve começar por adicionar os contratos próprios aos cartões dos workers sem apagar nada do Backend. Em seguida, o Incoming Worker deve ser convertido para publicar exclusivamente eventos normalizados com `tenant_id` e o AI Worker deve processar `negobot:ai_jobs`. Depois devem ser migrados o Mailer, Campaign, Channel Publication e AutoPay, cada um com testes de tenant isolation, idempotência e falha de fornecedor.

Após cada migração, deve ser executada a suite backend, `pnpm run check`, `pnpm run build`, `git diff --check` e um smoke test limitado. O serviço afectado deve ser redeployado isoladamente no Boomploy; Evolution API, PostgreSQL e Redis não devem ser reiniciados sem necessidade.

Só depois de observar os logs e os health checks durante um período estável se devem remover as variáveis antigas do Backend. A remoção deve ocorrer por grupos: primeiro IA, depois SMTP, depois n8n/campanhas, depois Evolution dos workers e por fim aliases legados. Cada grupo deve ter commit e rollback próprios.

## 18. Fontes internas auditadas

A matriz foi cruzada com os seguintes ficheiros do repositório:

- `services/service_config.py`, contratos oficiais `api`, `whatsapp_ingress`, `campaign`, `channel_publication`, `billing`, `video`, `ai`, `image`, `audio`, `social` e `mailer`.
- `config.py`, configuração ainda carregada pelo monólito.
- `services/ai_pool_service.py`, roteador dos fornecedores de IA.
- `services/channel_oauth_service.py`, definições OAuth server-side.
- `services/password_reset_service.py`, utilização actual de SMTP no Backend.
- `services/secret_store.py`, cifragem de tokens Telegram/social.
- `site_server.py`, contrato efectivo do Site.
- `docker-compose.yml` de `boomploy-infra`, montagem dos `.env`, perfis e volumes.
- Templates `.env.example` dos workers, Evolution, n8n, Backend e Site.

## 19. Validação da auditoria

A matriz contém 150 linhas de tabela e foi validada com `python3 -m compileall -q services routes *.py` e `git diff --check`, ambos concluídos com sucesso. A suite existente executou 125 testes, com 124 aprovados e 1 falha em `test_active_trial_gets_temporary_premium_entitlements`.

A falha é temporal e não foi causada pela matriz: o teste fixa `connected_at` em 18 de Agosto de 2026, enquanto a execução ocorre em 20 de Agosto de 2026; pela regra de dois dias, esse trial já expirou. O teste deve ser actualizado posteriormente para usar um relógio congelado ou uma data relativa controlada. Não alterei a lógica de trial nem fiz deploy nesta auditoria.
