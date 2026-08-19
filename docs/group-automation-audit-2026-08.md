# Auditoria do módulo de grupos próprios — 2026-08

## Estado encontrado

O webhook em `routes/webhook_routes.py` ignorava todos os JIDs `@g.us` antes do processamento do fluxo. O `client_flow.py` e o `central_flow.py` também mantinham bloqueios de grupos. A sincronização antiga em `services/evolution_service.py` usava `GET /group/fetchAllGroups/{instance}?getParticipants=true` e gravava membros em `base_contactos`, sem verificar se a instância era administradora e sem uma regra de consentimento para marketing.

O Compose já possui um `incoming_worker.py` persistente que consome `whatsapp_incoming_queue`; portanto, o processamento de eventos de grupos pode permanecer no mesmo caminho de webhook/worker, sem criar uma fila concorrente ou depender do browser. O novo módulo deve interceptar grupos antes do bloqueio legado e deixar intactos os fluxos privados.

## Contrato seguro decidido

Cada documento de grupo será tenant-scoped e guardará `tenant_id`, `instance_name`, `group_jid`, `name`, `bot_jid`, `bot_is_admin`, `admin_verified_at`, `status`, `automation_enabled`, `mention_required`, `welcome_enabled`, `keywords`, `welcome_message`, `last_event_at` e `last_error`. A API nunca aceitará um JID arbitrário como autorizado: o grupo só será activado depois de uma sincronização que confirme a instância como participante com `isAdmin=true`, `isSuperAdmin=true`, `admin=true`, `superadmin=true`, `creator` ou papel equivalente.

A documentação oficial da Evolution API v2.3.7 define `GET /group/participants/{instanceName}?groupJid=...` e devolve participantes com `id`, `isAdmin` e `isSuperAdmin`. Também documenta os eventos `GROUPS_UPSERT`, `GROUPS_UPDATE` e `GROUP_PARTICIPANTS_UPDATE`, com acções `add`, `remove`, `promote` e `demote`. O webhook de cada instância será actualizado para incluir esses eventos e `groupsIgnore=false`.

## Regra de execução

Mensagens em grupos de terceiros são ignoradas. Em grupos próprios activos, o bot só processa mensagens que contenham menção ao bot ou um comando directo autorizado. Keywords podem responder deterministicamente; menções sem keyword podem usar o pool de IA, sempre com o prompt tenant-scoped. Entradas de novos membros só geram boas-vindas quando o grupo continua com `bot_is_admin=true`, `welcome_enabled=true` e o evento é idempotente.

A automação nunca extrai membros de grupos para campanhas privadas. Mensagens de campanha para grupos, quando implementadas na UI, serão enviadas apenas ao JID do grupo próprio autorizado, nunca aos participantes individuais.
