# Plano de melhoria da plataforma do cliente — NEGOBOT MOZ

**Data:** 21 de Agosto de 2026
**Objectivo:** tornar a plataforma mais simples, bilingue, orientada à activação e segura para cada tenant.

## Prioridades aprovadas para a primeira iteração

| Prioridade | Problema observado | Melhoria proposta | Critério de aceitação |
|---|---|---|---|
| P0 | O cliente entra, mas o onboarding continua quase todo em português | Tornar onboarding 100% PT/EN, incluindo labels, planos, trial, canais e mensagens de erro | A troca PT/EN não deixa texto operacional misturado |
| P0 | Algumas páginas calculam `english`, mas mantêm labels e placeholders hard-coded | Completar tradução nas áreas críticas: Conversas, Campanhas, Plano, WhatsApp, Canais e Suporte | Em English, labels, botões, erros, estados e instruções ficam em inglês |
| P0 | O cliente pode não saber o próximo passo | Tornar o percurso visível: perfil → primeiro canal → trial → plano; manter banners de trial e CTAs contextuais | O cliente consegue identificar a próxima acção sem suporte |
| P1 | O sistema de tradução DOM pode falhar em conteúdo dinâmico | Preferir textos condicionais nos componentes e usar o dicionário apenas como compatibilidade | Conteúdo carregado depois da API mantém o idioma seleccionado |
| P1 | Estados de canais e operações podem parecer mais activos do que estão | Manter estados honestos: connected, pending, review, not configured e error | Nenhuma integração é apresentada como ligada só por existir um cartão |
| P1 | Formulários longos e feedback pouco consistente | Melhorar agrupamento, mensagens de sucesso/erro, estados vazios e aria-labels | Formulários são utilizáveis em mobile e teclado |
| P2 | Vídeos, campanhas e extras já existem mas não são sempre autoexplicativos | Refinar instruções e pré-visualizações sem alterar os contratos de backend | O cliente entende limites, consentimento, agendamento e custos |

## Fora desta iteração

Não alterar o isolamento por `tenant_id`, o trial central de 2 dias, Evolution API, filas Redis, M-Pesa, Lemon Squeezy, tokens Telegram ou permissões de grupos. Não activar APIs que ainda dependem de aprovação de Meta, TikTok, X ou LinkedIn.

## Sequência de entrega

Primeiro será actualizado o onboarding e a camada de textos. Depois serão melhoradas as páginas do cliente mais usadas. Em seguida serão executados `pnpm run check`, `pnpm run build`, testes backend e smoke tests sem criar pagamentos ou contas reais. O redeploy só será feito depois de confirmar o diff e os serviços afectados.
