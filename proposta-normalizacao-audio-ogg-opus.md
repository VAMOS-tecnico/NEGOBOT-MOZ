# Proposta: validação e normalização de áudio OGG/Opus antes do Whisper

## Conclusão

A melhor opção para o NEGOBOT-MOZ é usar **FFmpeg + ffprobe** como uma camada de validação e conversão no backend Python. O FFmpeg suporta contentores OGG e o codec Opus e pode converter o áudio para WAV PCM mono a 16 kHz, um formato simples e previsível para o Whisper.

Esta camada resolve dois casos diferentes:

1. Um OGG/Opus válido, mas com parâmetros incompatíveis: o FFmpeg valida e converte.
2. Bytes inválidos, incompletos ou `.enc` devolvidos pela Evolution: o `ffprobe` falha rapidamente e o bot usa o fallback, sem enviar lixo ao Groq.

A camada **não consegue desencriptar** um ficheiro `.enc` nem reconstruir bytes que a Evolution não entregou. Nesse caso, a correção definitiva continua a ser corrigir a recuperação na Evolution API.

## Implementação recomendada em Python

Adicionar `ffmpeg` e `ffprobe` à imagem Docker do backend e criar uma função semelhante a esta:

```python
import json
import os
import subprocess
import tempfile
from pathlib import Path

MAX_AUDIO_BYTES = 20 * 1024 * 1024


def normalizar_audio_para_whisper(media_bytes: bytes) -> bytes:
    if not media_bytes or len(media_bytes) > MAX_AUDIO_BYTES:
        return b""

    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        logger.error("FFmpeg/ffprobe não estão instalados no backend.")
        return b""

    with tempfile.TemporaryDirectory(prefix="negobot-audio-") as temp_dir:
        source = Path(temp_dir) / "input.bin"
        output = Path(temp_dir) / "output.wav"
        source.write_bytes(media_bytes)

        probe = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,codec_type,sample_rate,channels:format=format_name",
                "-of", "json", str(source),
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if probe.returncode != 0:
            logger.warning("Áudio rejeitado pelo ffprobe: %s", probe.stderr[:300])
            return b""

        try:
            metadata = json.loads(probe.stdout or "{}")
            streams = metadata.get("streams") or []
            if not streams or streams[0].get("codec_type") != "audio":
                return b""
        except (ValueError, TypeError):
            return b""

        converted = subprocess.run(
            [
                ffmpeg, "-nostdin", "-v", "error", "-xerror",
                "-i", str(source),
                "-map", "0:a:0",
                "-ac", "1",
                "-ar", "16000",
                "-c:a", "pcm_s16le",
                "-f", "wav",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if converted.returncode != 0 or not output.exists():
            logger.warning("Conversão de áudio falhou: %s", converted.stderr[:300])
            return b""

        normalized = output.read_bytes()
        if not normalized or len(normalized) > MAX_AUDIO_BYTES:
            return b""
        return normalized
```

No exemplo, é necessário adicionar `import shutil` e substituir a chamada direta ao Groq por:

```python
normalized_audio = normalizar_audio_para_whisper(media_bytes)
if not normalized_audio:
    logger.warning("Áudio inválido ou não recuperável; não enviado ao Groq.")
    return ""

with tempfile.NamedTemporaryFile(prefix="negobot-audio-", suffix=".wav") as temporary:
    temporary.write(normalized_audio)
    temporary.flush()
    with open(temporary.name, "rb") as audio_file:
        transcript = transcrever_audio_groq(audio_file)
```

Também convém alterar o multipart no `groq_service.py` para enviar `audio/wav` quando o ficheiro normalizado for WAV:

```python
files = {"file": (filename or "audio.wav", audio_file, "audio/wav")}
```

## Dependências Docker

No `Dockerfile` baseado em `python:3.11-slim`, instalar o binário do sistema:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

Não é necessário instalar uma biblioteca Python para a solução principal. Isto reduz dependências e permite usar exatamente o mesmo comportamento em Python, Node.js e testes manuais.

## Alternativas de biblioteca

| Opção | Uso | Avaliação |
|---|---|---|
| `ffmpeg` + `ffprobe` | Validar contentor/codec e converter | **Recomendado**; robusto e já disponível no ecossistema Docker |
| PyAV | Aceder diretamente a contentores, streams, packets e frames FFmpeg | Boa alternativa Python, mas aumenta a complexidade da imagem |
| `pydub` | Conversão simples através de FFmpeg | Conveniente, mas menos adequado para diagnóstico detalhado |
| `opuslib` | Codificar/descodificar frames Opus | Não substitui um parser de contentor OGG; não é suficiente sozinho |
| Node.js `child_process.spawn` + FFmpeg | Usar o mesmo FFmpeg num serviço Node | Boa opção se a normalização for movida para Node |
| `music-metadata` | Ler metadados no Node.js | Útil para inspeção leve, mas não substitui FFmpeg para transcodificação |
| `fluent-ffmpeg` | API de alto nível para FFmpeg | Pode funcionar, mas prefiro `spawn` direto ou `execa` para controlar timeouts e erros |

## Critérios de segurança

O processo deve limitar o tamanho máximo, usar `-nostdin`, impor timeout, não aceitar caminhos vindos do utilizador e apagar os temporários sempre. O áudio não deve ser enviado ao Groq se o `ffprobe` não identificar pelo menos uma stream de áudio.

O log deve registar apenas tamanho, codec, sample rate, canais e resultado (`validado`, `convertido` ou `rejeitado`). Nunca deve registar Base64, conteúdo binário, chaves ou payload completo.

## Testes necessários

A suíte deve incluir um OGG/Opus válido, um WAV válido, um MP3 válido, bytes truncados, um falso OGG que começa por `OggS` mas não é um contentor válido e um payload `.enc`. O comportamento esperado para os dois últimos é rejeitar antes do Groq e ativar o fallback do bot.

## Recomendação final

Implementar FFmpeg/ffprobe como **camada de validação e normalização**, mas não tratá-la como substituto da correção da Evolution. Se a Evolution entregar o ficheiro válido, esta camada pode aumentar a compatibilidade e tornar a transcrição mais previsível. Se entregar bytes encriptados ou inválidos, apenas uma correção na origem ou outro método oficial de download poderá resolver.

## Referências

- [Groq Speech to Text](https://console.groq.com/docs/speech-to-text)
- [FFmpeg Documentation](https://ffmpeg.org/ffmpeg.html)
- [FFmpeg Codecs Documentation](https://ffmpeg.org/ffmpeg-codecs.html)
- [PyAV Documentation](https://pyav.org/docs/develop/)
- [fluent-ffmpeg](https://github.com/fluent-ffmpeg/node-fluent-ffmpeg)
