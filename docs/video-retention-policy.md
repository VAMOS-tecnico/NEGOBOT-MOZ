# Política de retenção temporária de vídeos

## Objectivo

Os vídeos renderizados são artefactos temporários. O cliente deve descarregar o ficheiro para o seu dispositivo antes de o publicar nas suas redes sociais. O NEGOBOT MOZ conserva no servidor apenas o estado do job e os metadados mínimos necessários ao histórico, não uma cópia permanente do vídeo.

## Ciclo de vida

| Estado | Ficheiro no servidor | Acção disponível |
|---|---:|---|
| `queued` / `processing` | Ainda não disponível ou em produção | Acompanhar o progresso |
| `completed` | Disponível no volume privado do CPX32 | **Baixar vídeo** ou **Apagar do servidor** |
| `deleted` | Removido | Publicar a cópia já descarregada pelo cliente |
| `failed` | Não deve conservar output utilizável | Consultar o erro e iniciar novo job |

O download é feito através do Backend autenticado, que valida a sessão e o `tenant_id` antes de pedir o ficheiro ao Video Service. O Video Service valida novamente o tenant, lê o ficheiro a partir do volume privado partilhado com o Video Worker e transmite-o em streaming. O ficheiro só é apagado quando a transmissão chega ao fim sem interrupção; se o cliente cancelar ou a rede falhar, a cópia permanece disponível para uma nova tentativa.

Depois de o download completo terminar, o job passa para `deleted`. O cliente pode então publicar a cópia local nas suas redes sociais. O endpoint de eliminação manual existe para o caso de o cliente publicar por outro fluxo ou preferir apagar sem descarregar.

## Retenção de segurança

Um processo periódico do Video Worker remove outputs concluídos que permaneçam no servidor durante mais de **sete dias**. Esta regra evita acumulação se o cliente abandonar a página. Jobs em `queued` ou `processing` não são removidos pela retenção, e a limpeza nunca segue um caminho de ficheiro fora de `VIDEO_OUTPUT_DIR`.

## Isolamento e volumes

O volume persistente `negobot_video_data_cpx32` é preservado. O `negobot-video-service` e o `negobot-video-worker` montam o mesmo volume em `/var/lib/negobot/videos`; o serviço não fica público na Internet e continua acessível apenas pelo endereço privado `10.0.0.3:8080`. Nenhum caminho absoluto do servidor é devolvido ao frontend.
