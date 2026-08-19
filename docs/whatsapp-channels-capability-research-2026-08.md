# Pesquisa de capacidade: WhatsApp Channels — 2026-08

## Conclusão preliminar

A documentação oficial da Evolution API apresenta **Evolution Channel** como uma integração universal de entrada de mensagens por webhooks. O texto descreve a criação de uma instância com `integration: "EVOLUTION"`, um webhook `/webhook/evolution` para receber mensagens e feedback/postbacks por webhook, RabbitMQ ou SQS. Isto não é a funcionalidade nativa de **WhatsApp Channels** (canais de transmissão seguidos por utilizadores).

A página oficial de visão geral da Evolution API descreve suporte a Baileys/WhatsApp Web, WhatsApp Cloud API, mensagens, grupos e contactos; não documenta endpoints de listar WhatsApp Channels, verificar administrador de um canal, criar publicações de canal ou enviar reacções de seguidores.

A documentação oficial de webhooks lista eventos para mensagens, grupos e participantes de grupos, mas não apresenta um evento `CHANNELS_UPSERT`, `NEWSLETTERS_UPSERT` ou equivalente para administrar Canais. O código actual do NEGOBOT já trata `@newsletter` como newsletter/canal e ignora a mensagem, mas isso é apenas filtragem de mensagens recebidas; não prova suporte de publicação.

## Implicação de arquitectura

Não se deve marcar WhatsApp Channels como `connected` nem construir um botão que simule publicação até existir um adaptador real e verificável. A UI deve mostrar `pending_authorization`/`pending_review` para esta capacidade, mantendo grupos próprios e conversas privadas separados.

Pode-se preparar o contrato de publicações agendadas, CTA e fila Redis de forma provider-neutral, mas a etapa de entrega deve falhar fechada com `outbound_adapter_not_configured` até uma API que exponha publicação em canais e a validação de administrador. O módulo não deve reutilizar automaticamente o endpoint de texto para `@newsletter`, pois isso não confirma permissão nem suporte do fornecedor.

## Fontes consultadas

1. Evolution API — visão geral oficial: https://docs.evolutionfoundation.com.br/en/evolution-api
2. Evolution API — Evolution Channel oficial: https://docs.evolutionfoundation.com.br/en/evolution-api/integrations/evolution-channel
3. Evolution API — Webhooks oficial: https://docs.evolutionfoundation.com.br/en/evolution-api/configuration/webhooks
4. Evolution API — Get Group Info/Participants: https://docs.evolutionfoundation.com.br/en/evolution-api/get-group-info e https://docs.evolutionfoundation.com.br/en/evolution-api/get-participants

## Verificação adicional no repositório oficial

A issue oficial #1723 descreve que o tratamento de `@newsletter` foi solicitado porque apenas o endpoint de texto teria sido ajustado, permanecendo pendentes os restantes endpoints, permissões `SEND_MESSAGES` e documentação. A issue oficial #1857 solicita um controlador de canais, um endpoint semelhante a `/fetchAllChannels/{instance}` e a aceitação de JIDs `@newsletter` no envio; encontra-se fechada como `not planned`. Isto confirma que não existe um contrato público e estável na Evolution API v2.3.7 para listar canais, validar administrador ou publicar com garantias.

A implementação do NEGOBOT deve, portanto, separar **preparação do módulo** de **entrega real**. O editor, agenda, CTA, auditoria e fila podem ser construídos agora; a fila deve marcar a publicação como `outbound_adapter_not_configured` e não chamar `sendText` para `@newsletter` até ser instalado um adaptador oficialmente verificado ou um fornecedor autorizado com contrato claro.

Fontes adicionais:

5. Evolution API issue #1723 — suporte de envio para `@newsletter`: https://github.com/evolution-foundation/evolution-api/issues/1723
6. Evolution API issue #1857 — pedido de controlador de canais, fechado `not planned`: https://github.com/evolution-foundation/evolution-api/issues/1857
7. Evolution API changelog 2.3.7: https://github.com/evolution-foundation/evolution-api/blob/main/CHANGELOG.md
