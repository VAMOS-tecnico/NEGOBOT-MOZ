# Notas de política para campanhas WhatsApp — 2026-08

Fontes oficiais consultadas em 2026-08-19:

- https://whatsappbusiness.com/policy/
- https://developers.facebook.com/documentation/business-messaging/whatsapp/getting-opt-in
- https://developers.facebook.com/documentation/business-messaging/whatsapp/policy-enforcement

## Regras que afectam o worker

1. O negócio só deve contactar pessoas que forneceram o número e deram opt-in para receber mensagens da empresa.
2. O opt-in deve indicar claramente o nome do negócio e que a pessoa está a autorizar comunicações; o método pode ser website, SMS, telefone ou presencial, desde que cumpra a lei aplicável.
3. O sistema deve respeitar pedidos de bloqueio, interrupção e opt-out, removendo a pessoa da lista de contactos de WhatsApp.
4. Para a WhatsApp Business Platform, conversas iniciadas pela empresa fora da janela de atendimento exigem Message Templates aprovados; respostas dentro de 24 horas podem ser automáticas sem template.
5. Feedback negativo, bloqueios, denúncias e mensagens não autorizadas podem causar limitação progressiva ou suspensão da conta.
6. A Meta recomenda opt-in por categoria de mensagem quando aplicável, instruções claras de opt-out e monitorização da qualidade.
7. A implementação não deve tentar contornar limites, revisão ou detecção de spam. Deve parar ou reduzir envios quando houver sinais de qualidade baixa.

## Aplicação na NEGOBOT-MOZ

- Campanhas individuais: somente `contacts.opt_in == true`, com origem e timestamp do consentimento.
- Opt-out: palavras como `PARAR`, `STOP` e `SAIR` devem desactivar o contacto e impedir novos envios.
- Grupos: apenas grupos explicitamente seleccionados e autorizados pelo cliente; não copiar automaticamente membros de grupos para marketing.
- Fila: cada destinatário deve ter estado, tentativas, erro, data de envio e chave idempotente.
- Segurança: cada consulta e cada job devem validar `tenant_id` e a instância Evolution associada.
- Agendamento: respeitar horário local configurado, janela de silêncio, limite por campanha e limite diário do tenant.
- O worker deve suportar pausa/cancelamento e não deve enviar se o tenant estiver sem WhatsApp `open`, sem consentimento ou com trial/plano sem entitlement de campanha.
