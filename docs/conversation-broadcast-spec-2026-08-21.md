# Especificação: campanhas para conversas existentes

**Data:** 21 de Agosto de 2026

## Objectivo

Permitir ao cliente seleccionar pessoas que já têm uma conversa registada com o negócio, usando a campanha persistente existente. A função não extrai membros de grupos e não transforma a existência de uma conversa em autorização automática para marketing.

## Regras de elegibilidade

Uma conversa só pode entrar na audiência quando o telefone pertence ao tenant autenticado, existe uma conversa em `clientes_bot/{tenant_id}/conversas/{phone}`, o documento possui uma interacção registada e existe um contacto correspondente em `contacts` com `opt_in == true` e sem `do_not_contact`.

A API deve devolver apenas metadados mínimos: telefone mascarado ou normalizado, nome disponível, última interacção, última mensagem e estado de atendimento. Não deve devolver histórico completo nem segredos.

## Janela de atendimento

A opção de conversa existente é uma fonte de audiência, não uma autorização para ignorar as regras de envio. O worker continua a validar `opt_in` no momento do envio. Fora da janela de atendimento, campanhas iniciadas pela empresa devem usar o mecanismo de template aprovado aplicável ao canal. Conversas sem opt-in ficam visíveis como não elegíveis e não podem ser seleccionadas.

## Contrato de campanha

A criação de campanha recebe `include_conversations: boolean`. Quando verdadeiro, o backend procura conversas do tenant, cruza-as com contactos autorizados pelo mesmo telefone, aplica tags quando solicitadas, limita o resultado a `recipient_limit` e cria os destinatários como `recipient_type: contact`. Assim, o worker existente mantém a revalidação de opt-in, lock por destinatário, limite diário, silêncio, pausa, cancelamento, retries e idempotência.

A campanha guarda `include_conversations`, `conversation_count` e `contacts_count`. A contagem de conversas representa apenas a origem da audiência; os destinatários continuam a ser contactos revalidados.

## Interface

O compositor mantém uma única campanha e apresenta uma caixa “Conversas existentes com opt-in”. O cliente vê a quantidade elegível e uma explicação: “Conversas sem consentimento não entram; não são extraídos membros de grupos.” A confirmação de consentimento é obrigatória quando contactos ou conversas forem incluídos.

## Não permitido

Não são elegíveis números extraídos de grupos de terceiros, conversas sem opt-in, pessoas bloqueadas, contactos com `do_not_contact`, números inválidos ou documentos pertencentes a outro tenant. O sistema não deve enviar uma mensagem privada apenas por o número aparecer numa conversa ou grupo.

## Rollback

A alteração é compatível com campanhas existentes: `include_conversations` ausente equivale a `false`, e o worker continua a aceitar apenas destinatários contact/group. Se a nova função falhar, o campo pode ser desactivado sem alterar campanhas anteriores.

## Validação e publicação

O commit `2732e60` foi publicado no GitHub. A suite passou com **131 testes**, a compilação TypeScript passou e o build Vite foi concluído. O Backend está `healthy`, o Campaign Worker actualizado no CPX32 está `running` e o site publicou o bundle `index-BF7Qz38g.js` com os marcadores da nova audiência de conversas.

Durante o deploy foi detectada uma publicação ausente da porta privada do Redis. O Compose foi corrigido com backup e o Redis foi recriado exclusivamente com `10.0.0.2:6379:6379`; o volume `infra_redis_data` foi preservado. A CPX32 voltou a comunicar com o Redis e os nove workers ficaram activos. Nenhum envio real foi efectuado durante os testes.
