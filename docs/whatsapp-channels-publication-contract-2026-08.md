# Contrato do módulo de publicações em WhatsApp Channels

## Estado real do fornecedor

A Evolution API v2.3.7 instalada no projecto não fornece um controlador documentado de WhatsApp Channels nativos. Por isso, o NEGOBOT não deve reutilizar automaticamente o envio de texto para JIDs `@newsletter`, nem afirmar que o cliente tem um canal ligado sem credencial, validação de administrador, evento e adaptador de saída verificáveis.

## Modelo de dados

As publicações são guardadas em `channel_publications` com `tenant_id`, `channel_type: whatsapp_newsletter`, `channel_jid`, `channel_name`, `title`, `body`, `cta_url`, `cta_label`, `scheduled_at`, `timezone`, `status`, `delivery_status`, `adapter_status`, `authorization_status`, `administrator_verified`, `created_at`, `updated_at`, `published_at` e `last_error`.

O JID só pode ser guardado como destino de publicação depois de uma integração futura confirmar o canal e os privilégios do número conectado. A criação de um rascunho não equivale a ligação do canal.

## Estados

`draft` significa que o editor guardou conteúdo sem publicação. `scheduled` significa que existe uma hora futura, mas não garante entrega. `blocked` com `delivery_status: outbound_adapter_not_configured` significa que a fila processou o trabalho, mas o sistema recusou deliberadamente o envio porque a Evolution actual não possui um adaptador de Channels validado. `published` só será permitido depois de um adaptador autorizado devolver confirmação de saída.

## Fila

O worker usa Redis persistente, com a lista `negobot:channel-publications` e o ZSET `negobot:channel-publications:scheduled`. Isto mantém o mesmo sistema de filas do NEGOBOT e evita introduzir BullMQ/Node num backend Flask/Python já operacional. A fila nunca chama `sendText` para `@newsletter` sem adapter.

## CTA

`cta_url` só aceita URLs absolutas `https://` ou `http://`, com limite de 500 caracteres. O CTA é conteúdo do post e não transforma o canal num chat; conversões devem seguir para o atendimento privado ou para o site/checkout.
