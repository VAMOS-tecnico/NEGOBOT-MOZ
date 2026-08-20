# Relatório de redeploy UX — NEGOBOT-MOZ

**Data:** 20 de Agosto de 2026  
**Commit:** [`7019ed2`](https://github.com/VAMOS-tecnico/NEGOBOT-MOZ/commit/7019ed2) — `feat: improve client panel onboarding and self-service extras`

## Resultado executivo

O redeploy faseado foi concluído. O cartão **NEGOBOT Site** foi redeployado primeiro e voltou a `running` com novo arranque Gunicorn. Em seguida, o cartão **NEGOBOT Backend** foi redeployado e permaneceu `running`. Não foram reiniciados Evolution API, PostgreSQL, Redis, Incoming Worker, Campaign Worker, AI Worker, Image Worker, Audio Worker, Social Poster, Mailer Worker, Video Service ou Video Worker.

Nenhum volume persistente foi apagado, recriado ou desmontado. Não foram executados pagamentos reais, webhooks válidos, criação de tenants de teste ou alterações de credenciais.

## Validação pós-deploy

| Área | Resultado |
|---|---|
| Backend `/healthz` | `{"status":"ok"}` |
| Backend `/readyz` | `status=ready`; Firebase `online`; Redis `online` |
| Site público canónico | [`https://negobotmoz.duckdns.org/`](https://negobotmoz.duckdns.org/) carregou correctamente |
| Plataforma privada | [`https://app-negobotmoz.duckdns.org/plataforma`](https://app-negobotmoz.duckdns.org/plataforma) redireccionou para login |
| Idioma inicial | Inglês, com selector PT/EN visível |
| Trial | CTA de 2 dias Premium visível no site e no login |
| Testes locais | 125 testes backend; `pnpm run check`; `pnpm run build`; `git diff --check` — todos OK |

## Serviços e rollback

O rollback continua disponível pelo commit anterior `92242a8`, caso seja necessário. O redeploy foi limitado aos dois cartões que continham código alterado. Os estados globais observados no Boomploy permaneceram `running` para os serviços existentes; o cartão legado `Negobot Video` continua `missing` no catálogo e não foi alterado.

## Configuração pendente

O Backend possui as variantes Lemon Squeezy dos três planos, mas não possui ainda variantes dedicadas aos extras. Para activar o checkout internacional dos extras, adicionar no cartão **NEGOBOT Backend** as seguintes variáveis com os IDs reais das variantes Lemon Squeezy:

```text
LEMONSQUEEZY_VARIANT_ADDON_CANAIS_PLUS=<variant-id>
LEMONSQUEEZY_VARIANT_ADDON_CAMPANHAS_AVANCADAS=<variant-id>
LEMONSQUEEZY_VARIANT_ADDON_UTILIZADOR_ADICIONAL=<variant-id>
```

Enquanto esses IDs não forem configurados, a interface mostra **Configuração necessária** e não cria um checkout fictício. Para contas moçambicanas, o fluxo M-Pesa AutoPay já está ligado ao endpoint de validação de extras e só activa o extra depois de confirmar transacção, remetente, valor e uso único.

## Observação de hostname

O cartão Boomploy mostra `negobot.duckdns.org`, mas esse hostname devolveu `ERR_NAME_NOT_RESOLVED` durante a validação nesta rede. O domínio canónico funcional é `negobotmoz.duckdns.org`. Não alterei DNS durante o redeploy; recomenda-se corrigir o URL exibido no cartão Boomploy numa operação separada.
