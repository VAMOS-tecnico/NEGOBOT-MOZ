# Auditoria do ambiente do AI Worker CPX32

**Data:** 21 de Agosto de 2026  
**Servidor:** `ubuntu-8gb-hel1-1` / CPX32  
**Container:** `negobot-ai-worker`

## Conclusão executiva

O AI Worker está operacional: o container está `running`, `healthy` e com zero reinícios desde o último redeploy. O `REDIS_URL` está carregado e o healthcheck do worker confirma a existência do heartbeat Redis.

O ficheiro do worker contém 21 variáveis válidas, sem chaves duplicadas, e todas as 21 são carregadas no container. Não existe divergência entre o ambiente gerido pelo Boomploy e o ambiente efectivamente usado pelo processo. O ficheiro remoto está protegido com modo `640` e pertence a `boomploy-agent:boomploy-agent`.

O problema não é excesso de variáveis duplicadas no ficheiro. O problema é que existem vários fornecedores configurados como fallbacks, mas alguns têm modelos antigos, contas sem saldo/permissão ou endpoints que já não respondem ao modelo configurado.

## Inventário funcional

| Grupo | Variáveis | Estado |
|---|---:|---|
| Contrato e fila | `NEGOBOT_SERVICE_PROFILE`, `REDIS_URL`, `AI_QUEUE` | Carregadas; perfil `ai` e fila definidos |
| Timeouts e limite | `AI_PRIMARY_TIMEOUT`, `AI_FALLBACK_TIMEOUT`, `AI_QUEUE_MAX_PER_SECOND` | Carregadas e com valores válidos |
| Groq | `GROQ_API_KEY`, `GROQ_MODEL` | **Funcional**; `qwen/qwen3.6-27b` respondeu com HTTP 200 e JSON mode |
| Cerebras | `CEREBRAS_API_KEY`, `CEREBRAS_MODEL` | Chave reconhecida, mas o modelo configurado devolve 404 |
| SambaNova | `SAMBANOVA_API_KEY`, `SAMBANOVA_MODEL` | Endpoint reconhece a chave, mas geração devolve HTTP 402 por falta de método de pagamento |
| Gemini | Duas chaves e dois modelos | Chaves reconhecidas, mas `gemini-2.0-flash` já não está disponível |
| Mistral | `MISTRAL_API_KEY`, `MISTRAL_MODEL` | **Funcional**; chamadas reais terminaram com sucesso |
| GitHub Models | `GITHUB_MODELS_TOKEN`, `GITHUB_MODELS_MODEL` | Pedido real devolve 404; não deve permanecer como fallback activo sem correcção |
| OpenRouter | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Endpoint de modelos responde 200; como Mistral/Groq funcionaram, o fallback não foi necessário no teste |

## Testes realizados

Foram executados testes de presença, sintaxe e carregamento sem imprimir os valores das chaves. Não foram encontradas linhas inválidas nem chaves duplicadas. A comparação entre o ficheiro e o container apresentou zero variáveis do AI Worker em falta.

Os endpoints de modelos de Groq, Cerebras, SambaNova, Mistral, OpenRouter e Gemini responderam. O teste funcional através do próprio pool do worker confirmou Groq e Mistral. Durante a rotação, os restantes fornecedores produziram os erros seguintes:

| Fornecedor | Resultado | Interpretação |
|---|---|---|
| Groq | HTTP 200 | Chave e modelo funcionais |
| Mistral | Sucesso | Chave e modelo funcionais |
| Cerebras | HTTP 404 | `llama-3.3-70b` não existe ou não está autorizado; a conta lista `gpt-oss-120b` e `gemma-4-31b` |
| SambaNova | HTTP 402 | É necessária configuração de pagamento; o modelo existe na conta, mas a geração está bloqueada |
| Gemini | HTTP 404 | `gemini-2.0-flash` foi descontinuado; a conta lista, entre outros, `gemini-3.6-flash` |
| GitHub Models | HTTP 404 | O modelo/endereço actualmente configurado não está utilizável |
| OpenRouter | Não foi necessário | Está reservado para fallback final; o modelo implícito é `openrouter/free` |

## Recomendações seguras

