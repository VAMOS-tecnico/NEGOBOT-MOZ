Preview React no VPS — 2026-08-16

URL de preview: https://app-negobotmoz.duckdns.org/plataforma-react/

A rota raiz devolveu HTTP 200 e o HTML contém NEGOBOT-MOZ. A rota interna `/plataforma-react/login` inicialmente devolveu 404; o servidor Flask foi corrigido para fallback SPA em caminhos sem extensão e, depois da reconstrução, a mesma rota devolveu HTTP 200 e carregou o bundle React.

O domínio público `https://negobotmoz.duckdns.org/plataforma-react/` devolve 302 para o site público, mantendo o preview restrito ao subdomínio administrativo.

A página React carregou o texto de login e mostrou brevemente o estado `A carregar a plataforma...` enquanto consultava `/api/platform/auth/me`. O backend protegido permanece responsável pela sessão; o frontend antigo `/plataforma` não foi substituído.

Estado dos serviços após a publicação: negobot-site running/restart 0, negobot-backend running/restart 0, boomploy-caddy running/restart 0; health do site HTTP 200.
