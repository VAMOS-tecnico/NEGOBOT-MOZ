# NEGOBOT MOZ — Relatório Final do Cutover para CPX32

**Autor:** Manus AI  
**Data:** 21 de Agosto de 2026  
**Estado:** **concluído e validado**, com sobreposição, backups e rollback preservado.

## 1. Resultado executivo

A arquitectura distribuída do NEGOBOT MOZ foi activada com sucesso. A nova CPX32 está ligada à VPS de produção por uma rede privada Hetzner, executa os nove workers destinados ao segundo host e é gerida pelo painel Boomploy. A VPS1 mantém os componentes de estado e controlo: Backend, Site, PostgreSQL, Redis, Evolution API, n8n, Caddy, Boomploy, Channel Publication Worker e AutoPay Sync.

O cutover foi feito sem apagar contentores antigos ou volumes persistentes. Os workers antigos da VPS1 foram parados apenas depois de os equivalentes CPX32 estarem activos, ligados ao Redis e a publicar heartbeats. O Backend foi actualizado para utilizar o Video Service pelo endereço privado da CPX32.

> **Conclusão:** a operação diária dos workers CPX32 já pode ser feita a partir do Boomploy, sem SSH manual.

## 2. Arquitectura operacional

| Host | IP público | IP privado | Função após o cutover |
|---|---:|---:|---|
| `ubuntu-4gb-hel1-3` — VPS1 | `62.238.52.209` | `10.0.0.2` | Backend, Site, PostgreSQL, Redis, Evolution API, n8n, Boomploy, Caddy, Channel Publication Worker e AutoPay Sync |
| `ubuntu-8gb-hel1-1` — CPX32 | `89.167.12.24` | `10.0.0.3` | Incoming, Campaign, AI, Image, Audio, Social Poster, Mailer, Video Service e Video Worker |

A rede privada `negobot-private-eu-central`, ID Hetzner `12567529`, usa a sub-rede `10.0.0.0/16`. A ligação foi testada nos dois sentidos com 0% de perda. Este desenho segue o propósito das redes privadas Hetzner: permitir comunicação directa entre servidores sem depender do tráfego público [1].

O Redis está publicado no host da VPS1 apenas em `10.0.0.2:6379`, e os workers CPX32 usam a base Redis 1 através de `redis://10.0.0.2:6379/1`. O Video Service está publicado apenas em `10.0.0.3:8080`, com firewall permitindo acesso a partir de `10.0.0.2`. Não foram publicados Redis, PostgreSQL ou os workers em interfaces públicas.

## 3. Workers transferidos

| Serviço | Host final | Estado validado | Observação |
|---|---|---|---|
| `negobot-incoming-worker` | CPX32 | `running` | Consome as filas WhatsApp e omnichannel |
| `negobot-campaign-worker` | CPX32 | `running` | Processa campanhas e agendamentos |
| `negobot-ai-worker` | CPX32 | `healthy` | Heartbeat activo no Redis |
| `negobot-image-worker` | CPX32 | `healthy` | Heartbeat activo no Redis |
| `negobot-audio-worker` | CPX32 | `healthy` | Heartbeat activo no Redis |
| `negobot-social-poster` | CPX32 | `healthy` | Heartbeat activo no Redis |
| `negobot-mailer` | CPX32 | `healthy` | Heartbeat activo no Redis |
| `negobot-video-service` | CPX32 | `healthy` | HTTP 200 e Redis `online` |
| `negobot-video-worker` | CPX32 | `healthy` | Heartbeat activo no Redis |

Os nove serviços usam `restart: unless-stopped`, política adequada para manter containers activos após falhas recuperáveis e reinícios do host [2] [3]. A Compose CPX32 aplica rotação de logs de `10m` por ficheiro e três ficheiros por container, em linha com a política já adoptada no projecto.

## 4. Segurança e gestão no Boomploy

Foi criado o utilizador de serviço `boomploy-agent` na CPX32. A conta não utiliza palavra-passe e recebe apenas o acesso necessário ao Docker para que o Boomploy possa operar os containers. A chave ED25519 dedicada está guardada na VPS1 sob `/var/lib/boomploy/remote/cpx32/`; a comunicação do Boomploy para a CPX32 usa o IP privado e não a interface pública.

