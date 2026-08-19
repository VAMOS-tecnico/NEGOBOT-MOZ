# Matriz sanitizada de variáveis do NEGOBOT MOZ

Este documento contém apenas nomes de variáveis encontrados no código; não contém valores, tokens ou passwords.

## `app.py`

| Variável |
|---|
| `ADMIN_TOKEN` |
| `MAX_UPLOAD_BYTES` |
| `NEGOBOT_SERVICE_PROFILE` |
| `PLATFORM_SECRET_KEY` |
| `PORT` |

## `autopay_sync_worker.py`

| Variável |
|---|
| `AUTOPAY_COLLECTION` |
| `AUTOPAY_GROQ_ENABLED` |
| `LOG_LEVEL` |
| `MPESA_RECEIVER_PHONE` |

## `campaign_worker.py`

| Variável |
|---|
| `REDIS_URL` |

## `config.py`

| Variável |
|---|
| `ADMIN_NUMBER` |
| `AI_FALLBACK_TIMEOUT` |
| `AI_PRIMARY_TIMEOUT` |
| `AI_QUEUE_MAX_PER_SECOND` |
| `ASSISTANT_NUMBER` |
| `CEREBRAS_API_KEY` |
| `CEREBRAS_MODEL` |
| `EVOLUTION_API_KEY` |
| `EVOLUTION_API_URL` |
| `EVOLUTION_INSTANCE_NAME` |
| `FIREBASE_CONFIG` |
| `GEMINI_API_KEY` |
| `GEMINI_API_KEY_2` |
| `GEMINI_MODEL` |
| `GEMINI_MODEL_2` |
| `GITHUB_MODELS_MODEL` |
| `GITHUB_MODELS_TOKEN` |
| `GROQ_API_KEY` |
| `GROQ_MODEL` |
| `GROQ_VISION_MODEL` |
| `MISTRAL_API_KEY` |
| `MISTRAL_MODEL` |
| `N8N_CAMPAIGN_WEBHOOK_URL` |
| `N8N_WEBHOOK_RETRIES` |
| `N8N_WEBHOOK_SECRET` |
| `N8N_WEBHOOK_TIMEOUT` |
| `OPENROUTER_API_KEY` |
| `OPENROUTER_MODEL` |
| `REDIS_URL` |
| `SAMBANOVA_API_KEY` |
| `SAMBANOVA_MODEL` |
| `TIMEOUT_HUMANO_MINUTOS` |
| `WEBHOOK_URL` |
| `WHATSAPP_INCOMING_QUEUE` |

## `disparo_service.py`

| Variável |
|---|
| `ADMIN_PHONES` |
| `AUTHENTICATION_API_KEY` |
| `EVOLUTION_API_KEY` |
| `EVOLUTION_API_URL` |
| `SERVER_URL` |

## `extensions.py`

| Variável |
|---|
| `FIREBASE_BASE64` |
| `FIREBASE_CONFIG_B64` |

## `incoming_worker.py`

| Variável |
|---|
| `REDIS_URL` |

## `platform_worker.py`

| Variável |
|---|
| `REDIS_URL` |

## `routes/omnichannel_routes.py`

| Variável |
|---|
| `META_VERIFY_TOKEN` |
| `X_CONSUMER_SECRET` |

## `routes/platform_routes.py`

| Variável |
|---|
| `ADMIN_TOKEN` |
| `EVOLUTION_API_KEY` |
| `EVOLUTION_API_URL` |
| `GROQ_MODEL` |
| `GROQ_VISION_MODEL` |
| `LEMONSQUEEZY_CURRENCY` |
| `PUBLIC_API_BASE_URL` |
| `PUBLIC_APP_BASE_URL` |
| `REDIS_URL` |
| `VIDEO_SERVICE_TOKEN` |
| `VIDEO_SERVICE_URL` |

## `services/ai_pool_service.py`

| Variável |
|---|
| `AI_FALLBACK_TIMEOUT` |
| `AI_PRIMARY_TIMEOUT` |
| `OPENROUTER_API_KEY` |
| `OPENROUTER_MODEL` |

## `services/channel_oauth_service.py`

| Variável |
|---|
| `PUBLIC_API_BASE_URL` |

## `services/channel_publication_service.py`

| Variável |
|---|
| `CHANNEL_PUBLICATIONS_QUEUE` |
| `CHANNEL_PUBLICATIONS_SCHEDULED_QUEUE` |
| `REDIS_URL` |

## `services/firebase_service.py`

| Variável |
|---|
| `FIREBASE_CONFIG` |

## `services/groq_service.py`

| Variável |
|---|
| `GROQ_API_KEY` |

## `services/incoming_queue.py`

| Variável |
|---|
| `OMNICHANNEL_INCOMING_QUEUE` |
| `REDIS_URL` |
| `WHATSAPP_INCOMING_QUEUE` |

## `services/lemonsqueezy_service.py`

