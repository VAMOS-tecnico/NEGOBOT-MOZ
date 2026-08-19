# Pesquisa de auto-autorização de canais — 2026-08

## TikTok

Fontes oficiais consultadas:

- TikTok Developer Solutions: https://developers.tiktok.com/
- Login Kit for Web: https://developers.tiktok.com/doc/login-kit-web/
- Manage User Access Tokens: https://developers.tiktok.com/doc/login-kit-manage-user-access-tokens/
- OAuth user access token management: https://developers.tiktok.com/doc/oauth-user-access-token-management/
- Content Posting API overview: https://developers.tiktok.com/products/content-posting-api/
- Content Posting API getting started: https://developers.tiktok.com/doc/content-posting-api-get-started
- Register an app: https://developers.tiktok.com/doc/getting-started-create-an-app

Conclusões a considerar:

1. A auto-autorização deve usar o Login Kit para Web e OAuth, com callback HTTPS registado na aplicação TikTok.
2. O backend deve trocar o código de autorização por tokens e gerir o ciclo de vida dos user access tokens no servidor; tokens e client secret nunca devem ser enviados para o frontend.
3. A publicação de conteúdo depende do produto Content Posting API, dos scopes aprovados, das regras do TikTok e da revisão da aplicação. A UI deve mostrar `pending_review` até existir autorização real.
4. A aplicação deve manter `state`/anti-CSRF e validar exactamente o redirect URI configurado.

## Decisão preliminar

A plataforma deve oferecer no painel um botão `Connect TikTok`. O cliente autoriza a sua própria conta no TikTok, regressa ao callback da NEGOBOT-MOZ e o backend persiste a ligação cifrada e associada ao `tenant_id`. O perfil social existente continuará a aceitar URL/nome de utilizador, mas isso será separado de uma ligação OAuth activa.

## Meta — Instagram e Facebook

Fontes oficiais consultadas:

- Instagram Platform overview: https://developers.facebook.com/documentation/instagram-platform/overview
- Instagram API with Facebook Login: https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login
- Instagram API with Instagram Login: https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login
- Facebook Login for Business: https://developers.facebook.com/documentation/facebook-login/facebook-login-for-business
- Instagram webhooks: https://developers.facebook.com/documentation/instagram-platform/webhooks
- Strict URI matching: https://developers.facebook.com/blog/post/2017/12/18/strict-uri-matching/

Conclusões a considerar:

1. Instagram deve ser ligado por OAuth oficial da Meta e, conforme o fluxo escolhido, exige conta profissional Business ou Creator e permissões adequadas.
2. Facebook Login for Business é o fluxo apropriado para onboarding de contas empresariais e gestão das autorizações do cliente.
3. Webhooks Meta devem ter endpoint HTTPS, verificação de challenge e validação da assinatura; o callback deve normalizar tudo para o `tenant_id` correcto.
4. Redirect URIs precisam de correspondência exacta. O cliente não deve fornecer passwords; autoriza a app no domínio da Meta.
5. Instagram/Facebook só podem aparecer como `connected` depois de OAuth concluído, permissões confirmadas, webhook validado e estado persistido. Caso contrário devem ficar `pending_authorization` ou `pending_review`.

## Telegram, X e LinkedIn

Fontes consultadas:

- Telegram Bot API: https://core.telegram.org/bots/api
- X OAuth 2.0 overview: https://docs.x.com/fundamentals/authentication/oauth-2-0/overview
- X user access token flow: https://docs.x.com/fundamentals/authentication/oauth-2-0/user-access-token
- LinkedIn authentication overview: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authentication
- LinkedIn authorization code flow: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow

Conclusões a considerar:

1. Telegram não oferece o mesmo OAuth de conta social para este caso. O cliente fornece o token do próprio bot criado no BotFather através de um formulário seguro; o backend valida o token com `getMe`, regista um webhook HTTPS com secret próprio e associa o bot ao tenant. O token nunca aparece depois no frontend.
2. X suporta OAuth 2.0 Authorization Code with PKCE. O backend deve guardar tokens server-side, limitar scopes e tratar a autorização como pendente até o callback e a chamada de identidade serem validados.
3. LinkedIn usa OAuth 2.0 e authorization code flow; publicar conteúdo e gerir páginas exige produtos/scopes aprovados, pelo que a ligação básica e a publicação devem ter estados separados.
4. A matriz comum deve distinguir `pending_authorization`, `connected`, `pending_review`, `not_configured`, `error` e `disabled`, sem anunciar capacidades que ainda dependem da aprovação do fornecedor.

## Validação textual das páginas oficiais

A leitura das páginas confirmou os seguintes detalhes operacionais:

- Instagram API with Instagram Login permite contas profissionais Business e Creator, incluindo publicação de conteúdo, insights, moderação de comentários, menções e mensagens; os scopes actuais incluem `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_messages` e `instagram_business_manage_comments`. Fonte: https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login
- X documenta OAuth 2.0 Authorization Code Flow with PKCE, parâmetros `state` e `code_challenge`, troca do código por access token e refresh token com `offline.access`, além de revogação. Fonte: https://docs.x.com/fundamentals/authentication/oauth-2-0/user-access-token
- Telegram confirma que cada bot tem token único, as chamadas usam HTTPS, `getMe` pode validar o token e `setWebhook` aceita URL HTTPS, `allowed_updates` e `secret_token`, enviado no header `X-Telegram-Bot-Api-Secret-Token`. Fonte: https://core.telegram.org/bots/api
- A documentação do TikTok expõe Login Kit Web, gestão de user access tokens, Display API, Content Posting API, webhooks e App Review; o fluxo deverá ser implementado com revisão de capacidades, sem tratar a existência da aplicação como autorização de produção. Fonte: https://developers.tiktok.com/doc/login-kit-web/