Não apagar chaves antigas automaticamente. A configuração pode ser reduzida sem destruir credenciais, mantendo Groq como primário, Mistral como fallback imediato e OpenRouter como fallback final.

Antes de alterar o ambiente pelo Boomploy, recomenda-se corrigir `CEREBRAS_MODEL` para um modelo realmente listado pela conta, actualizar ambos os modelos Gemini para um modelo disponível, e decidir se SambaNova e GitHub Models devem continuar activos. SambaNova não ficará funcional enquanto a exigência de pagamento não for resolvida.

Também é recomendável remover a duplicação operacional de Gemini: existem duas chaves (`GEMINI_API_KEY` e `GEMINI_API_KEY_2`) associadas ao mesmo modelo antigo. Isto não é uma duplicação de nome de variável, mas faz o pool tentar duas vezes o mesmo fornecedor indisponível.

## Referências

[1]: https://console.groq.com/docs/text-chat "Groq Text Chat API"
[2]: https://inference-docs.cerebras.ai/api-reference/chat-completions "Cerebras Chat Completions"
[3]: https://docs.mistral.ai/api/ "Mistral API documentation"
[4]: https://ai.google.dev/gemini-api/docs "Google Gemini API documentation"
[5]: https://openrouter.ai/docs/api-reference/overview "OpenRouter API documentation"

## Verificação adicional no Boomploy

O cartão `Negobot Ai Worker (CPX32)` está autenticado no painel. Foram confirmados os campos do ambiente sem copiar os valores secretos. O painel mostra o serviço CPX32 como `running`; os modelos actualmente visíveis são `llama-3.3-70b` para Cerebras, `gemini-2.0-flash` para as duas entradas Gemini, `meta-llama-3.1-70b-instruct` para GitHub Models, `qwen/qwen3.6-27b` para Groq, `mistral-small-latest` para Mistral e `Meta-Llama-3.3-70B-Instruct` para SambaNova.

A acção planeada é alterar apenas os modelos já confirmados como inválidos: Cerebras para `gpt-oss-120b` e Gemini para `gemini-3.6-flash`. As credenciais e as restantes variáveis permanecem intactas.

## Correcção aplicada pelo Boomploy

No cartão `Negobot Ai Worker (CPX32)`, foram actualizados apenas `CEREBRAS_MODEL` para `gpt-oss-120b` e `GEMINI_MODEL`/`GEMINI_MODEL_2` para `gemini-3.6-flash`. O Boomploy confirmou “Variáveis guardadas no .env deste serviço” e o redeploy do serviço CPX32 foi accionado. Nenhuma chave ou outra variável foi alterada.

## Publicação da correcção

O código foi validado com 142 testes do projecto e publicado no GitHub no commit `2f1a6ea` (`fix(ai): validate providers and tolerate Groq JSON responses`). O commit inclui o script `scripts/test_ai_providers.py`, o parser robusto de JSON do pipeline de vídeos e este relatório. O Boomploy confirmou que as variáveis corrigidas foram guardadas e que o AI Worker CPX32 iniciou novamente com o perfil `ai`.

## Validação final após a correcção

Depois do redeploy do AI Worker CPX32, o container ficou `running`, `healthy` e com zero reinícios. O teste individual com orçamento de resposta suficiente passou em Groq (`qwen/qwen3.6-27b`), Gemini 1 e Gemini 2 (`gemini-3.6-flash`), Mistral (`mistral-small-latest`) e OpenRouter (`openrouter/free`).

Cerebras (`gpt-oss-120b`) e SambaNova (`Meta-Llama-3.3-70B-Instruct`) continuam a responder HTTP 402 por restrição de pagamento da conta, não por erro de variável. GitHub Models continua a responder HTTP 404 com o modelo configurado. Estes três fornecedores não foram apagados nem usados para interromper o worker; o pool continua a fazer fallback para os fornecedores funcionais.

O script de teste foi ajustado para usar até 400 tokens no teste rápido, pois alguns modelos com raciocínio devolvem HTTP 200 mas ficam sem conteúdo quando o limite é demasiado baixo. A opção `--json-mode` permanece disponível para verificar compatibilidade JSON separadamente.
