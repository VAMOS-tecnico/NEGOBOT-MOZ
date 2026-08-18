# Manual Técnico de Onboarding SaaS — NEGOBOT MOZ

**Versão:** 1.0  
**Data:** 17 de agosto de 2026  
**Repositório:** [`VAMOS-tecnico/NEGOBOT-MOZ`](https://github.com/VAMOS-tecnico/NEGOBOT-MOZ)  
**Infraestrutura:** Hetzner VPS, Boomploy, Docker Compose, Caddy, Firebase/Firestore, PostgreSQL e Redis

> Este documento descreve a arquitetura funcional e operacional do NEGOBOT MOZ como plataforma SaaS multi-tenant. O manual não contém chaves, tokens, palavras-passe, números administrativos privados ou outros segredos.

## 1. Objetivo e princípios da plataforma

O NEGOBOT MOZ é uma plataforma SaaS centralizada para automação de atendimento e campanhas em WhatsApp e outros canais digitais. Cada cliente possui um **tenant isolado**, uma conta identificada pelo email e uma configuração própria de empresa, redes sociais, plano, instância WhatsApp, contactos, campanhas, conversas, pagamentos e suporte.

A plataforma deve seguir cinco princípios fundamentais. Primeiro, os dados de cada cliente nunca podem ser misturados com os dados de outro tenant. Segundo, o WhatsApp só deve ser ligado depois de existir uma demonstração válida ou um pagamento confirmado. Terceiro, a demonstração inicial é única e dura dois dias, não podendo ser reiniciada pelo cliente. Quarto, os dados utilizados pela IA devem vir do perfil oficial e da base de conhecimento do próprio tenant. Quinto, os processos demorados devem ser executados de forma assíncrona através de Redis e workers persistentes.

## 2. Arquitetura de alto nível

A arquitetura é composta por uma camada pública de conversão, uma plataforma React autenticada, um backend Flask, workers persistentes, Evolution API, n8n, Firebase/Firestore, Redis, PostgreSQL e serviços auxiliares.

| Componente | Responsabilidade | Estado |
|---|---|---|
| Site público React | Conversão, planos, assistente público, PT/EN e entrada para a plataforma | Implementado |
| Plataforma React | Área autenticada do cliente, pagamentos, QR Code, empresa, redes sociais, CRM e campanhas | Implementado |
| Backend Flask/Gunicorn | Autenticação, tenants, pagamentos, QR Code, webhook, CRM e APIs | Implementado |
| Incoming Worker | Consumo persistente de mensagens WhatsApp recebidas | Implementado |
| Platform Worker | Campanhas persistentes e dispatch omnichannel | Implementado |
| Evolution API v2 | Sessões WhatsApp, QR Codes, webhooks e envio de mensagens | Integrado |
| n8n | Orquestração de canais não WhatsApp e automações externas | Integrado; requer URL e segredo reais |
| Firebase/Firestore | Utilizadores, tenants, pagamentos AutoPay, conversas e configuração SaaS | Integrado |
| Redis | Filas de mensagens, campanhas e vídeos | Integrado |
| PostgreSQL | Dados internos da infraestrutura n8n/Evolution | Persistente |
| Video API/Worker | Geração assíncrona de vídeos curtos | Implementado |
| Boomploy | Gestão visual, sincronização Git e redeploy de serviços | Implementado |

## 3. Multi-tenancy e identificação por email

Cada cliente é representado por uma conta na coleção `platform_users` e por um documento correspondente na coleção `tenants`. O email da conta é o identificador de autenticação e faturamento. O email corporativo é um campo de perfil separado e pode ser diferente do email usado para entrar na plataforma.

A criação de um cliente deve gravar, no mínimo, os seguintes campos:

| Campo | Descrição |
|---|---|
| `tenant_id` | Identificador interno isolado do cliente |
| `email` | Email principal da conta |
| `account_email` | Email usado para autenticação e faturamento |
| `name` | Nome apresentado na plataforma |
| `empresa_nome` | Nome comercial da empresa |
| `nicho` | Área de atividade do negócio |
| `email_corporativo` | Email público/comercial opcional |
| `redes_sociais` | Objeto com os canais digitais oficiais |
| `instance_name` | Nome da instância Evolution associada |
| `telefone_proprietario` | Número que liga o WhatsApp automatizado |
| `status_plano` | `demonstracao`, `ativo`, `expirado`, `suspenso` ou `cancelado` |
| `data_ativacao` | Data de início da demonstração ou plano |
| `data_expiracao` | Data final da demonstração ou plano |
| `ultimo_tx_id` | Última transação M-Pesa validada |

As redes sociais são armazenadas com chaves controladas para impedir dados arbitrários no contexto da IA:

```json
{
  "facebook": "",
  "instagram": "",
  "twitter_x": "",
  "tiktok": "",
  "telegram": "",
  "linkedin": ""
}
```

O cliente pode editar o perfil empresarial e os links sociais, mas não pode alterar o email de autenticação através do formulário de perfil. O endpoint de atualização sincroniza os dados com o documento `clientes_bot/{instance_name}` quando já existe uma instância WhatsApp.

## 4. Demonstração de dois dias

A demonstração é concedida uma única vez por cliente e dura exactamente **2 dias**. A criação da conta ou o envio do primeiro `TESTE` não inicia o contador. Esses eventos colocam a conta em `trial_pending_connection`, preparam a instância e podem disponibilizar o QR Code. O contador só começa quando a Evolution confirma a primeira transição `CONNECTION_UPDATE=open`, que grava `trial_connected_at` e calcula `trial_expires_at = trial_connected_at + 2 dias`.

Uma conta pendente de ligação não está expirada, mesmo que existam campos antigos `data_ativacao` ou `data_expiracao` sem prova de ligação real. A demonstração é única: voltar a enviar `TESTE` não reinicia o prazo, e uma reconexão posterior não prolonga a data original.

O comportamento obrigatório é o seguinte:

| Situação | Resultado |
|---|---|
| Conta criada ou primeiro pedido `TESTE` | Estado pendente; prepara a instância/QR Code, mas não começa os 2 dias |
| QR enviado, mas WhatsApp ainda não está `open` | O cliente pode fazer perguntas sobre o Negobot Moz; não recebe mensagem de expiração |
| Primeira transição `CONNECTION_UPDATE=open` | Inicia uma única demonstração de 2 dias e grava a hora de ligação |
| Novo `TESTE` durante a demonstração | Não reinicia o prazo; informa que o período já está activo |
| `TESTE` antes de o WhatsApp estar ligado | Mantém a demonstração pendente; não cria outra instância |
| `TESTE` depois da expiração | Bloqueia a automação e pede pagamento, mas o assistente continua a responder perguntas comerciais |
| `#qrcode` enquanto pendente ou activo | Pode preparar/renovar o QR conforme a regra de ligação |
| `#qrcode` depois da expiração | Bloqueia e pede pagamento |
| Pedido de QR Code no site antes da primeira ligação | Permite preparação e devolve estado pendente, sem expirar a demonstração |
| Pedido de QR Code no site depois da expiração | HTTP 402 e nenhuma criação/renovação de instância |
| Pagamento confirmado | Activa o plano pago e permite novo QR Code |

> A mensagem “a sua demonstração terminou” só pode ser enviada quando existe `trial_connected_at` e a hora actual é igual ou posterior a `trial_expires_at`. Perguntas sobre preços, benefícios, pagamento, suporte e funcionamento do Negobot Moz continuam a ser respondidas pelo assistente central, inclusive antes da ligação e depois da expiração.

> A expiração deve ser avaliada pelo servidor. O frontend nunca deve ser a única camada de bloqueio.

## 5. Pagamentos para clientes moçambicanos

O método local é o M-Pesa manual para o número oficial configurado no backend. O cliente pode iniciar o processo pelo WhatsApp ou pela plataforma autenticada.

O processo é composto por quatro etapas. Primeiro, o cliente escolhe o plano. Segundo, transfere o valor por M-Pesa. Terceiro, envia o SMS completo ou o ID da transação pelo WhatsApp ou pelo formulário do site. Quarto, o AutoPay sincroniza a transação no Firebase e o backend valida o destinatário, valor, remetente, estado e reutilização do comprovativo.

A tabela de planos atualmente implementada é:

| Plano | Preço | Validade | Características principais |
|---|---:|---:|---|
| Básico | 500 MT | 30 dias | Até 1.500 conversas/contactos, WhatsApp, 1 utilizador e 2 campanhas por mês |
| Médio | 1.000 MT | 30 dias | Até 5.000 conversas/contactos, WhatsApp + 1 canal adicional aprovado, 3 utilizadores e 10 campanhas por mês |
| Premium | 1.500 MT | 30 dias | Até 15.000 conversas/contactos, WhatsApp + até 3 canais aprovados, 5 utilizadores, IA avançada e 25 campanhas por mês |
| Omnichannel Pro | Sob consulta | Contrato | Todos os canais autorizados, mais utilizadores, API, integrações e campanhas avançadas |

Os extras comerciais previstos são o **Pacote Canais+** (+500 MT/mês, até dois canais adicionais), **Campanhas avançadas** (+500 MT/mês) e **Utilizador adicional** (+100 MT/mês). A activação destes extras é feita após confirmação comercial, porque os fornecedores externos podem exigir aprovação e credenciais próprias.

Os canais adicionais nunca devem ser apresentados como activos apenas por aparecerem no catálogo. Cada canal depende de autorização, credenciais, consentimento e configuração do tenant.

A validação M-Pesa deve impedir a reutilização do mesmo comprovativo. O registo AutoPay é marcado como usado, associado ao tenant e ao número que solicitou a ativação. O remetente da transação deve coincidir com o número informado pelo cliente, salvo exceção operacional tratada pelo administrador.

Depois da confirmação, o backend atualiza `clientes_bot` e `tenants` com o plano, a data de expiração, os limites, a autorização de disparos, o método de pagamento e o ID da transação. Em seguida, prepara a instância Evolution e tenta obter o QR Code. Se a Evolution estiver temporariamente indisponível, o pagamento continua confirmado e o cliente recebe instruções para solicitar novamente `#qrcode` depois.

## 6. Lemon Squeezy para clientes internacionais

Lemon Squeezy é o método destinado a clientes internacionais que possam pagar por cartão, PayPal ou outro método apresentado no checkout. A subscrição só deve ativar ou renovar um plano depois de o webhook assinado ser validado.

As variáveis de produção são mantidas exclusivamente no Boomploy:

```text
LEMONSQUEEZY_STORE_ID
LEMONSQUEEZY_API_KEY
LEMONSQUEEZY_WEBHOOK_SECRET
LEMONSQUEEZY_VARIANT_BASICO
LEMONSQUEEZY_VARIANT_MEDIO
LEMONSQUEEZY_VARIANT_PREMIUM
LEMONSQUEEZY_CURRENCY
```

Os eventos de subscrição devem ser associados ao tenant através do email, customer ID, order ID ou metadados do checkout. Eventos de cancelamento, expiração ou reembolso devem alterar o estado do plano para `cancelado` ou `expirado` e bloquear a geração de novos QR Codes até existir uma nova confirmação válida.

As variáveis Lemon Squeezy estão previstas no ambiente, mas não devem ser preenchidas com valores inventados. Sem credenciais e variantes reais, o checkout internacional permanece desativado e o M-Pesa continua a ser o caminho local para Moçambique.

## 7. Gestão das instâncias WhatsApp e QR Code

Cada cliente deve possuir uma instância Evolution própria, associada ao tenant e ao email da conta. A criação/configuração da instância deve aplicar webhook, eventos `MESSAGES_UPSERT`, `CHATS_UPSERT` e `CONNECTION_UPDATE`, definições de grupos e parâmetros de leitura.

Os endpoints de cliente relacionados com a ligação WhatsApp são:

| Método | Endpoint | Função |
|---|---|---|
| `GET` | `/api/platform/client/integration/status` | Consulta o estado da instância do tenant |
| `POST` | `/api/platform/client/evolution/qr` | Prepara a instância e devolve estado/QR quando permitido |
| `POST` | `/api/platform/client/payments/mpesa/verify` | Valida comprovativo e pode devolver QR após confirmação |

O helper `obter_qrcode_instancia()` centraliza a leitura de estado e QR. O mesmo helper é usado pelo site e pelo fluxo WhatsApp para evitar diferenças entre canais. A instância não deve ser apagada, recriada ou renovada quando o tenant estiver expirado.

O QR Code deve ser apresentado no site como imagem base64 temporária e, no WhatsApp, enviado pelo assistente com instruções para abrir **Aparelhos conectados**. O cliente deve ser informado de que o QR Code expira e que a emissão de um novo código depende do estado válido da demonstração ou do plano pago.

## 8. Atendimento no site e no WhatsApp

O site público disponibiliza o endpoint `/api/platform/public/assistant/chat`, que responde perguntas comerciais, apresenta a tabela de planos e explica o pagamento M-Pesa. A plataforma autenticada disponibiliza o BillingPage para envio do comprovativo e apresentação do QR Code após confirmação.

No WhatsApp, o webhook da Evolution recebe os eventos, valida o payload e encaminha mensagens externas para o fluxo central ou para o fluxo do tenant. Mensagens do próprio bot (`fromMe`) não devem ser tratadas como mensagens de cliente, pois isso criaria ciclos de resposta.

A cadeia de atendimento é:

```text
Evolution API
    -> POST /webhook
    -> validação Flask
    -> Redis whatsapp_incoming_queue
    -> negobot-incoming-worker
    -> fluxo central ou fluxo do tenant
    -> pool de IA/determinístico
    -> Evolution API sendText/sendMedia
```

O fluxo central apresenta a NEGOBOT MOZ, responde saudações e planos de forma determinística, trata dúvidas de pagamento, valida comprovativos e orienta o cliente para demonstração, pagamento e QR Code. O fluxo de tenant utiliza o perfil e a base de conhecimento da empresa cliente.

## 9. Perfil empresarial no contexto da IA

O fluxo de cada tenant constrói um bloco de contexto com nome da empresa, nicho, email corporativo e redes sociais preenchidas. O prompt instrui a IA a divulgar somente os links existentes no perfil oficial. Se uma rede social estiver vazia, o assistente não deve inventar um endereço.

Exemplo de contexto interno:

```text
PERFIL OFICIAL DA EMPRESA:
Nome da empresa: Empresa de Exemplo
Nicho: Restauração
Email corporativo: contacto@empresa.co.mz
Facebook: https://facebook.com/empresa
Instagram: https://instagram.com/empresa
```

As diretrizes corporativas e os documentos enviados pelo cliente continuam a ser considerados juntamente com o perfil. O isolamento por tenant deve ser mantido tanto no carregamento dos documentos como na montagem do prompt.

## 10. Pool multi-provedor de IA

O pool usa rotação round-robin entre provedores configurados e ignora automaticamente aqueles sem chave ou modelo válido. Em caso de falha, timeout ou limite de um provedor, tenta o seguinte; quando todos os primários falham, usa OpenRouter como fallback.

| Provedor | Variável de chave | Variável de modelo |
|---|---|---|
| Groq | `GROQ_API_KEY` | `GROQ_MODEL` |
| Cerebras | `CEREBRAS_API_KEY` | `CEREBRAS_MODEL` |
| SambaNova | `SAMBANOVA_API_KEY` | `SAMBANOVA_MODEL` |
| Gemini conta 1 | `GEMINI_API_KEY` | `GEMINI_MODEL` |
| Gemini conta 2 | `GEMINI_API_KEY_2` | `GEMINI_MODEL_2` |
| GitHub Models | `GITHUB_MODELS_TOKEN` | `GITHUB_MODELS_MODEL` |
| Mistral | `MISTRAL_API_KEY` | `MISTRAL_MODEL` |
| OpenRouter fallback | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL` |

Os valores devem ser introduzidos no cartão **NEGOBOT Backend** do Boomploy. O incoming worker utiliza o mesmo ambiente do backend e deve ser reconstruído depois de alterações. Nenhuma chave deve ser colocada neste documento ou no GitHub.

## 11. Fila Redis e resiliência

O webhook deve retornar HTTP 200 rapidamente e não pode ficar à espera da IA. O produtor cria um envelope com `event_id`, payload e `enqueued_at`, colocando-o em `whatsapp_incoming_queue`. O worker consome os eventos de forma persistente, mede o tempo de espera, chama o processamento legado e confirma (`ACK`) o item apenas depois da execução.

Quando o Redis está indisponível, o backend mantém um fallback temporário para thread, evitando perda imediata de mensagens. Em produção, a biblioteca Redis deve estar instalada e o worker deve permanecer ativo mesmo quando a fila está vazia.

A fila deve ser monitorizada por comprimento, idade do evento mais antigo, taxa de erro, retries e mensagens rejeitadas. O consumidor deve evitar duplicados usando `event_id` ou o ID da mensagem recebido da Evolution.

## 12. Endpoints principais do backend

| Área | Endpoint | Acesso |
|---|---|---|
| Login | `POST /api/platform/auth/login` | Público com rate limit |
| Sessão | `GET /api/platform/auth/me` | Sessão autenticada |
| Planos | `GET /api/platform/client/plans` | Cliente/operator |
| Plano atual | `GET /api/platform/client/plan` | Cliente/operator |
| Perfil | `GET /api/platform/client/profile` | Cliente/operator |
| Atualizar perfil | `PATCH /api/platform/client/profile` | Owner/operator do tenant |
| Conversas | `GET /api/platform/client/conversations` | Cliente/operator |
| M-Pesa | `POST /api/platform/client/payments/mpesa/verify` | Cliente/operator |
| Histórico de pagamentos | `GET /api/platform/client/payments/history` | Cliente/operator |
| Lemon status | `GET /api/platform/client/payments/lemonsqueezy/status` | Cliente/operator |
| Lemon checkout | `POST /api/platform/client/payments/lemonsqueezy/checkout` | Cliente/operator |
| Lemon webhook | `POST /api/platform/webhooks/lemonsqueezy` | Assinatura HMAC |
| QR Code | `POST /api/platform/client/evolution/qr` | Cliente/operator |
| Estado Evolution | `GET /api/platform/client/integration/status` | Cliente/operator |
| Assistente público | `POST /api/platform/public/assistant/chat` | Público com rate limit |
| Campanhas | `POST /api/platform/client/campaigns` | Cliente/operator |
| Métricas | `GET /api/platform/client/metrics` | Cliente/operator |
| Suporte | `/api/platform/client/support/tickets` | Cliente/operator |

## 13. Segurança e isolamento

Todas as rotas privadas devem validar sessão, papel e tenant. O cliente só pode ler e alterar documentos cujo `tenant_id` corresponda à sua identidade. Operações administrativas ficam restritas ao subdomínio da plataforma e aos papéis `owner` e `admin`.

Os tokens e chaves devem ser guardados nos cartões de serviço do Boomploy, nos ficheiros `.env` protegidos ou nos mecanismos de segredo da infraestrutura. Nunca devem ser gravados em commits, documentação, screenshots, relatórios públicos ou mensagens de log.

Os webhooks externos devem validar assinatura, timestamp quando aplicável, request ID e idempotência. Falhas de fornecedor devem produzir mensagens genéricas para o cliente e detalhes apenas nos logs protegidos do backend.

## 14. Operação e deploy

O GitHub é a fonte da verdade para o código. As alterações devem ser feitas em `NEGOBOT-MOZ`, validadas localmente e publicadas na branch `main`. O Boomploy/Compose reconstrói os serviços a partir dessa branch.

Antes de cada publicação, executar:

```bash
python3 -m py_compile routes/platform_routes.py workflows/central_flow.py workflows/client_flow.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
cd platform-react && pnpm run build
```

O deploy pode reconstruir `negobot-backend`, `negobot-incoming-worker` e `negobot-site`. PostgreSQL, Redis, Evolution API, n8n e volumes persistentes não devem ser removidos por deploy normal. A presença de containers órfãos históricos deve ser tratada com cuidado e não com `--volumes` indiscriminado.

A rotação Docker está configurada com `max-size=10m` e `max-file=3`. O disco deve ser acompanhado porque logs, imagens e ficheiros de vídeo podem crescer mesmo quando CPU e RAM estão disponíveis.

## 15. Critérios de aceitação do onboarding

A implementação é considerada correcta quando um cliente novo é criado com email, estado pendente e perfil empresarial inicial; consegue preencher redes sociais; recebe/prepara o QR Code sem iniciar o contador; o WhatsApp ligado em `open` inicia exactamente dois dias; não consegue reiniciar a demonstração depois da expiração; não consegue obter QR Code novo sem pagamento após expirar; consegue enviar comprovativo M-Pesa pelo WhatsApp ou plataforma; recebe QR Code após confirmação; e o assistente continua a responder perguntas sobre o Negobot Moz antes da ligação e depois da expiração.

Para clientes internacionais, o checkout Lemon Squeezy deve aparecer apenas quando estiver configurado com credenciais e variantes válidas. Webhooks inválidos devem ser rejeitados e cancelamentos/refundos devem bloquear o plano. Todos os dados devem permanecer isolados e todas as filas devem continuar a funcionar sem o navegador aberto.

## 16. Estado de implementação

No estado atual, o código funcional está publicado na branch `main`. A implementação inclui trial único de dois dias, bloqueio de QR após expiração, ativação M-Pesa com preparação de QR, perfil empresarial por email, redes sociais por tenant, contexto social no assistente, Redis incoming worker, pool de IA multi-provedor, site React, plataforma React e Lemon Squeezy preparado para credenciais reais.

A configuração Lemon Squeezy é opcional até que o proprietário forneça as credenciais e variantes reais. O atendimento WhatsApp depende ainda de a sessão da instância central Evolution permanecer efetivamente em estado `open`; a interface pode mostrar “Conectados” enquanto a API Baileys ainda estiver em `connecting`, situação que deve ser resolvida pela reconexão da sessão.

## Referências internas

1. [Especificação mestre NEGOBOT MOZ](./negobot-moz-master-spec.md)
2. [Configuração omnichannel n8n](./n8n-omnichannel-setup.md)
3. [Documentação do serviço de vídeo](./video-service.md)
4. [Repositório NEGOBOT-MOZ](https://github.com/VAMOS-tecnico/NEGOBOT-MOZ)
5. [Repositório boomploy-infra](https://github.com/VAMOS-tecnico/boomploy-infra)
