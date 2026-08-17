# Notas sobre Evolution API e áudio

Data da consulta: 2026-08-17.

## Estado das versões

A página oficial de releases mostra `v2.3.7` como release estável/latest e `2.4.0-rc2` como pre-release candidate. A nota da `2.4.0-rc2` recomenda validação e não deployment direto em produção sem testes. A série 2.4 introduz ativação/licenciamento obrigatório e migração de base de dados `RuntimeConfig`, portanto não é um upgrade sem risco.

## Webhook e mídia

A documentação de webhooks descreve `base64: true` no webhook por instância e recomenda configurar eventos de mensagens. O endpoint de recuperação de mídia `POST /chat/getBase64FromMediaMessage/{instance}` documentado no Postman usa apenas `message.key.id` e permite `convertToMp4`.

## Bug conhecido

A issue oficial #2550 indica que `getBase64FromMediaMessage` apresenta falhas com mensagens de áudio `audio/ogg; codecs=opus` na v2.3.7 e também na 2.4.0-rc2; menciona retorno de mídia cifrada quando se tenta descarregar diretamente a URL. Isto é consistente com os testes do NEGOBOT: bytes recebidos sem assinatura `OggS` e Groq Whisper HTTP 400 por mídia inválida.

## Recomendação preliminar

Não atualizar diretamente para 2.4.0-rc2 em produção. A opção de menor risco é manter v2.3.7, preservar o fallback textual para voz e testar uma atualização isolada numa cópia da instância/ambiente. A opção de maior probabilidade de resolver é testar uma versão posterior estável que corrija a recuperação de mídia, mas só depois de backup dos volumes e plano de rollback. Como alternativa, usar um gateway de mídia separado que receba a mensagem antes da Evolution cifrar o conteúdo, ou aceitar temporariamente áudio apenas quando a Evolution fornecer um ficheiro válido.

Fontes:
- https://github.com/EvolutionAPI/evolution-api/releases
- https://github.com/evolution-foundation/evolution-api/issues/2550
- https://evolutionapi-evolution-api-90.mintlify.app/concepts/webhooks
- https://www.postman.com/agenciadgcode/evolution-api/request/t64zlpo/get-base64-from-media-message
