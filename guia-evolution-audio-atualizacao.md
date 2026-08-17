# Evolution API: atualização ou contorno do problema de áudio

## Diagnóstico atual

A instalação em produção está na Evolution API `v2.3.7`. A mensagem de voz chega ao webhook, mas o endpoint de recuperação de mídia devolve bytes que não têm assinatura de OGG ou MP4. O Whisper da Groq rejeita esse ficheiro com HTTP 400. A chave Groq e o fluxo de mensagens de texto estão operacionais.

A documentação da Evolution indica que o endpoint `POST /chat/getBase64FromMediaMessage/{instance}` usa `message.key.id` e aceita `convertToMp4`. Aplicámos esse formato e testámos também `base64=true` no webhook, sem obter uma mídia válida. Existe uma issue oficial que documenta falhas semelhantes com áudio `audio/ogg; codecs=opus` na v2.3.7 e na v2.4.0-rc2.

## Recomendação

Não substituir diretamente a versão em produção neste momento. A página oficial de releases identifica `v2.3.7` como release estável/latest e `2.4.0-rc2` como pre-release candidate. Além disso, a série 2.4 introduz ativação/licenciamento obrigatório e migração da tabela `RuntimeConfig`; portanto, não é uma atualização simples.

A estratégia recomendada é testar a versão mais recente num ambiente isolado, com uma instância WhatsApp de teste, sem reutilizar simultaneamente o volume ou a sessão da produção. Só depois de confirmar áudio, QR Code, mensagens, webhooks e n8n se decide uma promoção controlada.

## Plano seguro de atualização

### 1. Preparação e backup

Antes de qualquer alteração, guardar cópias de `docker-compose.yml`, `.env`, Caddyfile e da configuração do Boomploy. Fazer também backup dos volumes persistentes da Evolution e da base de dados, sem apagar nenhum volume. A sessão `assistente_negobot` deve continuar a ser usada apenas pela versão atual enquanto o teste estiver em curso.

### 2. Ambiente isolado

Criar um serviço de teste com outro nome, outra porta interna, outra base de dados/schema e uma instância WhatsApp de teste. O ambiente de teste deve usar uma cópia controlada dos ficheiros de configuração, mas não deve montar o volume de sessão da produção em simultâneo. O número de teste deve ser ligado por QR Code próprio.

### 3. Testes obrigatórios

No ambiente de teste, verificar: mensagem de texto; mensagem de voz curta; áudio `audio/ogg; codecs=opus`; transcrição para Português; resposta do bot; `#qrcode`; webhook `MESSAGES_UPSERT`; n8n; envio de imagem; pagamentos e QR Code da plataforma. Confirmar que o áudio descarregado começa por uma assinatura válida como `OggS` ou `ftyp` antes de enviá-lo ao Whisper.

### 4. Promoção ou rollback

Se a versão de teste resolver o áudio sem quebrar os restantes fluxos, agendar uma janela de manutenção. Parar apenas a Evolution durante a troca, preservar os volumes, atualizar a imagem e iniciar novamente. Confirmar estado `open`, QR Code, webhook e mensagens. Se qualquer teste falhar, voltar à imagem `v2.3.7` e aos ficheiros anteriores, sem remover volumes.

## Contornos possíveis enquanto o teste decorre

O contorno atual mais seguro é manter o fallback: quando a voz não pode ser transcrita, o bot informa a pessoa e pede uma mensagem escrita. Isto evita respostas inventadas e mantém o bot operacional.

Outra opção é usar um gateway externo ou uma versão alternativa do conector WhatsApp que entregue mídia já descodificada. O endpoint `/chat/getBase64FromMediaMessage` da própria Evolution não é suficiente quando devolve mídia cifrada; converter o ficheiro com FFmpeg não resolve bytes que ainda não são um contentor de áudio válido.

Também é possível avaliar o fluxo n8n como camada de mídia, mas só será uma solução real se o n8n receber uma URL ou base64 decifrado. Apenas encaminhar o mesmo payload para o n8n não contorna a limitação.

## Decisão recomendada

Manter a produção em `v2.3.7`, preservar o fallback textual e preparar um ambiente de teste separado. Não atualizar diretamente para `2.4.0-rc2` sem aceitar previamente o impacto de licenciamento e migração. A atualização em produção só deve ocorrer depois de um teste de voz bem-sucedido e de um plano de rollback confirmado.

## Fontes

1. https://github.com/EvolutionAPI/evolution-api/releases
2. https://github.com/evolution-foundation/evolution-api/issues/2550
3. https://evolutionapi-evolution-api-90.mintlify.app/concepts/webhooks
4. https://www.postman.com/agenciadgcode/evolution-api/request/t64zlpo/get-base64-from-media-message
