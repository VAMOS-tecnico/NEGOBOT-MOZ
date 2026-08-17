# NEGOBOT-MOZ — Arquitetura da plataforma SaaS

## Objetivo

O NEGOBOT-MOZ será uma plataforma SaaS multi-tenant sobre o motor atual de WhatsApp, IA, Evolution API e Firestore. O proprietário terá uma área administrativa global; cada cliente terá uma área privada limitada ao seu tenant.

## Papéis

| Papel | Alcance | Capacidades principais |
|---|---|---|
| `owner` | Plataforma inteira | Clientes, planos, integrações globais, instâncias, limites, pagamentos, auditoria, saúde e configurações |
| `admin` | Plataforma inteira ou tenant atribuído | Operação diária, suporte, campanhas e conversas conforme a permissão atribuída |
| `client` | Apenas o próprio tenant | Contactos, segmentos, campanhas, disparos, assistente, conversas e métricas próprias |
| `operator` | Tenant atribuído | Caixa de entrada, atendimento humano e execução operacional sem acesso a faturação ou segredos |

## Isolamento obrigatório

Cada documento de negócio terá `tenant_id`. Todas as leituras e escritas de clientes deverão passar por uma função de autorização que obtém o tenant a partir da sessão autenticada, nunca a partir de um `tenant_id` enviado livremente pelo navegador. O papel `owner` é a única exceção e fica registado em auditoria.

## Coleções Firestore

| Coleção | Conteúdo | Chave de isolamento |
|---|---|---|
| `platform_users` | Utilizadores, papel, password hash, estado e último acesso | `tenant_id` quando aplicável |
| `tenants` | Empresas/clientes, plano, estado, limites e instância Evolution | Documento do tenant |
| `tenant_integrations` | Configuração não secreta e referências seguras às integrações | `tenant_id` |
| `contacts` | Contactos, consentimento, tags, estado e opt-out | `tenant_id` |
| `segments` | Segmentos e filtros de contactos | `tenant_id` |
| `campaigns` | Texto, mídia, spintax, estado, agenda e métricas | `tenant_id` |
| `campaign_recipients` | Estado de entrega por contacto, tentativas e erro | `tenant_id`, `campaign_id` |
| `conversations` | Estado da conversa, humano/bot e última interação | `tenant_id`, `phone` |
| `audit_events` | Ações administrativas e operacionais | `tenant_id` ou `platform` |

## Sessão e segurança

A autenticação usa sessão HTTP-only assinada, expiração, rotação de sessão no login, hash de password com Werkzeug, proteção CSRF para mutações do painel, rate limiting de login e verificação de papel em todas as rotas. As chaves Evolution, Groq e Firebase nunca são devolvidas ao navegador; a área administrativa mostra apenas estado e campos mascarados.

## Campanhas e fila

A criação de campanha grava primeiro a campanha e os destinatários deduplicados. A execução é feita por uma fila persistente Redis, com estados `draft`, `scheduled`, `running`, `paused`, `completed`, `cancelled` e `failed`. Cada envio tem idempotency key, opt-out obrigatório, limite por tenant, retry limitado, delay variável e pausa por lote. O navegador apenas consulta o progresso; não executa o disparo.

## Mapeamento do código existente

| Código atual | Módulo visual futuro |
|---|---|
| `routes/webhook_routes.py` | Integrações e caixa de entrada |
| `workflows/central_flow.py` | Operação da conta proprietária |
| `workflows/client_flow.py` | Assistente de cada tenant |
| `disparo_service.py` | Campanhas, fila, limites e auditoria |
| `services/groq_service.py` | Configuração do assistente e capacidades IA |
| `services/media_service.py` | Base de conhecimento e anexos |
| `services/image_generator_service.py` | Gerador de artes |
| `services/payment_service.py` | Planos, pagamentos e ativação |
| `database/chat_repo.py` | Conversas e histórico |
| `services/evolution_service.py` | Instâncias e integração WhatsApp |

## Fases de entrega

1. Login seguro, sessão, tenants, papéis e shell dos painéis.
2. Contactos, tags, importação CSV/XLSX, opt-in/opt-out e segmentos.
3. Campanhas, fila persistente, progresso, pausa, cancelamento e relatórios.
4. Caixa de entrada, transição humana, base de conhecimento e configurações IA.
5. Instâncias Evolution, webhooks, pagamentos, limites e auditoria administrativa.

## Estado da migração React — 2026-08-16

Foi criada a base `platform-react/` com Vite, React, TypeScript e React Router. O bundle usa a base pública `/plataforma/` e mantém o backend Flask como fonte de dados.

A estrutura inicial inclui `src/lib/api.ts` para autenticação, overview, clientes, integrações, conversas, contactos, campanhas e planos; `App.tsx` para sessão, rotas e layout; `pages/AdminPage.tsx` para administração; e `pages/ClientPages.tsx` para conversas/contactos, campanhas e planos.

O login usa `/api/platform/auth/me`, `/api/platform/auth/login` e `/api/platform/auth/logout`, mantendo a sessão HTTP do Flask. Os módulos de cliente usam `/api/platform/client/contacts`, `/api/platform/client/conversations`, `/api/platform/client/campaigns`, `/api/platform/client/plan`, `/api/platform/client/plans` e `/api/platform/client/integration/status`. A administração usa `/api/platform/admin/overview`, `/api/platform/admin/tenants` e `/api/platform/admin/health`.

A build local foi validada com `pnpm run build`. A aplicação ainda não substitui `platform.html` no VPS; o frontend antigo continua a ser o fallback de produção até a migração completa e a validação autenticada.
