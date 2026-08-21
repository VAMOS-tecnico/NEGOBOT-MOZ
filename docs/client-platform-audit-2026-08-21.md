# Auditoria inicial da plataforma do cliente — 21 de Agosto de 2026

## Observações visuais

A rota pública `https://app-negobotmoz.duckdns.org/plataforma` abre inicialmente em inglês, com selector PT/EN, login, recuperação de palavra-passe e ligação para iniciar o trial de 2 dias. O texto inicial do login está traduzido correctamente.

Ao abrir `/plataforma/register`, a aplicação apresentou temporariamente `Loading platform...`; é necessário aguardar ou validar o carregamento em nova tentativa.

## Observações do código

`platform-react/src/App.tsx` já implementa selector de idioma, banner de trial pendente, navegação por cliente/admin, login, recuperação de palavra-passe, registo com região/plano e dashboard de ligações dos serviços.

`platform-react/src/pages/OnboardingPage.tsx` já implementa perfil, região de cobrança, plano, escolha do canal de trial e regra de dois dias Premium partilhados. Contudo, todo o JSX do onboarding está em português e não usa o selector PT/EN.

`platform-react/src/pages/ClientPages.tsx` já implementa campanhas, grupos próprios, anti-spam, planos, checkout Lemon Squeezy, AutoPay M-Pesa, QR WhatsApp, assistente, equipa, métricas, suporte e vídeos. Ainda há muitos textos hard-coded em português dentro de páginas que já calculam `english`, especialmente em formulários, mensagens de sucesso/erro, placeholders e labels.

`platform-react/src/pages/ChannelsPage.tsx` e `ChannelPublicationsPage.tsx` já têm estados reais de integração e avisos de autorização, mas também mantêm instruções em português quando a interface está em inglês.

## Prioridades preliminares

1. Tornar o onboarding totalmente bilingue e reduzir o número de decisões no primeiro ecrã.
2. Substituir o sistema de tradução DOM por textos de interface controlados por componentes, reduzindo mistura de idiomas e efeitos sobre conteúdo dinâmico.
3. Completar PT/EN em Conversas, Campanhas, Plano, WhatsApp, Canais, Grupos, Perfil, Equipa, Métricas, Suporte e Vídeos.
4. Mostrar no dashboard um percurso claro: completar perfil, ligar WhatsApp/Telegram, testar e escolher plano.
5. Preservar contratos tenant-scoped, trial central, pagamentos, QR e estados honestos dos canais.

## Teste visual da primeira iteração

A pré-visualização local abriu `/plataforma/register` em inglês, com carregamento concluído, PT/EN visível, formulário de acesso reduzido e explicação clara do trial. O layout permanece compacto e legível no viewport de teste. O teste não submeteu formulário nem criou conta real.

O teste visual do selector PT/EN na pré-visualização mostrou o estado PT activo, mas o texto permaneceu em inglês. Como o conteúdo do onboarding foi tornado condicional ao contexto React, isto indica que o estado local do navegador/pré-visualização não foi re-renderizado correctamente durante o clique, e deve ser revalidado antes do deploy. O build TypeScript e Vite permanece aprovado.

O diagnóstico do preview confirmou `localStorage = pt`, mas o texto do registo permaneceu em inglês depois do clique. A causa provável é o mecanismo actual de tradução DOM/estado, não o armazenamento da preferência. A solução deve garantir re-renderização React explícita quando o idioma muda, em vez de depender apenas do MutationObserver.

Após adicionar as entradas de login/registo ao dicionário, a pré-visualização confirmou as duas direcções: com a preferência PT, o registo aparece em português; ao alternar para EN, volta a aparecer em inglês. Nenhum formulário foi submetido.
