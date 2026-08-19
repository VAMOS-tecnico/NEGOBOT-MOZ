# Auditoria de Microserviços do NEGOBOT MOZ — 19-08-2026

## Resumo executivo

A aplicação já possui uma primeira modularização segura: API com health checks, Campaign Worker, Incoming Worker, Channel Publication Worker, AutoPay Sync e código de Vídeo separado. Contudo, vários containers ainda são construídos a partir da mesma imagem e carregam o mesmo `.env` do Backend. O problema principal não é apenas o número de variáveis: é a combinação de acoplamento de imports, inicialização global de `config.py`, duplicação de dependências e consumidores de Redis que ainda não possuem contratos próprios.

## Estado real do Compose

| Serviço | Estado no Compose | Imagem/contexto | Ambiente actual | Observação |
|---|---|---|---|---|
| `negobot-backend` | existente | `./services/negobot-backend` | `.env` monolítico | perfil `api`, health check `/healthz` |
| `negobot-incoming-worker` | existente | mesma imagem do Backend | `.env` monolítico | consome filas WhatsApp/omnichannel |
| `negobot-campaign-worker` | existente | mesma imagem do Backend | `.env` monolítico | consumidor autorizado da fila de campanhas |
| `negobot-channel-publication-worker` | existente | mesma imagem do Backend | `.env` monolítico | publica/agenda Channel Publications |
| `negobot-autopay-sync` | existente | mesma imagem do Backend | `.env` monolítico + overrides | billing/AutoPay |
| Vídeo | código existente, Compose ausente | `workflows/Video.Dockerfile` | não publicado pelo Compose | API FastAPI e worker Redis já existem |
| AI, Image, Audio, Social, Mailer | não existem como containers | sem entrypoints dedicados | não isolados | precisam de contratos e adaptadores reais |

## Uso real das variáveis

A matriz documentada contém aproximadamente 60 nomes de ambiente, mas o uso real está concentrado em quatro grupos: configuração global inicializada em `config.py`, API/rotas de plataforma, integração Evolution/WhatsApp e fornecedores de IA. O Core ainda importa indirectamente `groq_service`, que chama o pool multi-provider através de `flow_handlers.py`; portanto, mover apenas as chaves para outro `.env` sem criar um protocolo de jobs quebraria o fluxo de conversação.

A implementação de imagens usa actualmente Pollinations AI sem chave própria. Não há, no código auditado, adaptadores activos para Stability AI, Flux, DALL-E ou Leonardo AI. A implementação de vídeo é funcional e isolável, mas ainda não está declarada no Compose de produção. A publicação social possui OAuth e catálogo de capacidades, mas vários canais permanecem dependentes de aprovação/adaptador; não deve ser marcado como worker activo apenas pela existência da UI. O áudio/TTS usa `edge-tts` dentro do código do Backend; não existem actualmente clientes ElevenLabs ou Azure Speech.

## Riscos identificados

1. Se nove workers forem adicionados imediatamente na VPS de 2 vCPU e aproximadamente 3,7 GiB de RAM, haverá duplicação de processos Python, bibliotecas e conexões Redis/Firebase sem garantia de redução de memória.
2. `config.py` lê variáveis de múltiplos domínios e vários módulos são importados por rotas síncronas. A separação de `.env` deve acompanhar a separação de entrypoints/imports.
3. O Core chama directamente Evolution, Redis, IA, Vídeo e SMTP em rotas distintas. Para reduzir o Core para cerca de 10 variáveis é necessário introduzir contratos internos e filas/adaptadores, não apenas editar o Compose.
4. O vídeo já tem uma fila própria e perfil de ambiente; deve ser activado antes de criar um segundo pipeline.
5. Os canais sociais e os fornecedores de imagem/áudio ainda não possuem todos os adaptadores activos. Esses workers devem iniciar em estado `disabled`/`not_configured` até existirem credenciais e contratos verificáveis.

## Estratégia recomendada

A primeira entrega deve separar variáveis e processos já existentes: Core, Incoming, Campaign, Channel Publication, Billing e Video. Em seguida, devem ser adicionados AI, Image, Audio, Social e Mailer como workers orientados a filas, cada um com schema de job, idempotência, tenant_id, estado persistido e health check. A publicação deve usar perfis Compose desactivados por defeito até os respectivos `.env` isolados estarem preenchidos no Boomploy.

## Limitação operacional

O painel Boomploy actual fornece estado, logs e variáveis por serviço, mas não expõe uma métrica de CPU/RAM equivalente a `docker stats`. Por isso, esta auditoria não inventa números de utilização. A optimização deve começar por limites explícitos de workers, concorrência e fila; a decisão de activar serviços adicionais deve ser validada pelos logs e por métricas reais adicionadas ao painel ou a um endpoint de observabilidade.
