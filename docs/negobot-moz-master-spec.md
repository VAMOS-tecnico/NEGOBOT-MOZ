# NEGOBOT-MOZ — Especificação técnica central

**Estado:** integrada como documento de arquitetura e roteiro de evolução.  
**Data de integração:** 17 de agosto de 2026.  
**Repositório:** `VAMOS-tecnico/NEGOBOT-MOZ`.

## 1. Objetivo e interpretação

Este documento consolida a especificação recebida para a evolução do NEGOBOT-MOZ como plataforma SaaS multi-tenant de automação, atendimento e campanhas omnichannel. Ele funciona como **fonte de requisitos e roteiro**, mas não substitui as decisões de segurança e a infraestrutura já implementadas no repositório.

A especificação original menciona Node.js, Dokploy e um microserviço Python separado. A implementação atual do NEGOBOT-MOZ utiliza Flask/Python no backend, React/Vite no frontend, Boomploy para gestão visual da infraestrutura, Caddy como proxy, Evolution API, Redis, n8n e Firestore/Firebase. Qualquer migração de stack deverá ser aprovada e executada numa fase própria; não é feita implicitamente por este documento.

## 2. Arquitetura-alvo

| Camada | Domínio ou componente | Responsabilidade | Estado atual |
|---|---|---|---|
| Site institucional | `https://negobotmoz.duckdns.org` | Conversão, planos, demonstração e seleção PT/EN | React publicado e validado |
| Plataforma privada | `https://app-negobotmoz.duckdns.org/plataforma/` | Administração global, tenants, CRM, campanhas, faturação e métricas | React e API multi-tenant em evolução |
| Backend | `https://negobot-api.duckdns.org` | Sessões, API SaaS, webhooks, pagamentos, CRM e autorizações | Flask/Gunicorn em produção |
| WhatsApp | Evolution API | Sessões, QR Code, mensagens e webhooks | Em produção |
| Orquestração | n8n | Tarefas pesadas, agendamentos e integrações externas | Em produção |
| Fila | Redis | Campanhas, retries, estados e execução fora do navegador | Worker persistente em produção |
| Proxy/TLS | Caddy | HTTPS e roteamento dos subdomínios | Em produção |
| Dados SaaS | Firestore/Firebase | Tenants, utilizadores, contactos, pagamentos e auditoria | Integrado no backend |
| Vídeo curto | FastAPI/Python dedicado | Roteiros, TTS, media vertical e renderização MP4 | Roadmap |

O painel administrativo permanece exclusivamente no domínio `app-negobotmoz.duckdns.org`. O site institucional não apresenta a tela de login nem links de administração.

## 3. Arquitetura dual de pagamentos

O fluxo local mantém o pagamento manual por M-Pesa para o número **855000929**, com confirmação pelo AutoPay/Firebase e validação do comprovativo. O fluxo internacional utiliza Lemon Squeezy como Merchant of Record para pagamentos com cartão e outros métodos suportados pela plataforma.

Independentemente do gateway, o backend deverá normalizar o resultado num único ciclo de ativação: validar o evento, impedir duplicação, localizar o tenant, registar o pagamento, ativar o plano e libertar os limites e a ligação WhatsApp apenas depois de a confirmação ser considerada válida.

| Fluxo | Entrada | Validação | Resultado |
|---|---|---|---|
| M-Pesa | Transferência para 855000929 e comprovativo | AutoPay/Firebase, comparação de referência, valor, telefone e plano | Pagamento registado e plano ativado |
| Lemon Squeezy | Checkout internacional e webhook assinado | HMAC, evento de pagamento, idempotência e variante do plano | Pagamento registado e plano ativado |

Os webhooks nunca devem ativar um plano apenas porque receberam um pedido HTTP. A assinatura, o evento suportado, a identidade do tenant e a idempotência devem ser verificadas antes da mutação.

## 4. Orquestração com n8n

O backend deve delegar ao n8n tarefas pesadas, agendadas ou que envolvam várias APIs externas. A Evolution API permanece focada na gestão das sessões WhatsApp e na entrega de mensagens. O browser não deve executar campanhas, retries ou tarefas longas.

O fluxo recomendado é:

1. O backend valida a autorização, o tenant, os limites e o payload.
2. O backend grava a operação e a respetiva idempotency key.
3. O backend emite um webhook autenticado para um workflow n8n.
4. O n8n ramifica as ações em paralelo, aplica retries controlados e devolve estados correlacionáveis.
5. O backend atualiza a campanha, o destinatário, a métrica e a auditoria.

Toda chamada entre backend e n8n deve utilizar autenticação própria, timeout, correlação por `request_id` e proteção contra reenvio.

## 5. Central de campanhas omnichannel

A plataforma deverá disponibilizar um editor unificado onde o cliente informa produto, oferta, público, idioma, tom e canais. A IA pode preparar variações, hashtags e criativos, mas o envio depende sempre das permissões do tenant, do consentimento dos contactos, dos limites do plano e das regras de cada canal.

