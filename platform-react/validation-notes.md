Validação inicial React — 2026-08-16

A build local foi concluída com sucesso usando `pnpm run build`.

O primeiro acesso ao preview foi bloqueado pelo hostname temporário do Vite; foi corrigido com `server.allowedHosts=true` apenas na configuração de desenvolvimento.

Após reiniciar o preview, `/plataforma/login` carregou corretamente com título NEGOBOT-MOZ | Plataforma, formulário de identificador, palavra-passe e botão Entrar na plataforma.

A interface visual usa tema escuro grafite/verde, cartão central, tipografia Space Grotesk/DM Sans e layout responsivo. Ainda não foi publicada no VPS nem substituiu o `platform.html` existente.
