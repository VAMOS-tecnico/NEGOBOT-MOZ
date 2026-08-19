# Estado da configuração OAuth no Boomploy — 2026-08-19

O painel Boomploy foi desbloqueado pelo utilizador e o serviço correcto é `NEGOBOT Backend`, com `.env` em `/opt/infra/services/negobot-backend/.env`.

A sessão mostra que as variáveis OAuth Meta/TikTok ainda não estão no catálogo do Backend. O formulário de nova variável foi preenchido, mas ainda não foi guardado porque faltam as credenciais privadas dos fornecedores.

Valores públicos que devem ser configurados no Backend:

- `PUBLIC_API_BASE_URL=https://negobot-api.duckdns.org`
- `PUBLIC_APP_BASE_URL=https://app-negobotmoz.duckdns.org/plataforma`
- `TIKTOK_REDIRECT_URI=https://negobot-api.duckdns.org/api/platform/client/channels/tiktok/callback`
- `TIKTOK_SCOPES=user.info.basic,video.list`
- `META_INSTAGRAM_REDIRECT_URI=https://negobot-api.duckdns.org/api/platform/client/channels/instagram/callback`
- `META_INSTAGRAM_SCOPES=instagram_business_basic,instagram_business_content_publish,instagram_business_manage_messages,instagram_business_manage_comments`
- `META_REDIRECT_URI=https://negobot-api.duckdns.org/api/platform/client/channels/facebook/callback`
- `META_SCOPES=public_profile,pages_show_list,pages_read_engagement,pages_manage_posts`

Não registar aqui, no Git ou no frontend quaisquer Client secrets, tokens ou API keys. As credenciais privadas devem ser introduzidas directamente no formulário do Backend no Boomploy.

## TikTok Developer Portal

A conta de desenvolvimento do utilizador está autenticada. A aplicação `negobot moz` foi localizada em `https://developers.tiktok.com/app/7670982061959858193/pending`.

Estado visível: `Draft`, Client key/secret mascarados, Web disponível, Terms of Service URL vazio, Privacy Policy URL vazio, descrição vazia, nenhum produto seleccionado e nenhum scope configurado. A aplicação ainda requer configuração antes de poder ser usada com clientes externos.

Não copiar nem registar os valores mascarados de Client key ou Client secret. Eles devem ser revelados/copied pelo utilizador directamente para os campos secretos do Backend no Boomploy.

## Valores públicos guardados no Backend

No serviço `NEGOBOT Backend`, foram adicionados e guardados através do formulário do Boomploy os valores públicos de redirect URI e scopes para TikTok, Instagram e Facebook. Nenhuma Client key, Client secret, access token ou outra credencial privada foi adicionada nesta etapa.

O Backend ainda requer as seguintes credenciais privadas, que devem ser inseridas directamente pelo utilizador nos campos password do mesmo formulário: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `META_INSTAGRAM_CLIENT_ID`, `META_INSTAGRAM_CLIENT_SECRET`, `META_CLIENT_ID` e `META_CLIENT_SECRET`.

## Validação inicial TikTok

Os campos Terms of Service e Privacy Policy foram preenchidos com `/terms` e `/privacy`, mas o TikTok indicou `This URL is not verified` porque as novas páginas ainda não foram publicadas no site público. A aplicação continua em Draft, sem categoria seleccionada, sem produtos e sem scopes. O próximo passo é publicar o commit das páginas legais, validar os dois URLs HTTP 200 e depois usar `Verify URL properties` no portal TikTok.
