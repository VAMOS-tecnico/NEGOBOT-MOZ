# Motor de vídeos curtos

## Componentes

| Ficheiro | Função |
|---|---|
| `video_service.py` | API FastAPI para criar e consultar jobs |
| `video_worker.py` | Worker Redis persistente que processa jobs fora do browser |
| `video_pipeline.py` | Renderização 9:16, cartões, TTS opcional e concatenação MP4 |
| `workflows/Video.Dockerfile` | Imagem isolada com FFmpeg, fontes e dependências Python |
| `requirements-video.txt` | Dependências exclusivas do serviço de vídeos |

## API interna

A API exige o header `X-Video-Service-Token`. Os endpoints são `GET /health`, `POST /api/video/jobs` e `GET /api/video/jobs/{job_id}`. A plataforma Flask funciona como camada privada para os tenants: grava `tenant_id` em `video_jobs`, encaminha o pedido ao serviço e impede que um tenant consulte o job de outro.

## Variáveis

| Variável | Função |
|---|---|
| `VIDEO_SERVICE_TOKEN` | Segredo da API interna |
| `VIDEO_SERVICE_URL` | URL interna do container FastAPI |
| `VIDEO_QUEUE` | Fila Redis; padrão `negobot:video_jobs` |
| `VIDEO_OUTPUT_DIR` | Diretório temporário ou volume dos MP4 finais |
| `REDIS_URL` | Redis persistente partilhado pela plataforma |

Os assets só são aceites através de URLs HTTPS. O pipeline aplica limite de 25 MB por asset e usa cartões de fallback quando não existe media externo. A locução é gerada por `edge-tts` quando a dependência e a voz configurada estão disponíveis; a ausência de TTS não invalida o render.

## Estados

`queued` indica que o job está na fila, `processing` indica renderização, `completed` indica que o MP4 foi produzido e `failed` guarda uma mensagem de erro limitada. O worker atualiza progresso e continua ativo sem o cliente manter o browser aberto.

## Operação segura

O serviço deve ser executado como container separado, com `restart: unless-stopped`, logs `max-size=10m` e `max-file=3`, limite de concorrência e volume dedicado para os resultados. A API do vídeo não deve ficar pública sem autenticação; o tráfego normal passa pelo backend privado.
