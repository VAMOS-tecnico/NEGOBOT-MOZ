# Recuperação de palavra-passe por email

A plataforma agora inclui `Forgot password?` no login e um formulário `Reset password` ligado por token temporário.

## Fluxo

1. O cliente introduz o email usado no registo da plataforma.
2. O Backend responde sempre com a mesma mensagem, exista ou não uma conta, para não revelar quais emails estão registados.
3. Se existir uma conta activa e o SMTP estiver configurado, o cliente recebe uma ligação temporária.
4. A ligação expira por defeito em 30 minutos e só pode ser usada uma vez.
5. O novo segredo é guardado apenas como hash no documento `platform_users`; a palavra-passe antiga nunca é enviada nem mostrada.

## Variáveis do NEGOBOT Backend

Adicionar no cartão **NEGOBOT Backend** do Boomploy, sem colocar os valores no Site/frontend:

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=mailer@example.com
SMTP_PASSWORD=<segredo-do-provedor>
SMTP_FROM=NEGOBOT-MOZ <mailer@example.com>
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=20
PASSWORD_RESET_TTL_MINUTES=30
```

O fornecedor pode ser um serviço SMTP transaccional ou um servidor SMTP empresarial. Para Gmail/Google Workspace deve ser usada uma App Password ou credencial SMTP apropriada; nunca deve ser usada a palavra-passe normal da conta.

Depois de guardar as variáveis no **NEGOBOT Backend**, fazer redeploy apenas do Backend. O Site não deve receber `SMTP_PASSWORD`, `SMTP_USER` ou qualquer outro segredo SMTP.

## Endpoints internos

- `POST /api/platform/auth/forgot-password`
- `POST /api/platform/auth/reset-password`

As respostas públicas não confirmam se o email existe. O token é guardado como SHA-256, não em texto simples.
