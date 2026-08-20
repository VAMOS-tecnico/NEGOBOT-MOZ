# Estado pré-deploy UX — 2026-08-20

O painel Boomploy foi autenticado com a sessão existente. Os cartões `NEGOBOT Backend` e `NEGOBOT Site` aparecem como `running`. Os serviços de infraestrutura e workers também aparecem activos, incluindo Evolution API, PostgreSQL, Redis, Incoming Worker, Campaign Worker, AI, Image, Audio, Social, Mailer, Video Service e Video Worker.

O redeploy desta alteração deve limitar-se a `NEGOBOT Site` e `NEGOBOT Backend`. Evolution API, PostgreSQL, Redis e workers não foram seleccionados para reinício.

O cartão legado `Negobot Video` aparece como `missing` no catálogo Boomploy; não faz parte deste redeploy e não será alterado.

Não foram copiados valores de segredos para este ficheiro.

Commit a publicar: `7019ed2` — `feat: improve client panel onboarding and self-service extras`.

Validações prévias: suite backend com 125 testes OK; `pnpm run check` OK; `pnpm run build` OK; `git diff --check` OK.

O cartão do Backend foi aberto para observação. O serviço continua `running` e os logs mostram Gunicorn a escutar na porta interna e workers activos. A lista visível de variáveis contém as variantes dos três planos, mas não mostra variáveis `LEMONSQUEEZY_VARIANT_ADDON_*`; por isso não alterei o `.env`. Os extras internacionais permanecerão correctamente bloqueados como configuração pendente até os IDs de variantes serem fornecidos no Boomploy.

O cartão `NEGOBOT Site` foi aberto sem alterar variáveis. O estado observado é `running`, com contentor `negobot-site`, e a acção `Forçar re-deploy` está disponível. O Site será o primeiro serviço publicado.

O Site reportou `redeploy concluído` e os logs mostraram novo arranque do Gunicorn em `2026-08-20T07:33:32Z`. O Backend foi accionado pelo botão exacto `Forçar re-deploy`; após a operação o cartão continua `running`. A confirmação final será feita pelos endpoints HTTPS e pela verificação de versão/rotas.

Validação externa pós-deploy do Backend:

- `https://negobot-api.duckdns.org/healthz` respondeu `{"status":"ok"}`.
- `https://negobot-api.duckdns.org/readyz` respondeu `{"checks":{"firebase":"online","redis":"online"},"status":"ready"}`.

Não foi executado nenhum pagamento, webhook válido ou criação de tenant de teste.

Validação do site público: `https://negobotmoz.duckdns.org/` carregou correctamente após o redeploy, com PT/EN, CTA para `https://app-negobotmoz.duckdns.org/plataforma/register`, trial de 2 dias e planos em USD. O hostname `https://negobot.duckdns.org/` exibido no cartão Boomploy não resolveu nesta rede (`ERR_NAME_NOT_RESOLVED`); o domínio canónico `negobotmoz.duckdns.org` está funcional. Não alterei DNS.

Validação da plataforma privada: `https://app-negobotmoz.duckdns.org/plataforma` redireccionou para `/plataforma/login` e carregou o login em inglês por defeito, com selector PT/EN, recuperação de palavra-passe e início do trial. Não foram introduzidas credenciais, criadas contas ou executados pagamentos.
