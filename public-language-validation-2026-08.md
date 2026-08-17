# Validação PT/EN do site público

Data: 17 de agosto de 2026.

O build React foi executado com `pnpm exec tsc --noEmit` e `pnpm build`, sem erros. A pré-visualização foi aberta no browser em PT e o botão `EN` foi acionado.

Em inglês, foram confirmadas a navegação `Capabilities`, `Plans`, `How it works`, `Contact`, o CTA `Talk to an assistant`, o hero `More answers. More business.`, capacidades, planos, benefícios, fluxo de funcionamento e chamadas finais. O seletor mostra `PT / EN` e o idioma é guardado em `localStorage` com a chave `negobot-public-language`.

O mesmo seletor foi adicionado à página pública `/assistente`. A preferência é aplicada também ao atributo `document.documentElement.lang`, permitindo melhor acessibilidade e indexação.
