# Comparação das respostas do bot com o roteiro

## Resultado

As últimas respostas não estão todas de acordo com o roteiro implementado. O fluxo de geração de imagem está alinhado, mas as saudações e a resposta sobre preços estão demasiado genéricas. As respostas sobre áudio correspondem ao problema de mídia da Evolution observado nos testes anteriores.

## Evidência recente

| Hora UTC | Resposta observada | Avaliação |
|---|---|---|
| 00:17:33 | "Olá! Como posso ajudar você hoje no NEGOBOT MOZ?" | Fora do roteiro: devia apresentar imediatamente o Negobot Moz e convidar para o teste. |
| 00:18:08 | Explica o comando `#imagem` para criar artes | Alinhada com o handler e com o prompt comercial. |
| 00:18:45 | Diz que os preços variam e pede mais detalhes | Fora do roteiro se a pergunta era sobre preços: devia apresentar Básico, Médio e Premium com valores e benefícios. |
| 23:38–23:45 | Diz que não consegue ouvir/processar áudios | Compatível com a limitação real da mídia da Evolution, mas não com a promessa do Plano Premium; o fallback deve ser claro e não inventar uma transcrição. |

## Comparação com o código

Em `workflows/central_flow.py`, saudações e perguntas gerais seguem para `processar_resposta_ia`. Em `services/flow_handlers.py`, o prompt comercial exige uma apresentação do Negobot em saudações simples, proíbe frases genéricas de suporte e exige a tabela completa de planos quando o cliente pergunta por preços. O handler de `#imagem` é determinístico e está alinhado.

A divergência mais importante é que o sistema depende demasiado da obediência do modelo ao prompt para preços e saudações. A correção recomendada é criar handlers determinísticos para saudações e preços, em vez de deixar esses casos exclusivamente na Groq.

## Correções recomendadas

1. Interceptar saudações simples e enviar uma apresentação fixa com o convite `TESTE`.
2. Interceptar palavras como `preço`, `planos`, `quanto custa` e `benefícios` e enviar a tabela oficial dos três planos.
3. Manter `#imagem`, `#pago`, `#qrcode` e atendimento humano como handlers determinísticos.
4. Manter o fallback de áudio até a Evolution devolver mídia válida; não afirmar que o áudio foi transcrito quando o Whisper falhar.

Nenhuma alteração foi aplicada nesta comparação; o relatório apenas identifica as divergências.