| Variável |
|---|
| `LEMONSQUEEZY_API_KEY` |
| `LEMONSQUEEZY_STORE_ID` |
| `LEMONSQUEEZY_WEBHOOK_SECRET` |

## `services/n8n_service.py`

| Variável |
|---|
| `N8N_CAMPAIGN_WEBHOOK_URL` |
| `N8N_WEBHOOK_RETRIES` |
| `N8N_WEBHOOK_SECRET` |
| `N8N_WEBHOOK_TIMEOUT` |

## `services/password_reset_service.py`

| Variável |
|---|
| `PASSWORD_RESET_TTL_MINUTES` |
| `SMTP_FROM` |
| `SMTP_HOST` |
| `SMTP_PASSWORD` |
| `SMTP_PORT` |
| `SMTP_TIMEOUT_SECONDS` |
| `SMTP_USER` |
| `SMTP_USE_TLS` |

## `services/secret_store.py`

| Variável |
|---|
| `ADMIN_TOKEN` |
| `PLATFORM_SECRET_KEY` |
| `TELEGRAM_TOKEN_ENCRYPTION_KEY` |

## `services/service_config.py`

| Variável |
|---|
| `NEGOBOT_SERVICE_PROFILE` |

## `site_server.py`

| Variável |
|---|
| `ASSISTANT_NUMBER` |
| `PLATFORM_API_URL` |

## `video_service.py`

| Variável |
|---|
| `REDIS_URL` |
| `VIDEO_QUEUE` |
| `VIDEO_SERVICE_TOKEN` |

## `video_worker.py`

| Variável |
|---|
| `REDIS_URL` |
| `VIDEO_OUTPUT_DIR` |
| `VIDEO_QUEUE` |

## `workflows/client_flow.py`

| Variável |
|---|
| `ADMIN_PHONES` |
| `EVOLUTION_GLOBAL_APIKEY` |



## Workers de microserviços faseados — 2026-08

### `ai_worker.py`

| Variável |
|---|
| `NEGOBOT_SERVICE_PROFILE` |
| `NEGOBOT_ENV_FILE` |
| `REDIS_URL` |
| `AI_QUEUE` |
| `AI_PRIMARY_TIMEOUT` |
| `AI_FALLBACK_TIMEOUT` |
| `AI_QUEUE_MAX_PER_SECOND` |
| `GROQ_API_KEY` |
| `GROQ_MODEL` |
| `CEREBRAS_API_KEY` |
| `CEREBRAS_MODEL` |
| `SAMBANOVA_API_KEY` |
| `SAMBANOVA_MODEL` |
| `GEMINI_API_KEY` |
| `GEMINI_API_KEY_2` |
| `GEMINI_MODEL` |
| `GEMINI_MODEL_2` |
| `GITHUB_MODELS_TOKEN` |
| `GITHUB_MODELS_MODEL` |
| `MISTRAL_API_KEY` |
| `MISTRAL_MODEL` |
| `OPENROUTER_API_KEY` |
| `OPENROUTER_MODEL` |

### `image_worker.py`

| Variável |
|---|
| `NEGOBOT_SERVICE_PROFILE` |
| `NEGOBOT_ENV_FILE` |
| `REDIS_URL` |
| `IMAGE_QUEUE` |
| `IMAGE_PROVIDER` |
| `IMAGE_CALLBACK_URL` |

### `audio_worker.py`

| Variável |
|---|
| `NEGOBOT_SERVICE_PROFILE` |
| `NEGOBOT_ENV_FILE` |
| `REDIS_URL` |
| `AUDIO_QUEUE` |
| `AUDIO_PROVIDER` |
| `AUDIO_OUTPUT_DIR` |
| `ELEVENLABS_API_KEY` |
| `AZURE_SPEECH_KEY` |
| `AZURE_SPEECH_REGION` |

### `social_poster_worker.py`

| Variável |
|---|
| `NEGOBOT_SERVICE_PROFILE` |
| `NEGOBOT_ENV_FILE` |
| `REDIS_URL` |
| `SOCIAL_QUEUE` |
| `SOCIAL_CALLBACK_URL` |
| `FIREBASE_CONFIG` |

### `mailer_worker.py` / `services/mailer_service.py`

| Variável |
|---|
| `NEGOBOT_SERVICE_PROFILE` |
| `NEGOBOT_ENV_FILE` |
| `REDIS_URL` |
| `MAIL_QUEUE` |
| `SMTP_HOST` |
| `SMTP_PORT` |
| `SMTP_USER` |
| `SMTP_PASSWORD` |
| `SMTP_FROM` |
| `SMTP_USE_TLS` |
| `SMTP_TIMEOUT_SECONDS` |

### `services/job_runtime.py`

| Variável |
|---|
| `REDIS_URL` |
| `NEGOBOT_SERVICE_PROFILE` |
| fila definida pelo worker |