O Boomploy foi actualizado para reconhecer os serviços com sufixo `-cpx32`. Cada cartão permite consultar o estado, ver logs, actualizar o ambiente isolado, iniciar, parar, reiniciar e fazer redeploy. A gestão remota foi validada pela API e visualmente no painel em [boomploy.duckdns.org](https://boomploy.duckdns.org/).

O painel continua protegido pelo token de administrador. Nenhum token de aplicação, chave de fornecedor, senha SMTP, credencial Firebase ou chave privada foi incluído no repositório ou neste relatório.

## 5. Cutover e preservação de rollback

Antes da remoção lógica de qualquer serviço, todos os nove containers foram executados em paralelo na CPX32. Durante a sobreposição, os heartbeats dos workers foram confirmados no Redis DB 1 e os equivalentes antigos da VPS1 continuaram disponíveis como margem de segurança.

O Backend recebeu `VIDEO_SERVICE_URL=http://10.0.0.3:8080`, foi reconstruído e passou os endpoints públicos `/healthz` e `/readyz`. Só depois disso os containers antigos foram parados. Eles permanecem no host da VPS1 com `restart=no`, não foram removidos e podem ser reactivados durante um rollback.

| Item preservado | Resultado |
|---|---|
| Volume Redis `infra_redis_data` | Preservado; `redis-cli ping` devolveu `PONG` |
| Volumes de áudio e vídeo da VPS1 | Preservados; não foram apagados |
| Backups do Compose Redis | Guardados em `/opt/infra/backups/` |
| Backup do `.env` do Backend | Guardado antes da alteração do URL privado |
| Backups do Boomploy | Guardados em `/opt/boomploy/` antes de cada actualização |
| Contentores antigos | Parados, não removidos, com `restart=no` |

Para fazer rollback, deve-se restaurar o `.env` do Backend a partir do backup timestamped, redeployar apenas o Backend, iniciar os workers antigos pela Compose original e parar os cartões CPX32 no Boomploy. **Não executar `docker compose down -v` e não remover volumes.**

## 6. Validações finais

| Verificação | Resultado observado |
|---|---|
| Autenticação do agente pela rede privada | Funcionou com `boomploy-agent@10.0.0.3` |
| Docker remoto CPX32 | Versão 29.1.3; nove containers activos |
| Redis a partir da CPX32 | `ping=True`; TTL dos heartbeats activo |
| Video Service | `{"service":"negobot-video","status":"online","redis":"online"}`; HTTP 200 |
| Backend | `/healthz` HTTP 200; `/readyz` HTTP 200; Firebase e Redis online |
| Site público | HTTP 200 |
| Containers transferidos na VPS1 | 9/9 parados com `restart=no` |
| Cartões CPX32 no Boomploy | 9/9 presentes e apresentados como `running` |
| CPX32 — memória | 7,6 GiB total; aproximadamente 1,0 GiB usado; 6,6 GiB disponível |
| CPX32 — disco | 150 GiB; aproximadamente 7,7 GiB usados; 6% de utilização |

A instância `negobot-video` antiga, separada do par principal Video Service/Video Worker, não foi alterada neste cutover. Deve ser auditada e eventualmente removida numa tarefa independente, depois de confirmar que nenhum fluxo ainda depende dela.

## 7. Artefactos versionados

| Artefacto | Referência |
|---|---|
| Compose isolado CPX32 | [`3afe3c8`](https://github.com/VAMOS-tecnico/boomploy-infra-recovered/commit/3afe3c8) |
| Gestão remota Boomploy | [`9a29084`](https://github.com/VAMOS-tecnico/boomploy-infra-recovered/commit/9a29084) |
| Conta de agente limitado | [`15e0fae`](https://github.com/VAMOS-tecnico/boomploy-infra-recovered/commit/15e0fae) |
| Correcção de estado remoto | [`1c47650`](https://github.com/VAMOS-tecnico/boomploy-infra-recovered/commit/1c47650) |
| Relatório de criação e rede Hetzner | `docs/hetzner-cpx32-console-check-2026-08-21.md` |
| Matriz de integração do painel | `docs/client-panel-integration-audit-2026-08-21.md` |

O custo confirmado no formulário Hetzner para a CPX32 em Helsinki foi **$42,59/mês antes de IVA**, incluindo IPv4. Este valor não inclui eventuais alterações futuras de tráfego, volumes ou serviços adicionais.

## 8. Referências

[1]: https://docs.hetzner.com/networking/networks/overview/ "Hetzner — Networks overview"
[2]: https://docs.docker.com/engine/containers/start-containers-automatically/ "Docker — Start containers automatically"
[3]: https://docs.docker.com/reference/compose-file/services/ "Docker Compose — Services reference"