Os canais previstos são:

| Canal | Integração prevista |
|---|---|
| WhatsApp | Evolution API |
| Facebook | Meta API |
| Instagram | Meta API |
| TikTok | TikTok API |
| X/Twitter | X API |
| LinkedIn | LinkedIn API |
| Telegram | Telegram Bot API |
| E-mail | SMTP ou SendGrid |

A campanha deve manter um estado global e um estado por destinatário/canal. Estados mínimos: `draft`, `scheduled`, `running`, `paused`, `completed`, `cancelled` e `failed`. Cada envio deve guardar tentativas, erro normalizado, horário, idempotency key e resultado do fornecedor.

## 6. Motor de vídeos curtos

O motor de vídeos curtos será um microserviço isolado em Python/FastAPI, ativado apenas quando a infraestrutura e os limites de recursos da VPS forem suficientes. O pipeline de referência é:

1. A IA estrutura um roteiro em cenas curtas.
2. Um serviço TTS produz a locução em MP3.
3. Pexels, Pixabay ou outra fonte autorizada fornece media vertical 9:16.
4. MoviePy ou ferramenta equivalente compõe áudio, clipes, legendas e transições num MP4.
5. O n8n recolhe o resultado e agenda a publicação em TikTok, Reels, Shorts e Status.

O serviço deverá ter fila, limite de concorrência, limpeza de temporários, timeout, logs rotativos e armazenamento externo para os ficheiros finais. A renderização não deverá bloquear o backend principal nem consumir a memória reservada a PostgreSQL, Redis, n8n, Evolution, Caddy e workers SaaS.

## 7. Segurança multi-tenant

Cada documento de negócio deve possuir `tenant_id`. As rotas devem obter o tenant a partir da sessão autenticada e nunca aceitar um `tenant_id` livremente fornecido pelo navegador. O papel `owner` é a única exceção para operações globais e todas essas ações devem gerar auditoria.

As chaves de Evolution, Groq, Firebase, Meta, TikTok, X, LinkedIn, Telegram, SMTP e Lemon Squeezy permanecem no servidor. O frontend recebe apenas estado mascarado, capacidades permitidas e resultados necessários para a operação.

## 8. Modelo funcional mínimo

| Área | Entidades ou capacidades |
|---|---|
| Identidade | Utilizadores, sessões, papéis, equipas, recuperação e rate limiting |
| Tenants | Empresa, plano, limites, estado, instância WhatsApp e ciclo de vida |
| CRM | Contactos, tags, consentimento, opt-out, segmentos e auditoria |
| Campanhas | Templates, conteúdo, canais, agenda, destinatários, fila e métricas |
| Conversas | Histórico, estado bot/humano, atribuição e contexto |
| IA | Assistente, Groq, áudio, documentos, imagens e base de conhecimento |
| Faturação | M-Pesa/AutoPay, Lemon Squeezy, pagamentos, planos e idempotência |
| Suporte | Tickets, prioridade, SLA, notas internas e histórico |
| Administração | Integrações globais, saúde, tenants, auditoria e métricas |

## 9. Roteiro de execução

A prioridade imediata permanece fechar e validar completamente a arquitetura dual de pagamentos. Em seguida, deve ser consolidada a orquestração n8n para campanhas e integrações omnichannel. O motor de vídeos curtos entra depois de a fila persistente, métricas, armazenamento e limites de recursos estarem estabilizados.

| Fase | Entrega | Critério de conclusão |
|---|---|---|
| 1 | Pagamentos M-Pesa + Lemon Squeezy | Webhooks assinados, idempotência, histórico e ativação uniforme |
| 2 | n8n protegido | Workflows autenticados, retries, correlação e logs |
| 3 | Campanhas omnichannel | Editor, segmentação, consentimento, fila e métricas |
| 4 | Suporte e relatórios | Tickets, dashboards, auditoria e exportações |
| 5 | Vídeo curto | Serviço isolado, renderização assíncrona e publicação controlada |
| 6 | Hardening final | Testes de isolamento, carga, segurança, backups e rollback |

## 10. Regras de produção

Nenhuma alteração deve remover volumes persistentes Docker ou substituir segredos versionados. Todos os serviços devem manter rotação de logs com `max-size=10m` e `max-file=3`. Campanhas e tarefas longas devem continuar a funcionar sem o browser aberto. Todas as mudanças de código devem ser testadas antes do deploy e publicadas no repositório GitHub definido para o projeto.

## 11. Relação com a documentação existente

Este documento complementa [`docs/platform-architecture.md`](./platform-architecture.md) e [`docs/lemonsqueezy-setup.md`](./lemonsqueezy-setup.md). A arquitetura existente continua a ser a referência para os componentes já implementados; este ficheiro passa a ser a referência consolidada para os requisitos futuros, os canais omnichannel e o microserviço de vídeos.
