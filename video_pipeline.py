"""Pipeline modular de vídeos verticais do NEGOBOT MOZ.

O módulo mantém o processamento determinístico no Video Worker e trata as
integrações externas como opcionais: sem Pexels, Groq, edge-tts ou Whisper,
o job continua a poder produzir um vídeo de fallback em vez de falhar em
cadeia. Nenhuma chave é devolvida ao frontend.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlparse

import requests

logger = logging.getLogger("negobot-video-pipeline")
PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
MAX_ASSET_BYTES = 80 * 1024 * 1024
DEFAULT_PEXELS_PER_PAGE = 3
DEFAULT_PEXELS_TIMEOUT = 20


def _safe_text(value: str) -> str:
    return re.sub(r"[^\w\s,.!?;:'\-À-ÿ]", "", str(value or "")).strip()[:500]


def _run(command: list[str], timeout: int = 90) -> None:
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        text=True,
    )
    return max(0.1, float(result.stdout.strip()))


def _ffmpeg_text(value: str) -> str:
    return _safe_text(value).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")


def _download_url(url: str, target: Path, max_bytes: int = MAX_ASSET_BYTES, headers: dict[str, str] | None = None) -> Path:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Os assets devem usar URLs HTTPS públicas.")
    target.parent.mkdir(parents=True, exist_ok=True)
    request_headers = {"User-Agent": "NEGOBOT-video/1.0", **(headers or {})}
    with requests.get(url, timeout=DEFAULT_PEXELS_TIMEOUT, stream=True, headers=request_headers) as response:
        response.raise_for_status()
        content_length = int(response.headers.get("content-length") or 0)
        if content_length > max_bytes:
            raise ValueError("Asset demasiado grande.")
        written = 0
        with target.open("wb") as handle:
            for chunk in response.iter_content(1024 * 256):
                if not chunk:
                    continue
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError("Asset demasiado grande.")
                handle.write(chunk)
    if not target.exists() or target.stat().st_size == 0:
        raise ValueError("O asset descarregado está vazio.")
    return target


def _download_asset(url: str, target: Path, headers: dict[str, str] | None = None) -> Path | None:
    try:
        return _download_url(url, target, headers=headers)
    except (OSError, requests.RequestException, ValueError) as exc:
        logger.warning("Asset externo ignorado: %s", exc)
        return None


def _internal_asset_headers(job: dict[str, Any]) -> dict[str, str]:
    token = str(os.getenv("VIDEO_SERVICE_TOKEN") or "").strip()
    tenant_id = str(job.get("tenant_id") or "").strip()
    return {"X-Video-Service-Token": token, "X-Video-Tenant-Id": tenant_id} if token and tenant_id else {}


def _pexels_search(query: str, page: int = 1) -> list[dict[str, Any]]:
    api_key = str(os.getenv("PEXELS_API_KEY") or "").strip()
    if not api_key:
        return []
    per_page = max(1, min(80, int(os.getenv("PEXELS_PER_PAGE", str(DEFAULT_PEXELS_PER_PAGE)))))
    timeout = max(5, int(os.getenv("PEXELS_TIMEOUT_SECONDS", str(DEFAULT_PEXELS_TIMEOUT))))
    response = requests.get(
        PEXELS_SEARCH_URL,
        headers={"Authorization": api_key, "User-Agent": "NEGOBOT-video/1.0"},
        params={"query": str(query or "video"), "orientation": "portrait", "per_page": per_page, "page": page},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return [item for item in data.get("videos", []) if isinstance(item, dict)]


def _best_pexels_file(video: dict[str, Any]) -> tuple[str, float] | None:
    files = video.get("video_files") or []
    candidates = []
    for item in files:
        if not isinstance(item, dict) or not item.get("link"):
            continue
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        if width <= 0 or height <= 0 or height < width:
            continue
        candidates.append((item, width, height))
    if not candidates:
        return None
    # Prefer vertical Full HD or the closest smaller vertical rendition.
    candidates.sort(key=lambda row: (abs(row[2] - 1920) + abs(row[1] - 1080), row[1] * row[2]))
    return str(candidates[0][0]["link"]), float(video.get("duration") or 0)


def _normalise_keywords(words: Iterable[Any]) -> list[str]:
    result = []
    for word in words:
        value = re.sub(r"[^A-Za-z0-9 ]+", " ", str(word or "")).strip()
        if value and value.lower() not in {item.lower() for item in result}:
            result.append(value[:80])
    return result[:8]


def baixar_videos_pexels(palavras_chave: list, duracao_minima: float, pasta_destino: str = "temp_videos") -> list[str]:
    """Descarrega vídeos verticais Pexels até cobrir a duração pretendida.

    A ausência de ``PEXELS_API_KEY`` ou uma falha do fornecedor devolve uma
    lista vazia para activar o fallback local do renderizador.
    """
    root = Path(pasta_destino)
    root.mkdir(parents=True, exist_ok=True)
    required = max(0.1, float(duracao_minima))
    keywords = _normalise_keywords(palavras_chave) or ["business"]
    downloaded: list[str] = []
    covered = 0.0
    seen_ids: set[str] = set()
    for query in keywords:
        if covered >= required:
            break
        try:
            results = _pexels_search(query)
        except (requests.RequestException, ValueError, OSError) as exc:
            logger.warning("Pexels indisponível para query=%s: %s", query, exc)
            continue
        for video in results:
            if covered >= required:
                break
            video_id = str(video.get("id") or "")
            if video_id and video_id in seen_ids:
                continue
            selected = _best_pexels_file(video)
            if not selected:
                continue
            link, duration = selected
            if not duration or duration <= 0:
                continue
            seen_ids.add(video_id)
            target = root / f"pexels-{len(downloaded):03d}.mp4"
            try:
                _download_url(link, target)
            except (OSError, requests.RequestException, ValueError) as exc:
                logger.warning("Vídeo Pexels ignorado id=%s: %s", video_id or "unknown", exc)
                continue
            downloaded.append(str(target))
            covered += duration
    return downloaded


def _parse_json_object(content: str) -> dict[str, Any]:
    """Extrai um objecto JSON mesmo quando o modelo envolve a resposta em markdown."""
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("O Groq não devolveu um objecto JSON válido.") from None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            raise ValueError("O Groq não devolveu um objecto JSON válido.") from None
    if not isinstance(parsed, dict):
        raise ValueError("O roteiro Groq deve ser um objecto JSON.")
    return parsed


def gerar_roteiro(tema: str, idioma: str = "pt") -> dict:
    """Gera roteiro estruturado com contrato JSON validado localmente.

    O modelo qwen configurado no Groq rejeita ``response_format=json_object``
    para alguns pedidos curtos. Por isso o prompt exige JSON estrito e o
    resultado é validado localmente antes de ser aceite pelo pipeline.
    """
    from groq import Groq

    language = "Português" if str(idioma).lower().startswith("pt") else "English"
    api_key = str(os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY não configurada no AI Worker.")
    prompt = (
        f"Crie um roteiro curto e natural sobre: {tema}. Responda exclusivamente em JSON válido. "
        f"O campo narracao deve ser um texto fluido em {language}. "
        "O campo palavras_chave deve ser uma lista de 3 a 5 termos curtos obrigatoriamente em inglês "
        "para procurar vídeos verticais de fundo no Pexels. Não inclua markdown, comentários ou outras chaves."
    )
    client = Groq(api_key=api_key)
    completion = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {"role": "system", "content": "És um roteirista de vídeos curtos. Devolve somente JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=500,
    )
    content = completion.choices[0].message.content or "{}"
    data = _parse_json_object(content)
    narration = str(data.get("narracao") or "").strip()
    keywords = _normalise_keywords(data.get("palavras_chave") or [])
    if not narration or not 3 <= len(keywords) <= 5:
        raise ValueError("O roteiro Groq não respeita o contrato narracao/palavras_chave.")
    return {"narracao": narration, "palavras_chave": keywords}


async def gerar_audio(texto: str, idioma: str = "pt", output_path: str = "audio.mp3") -> str:
    """Sintetiza voz de forma assíncrona através do edge-tts."""
    import edge_tts

    voice = "pt-BR-AntonioNeural" if str(idioma).lower().startswith("pt") else "en-US-ChristopherNeural"
    communicator = edge_tts.Communicate(str(texto), voice)
    await communicator.save(output_path)
    if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
        raise RuntimeError("O edge-tts não produziu um ficheiro de áudio válido.")
    return output_path


VOICE_ALIASES = {
    "pt_mz_female": "pt-BR-FranciscaNeural",
    "pt_mz_male": "pt-BR-AntonioNeural",
    "en_us_female": "en-US-AriaNeural",
    "en_us_male": "en-US-ChristopherNeural",
}


class VoiceCloneError(RuntimeError):
    pass


class AvatarProviderError(RuntimeError):
    pass


def _resolved_edge_voice(language: str, voice: str | None) -> str:
    selected = str(voice or "").strip()
    return VOICE_ALIASES.get(selected, selected or ("pt-BR-AntonioNeural" if language.lower().startswith("pt") else "en-US-ChristopherNeural"))


def _elevenlabs_key() -> str:
    return str(os.getenv("ELEVENLABS_API_KEY") or "").strip()


def _clone_voice(sample_path: Path, voice_name: str) -> str:
    api_key = _elevenlabs_key()
    if not api_key:
        raise VoiceCloneError("ELEVENLABS_API_KEY não está configurada para clonagem de voz.")
    base = str(os.getenv("ELEVENLABS_API_BASE") or "https://api.elevenlabs.io/v1").rstrip("/")
    try:
        with sample_path.open("rb") as sample:
            response = requests.post(
                f"{base}/voices/add",
                headers={"xi-api-key": api_key},
                data={"name": voice_name[:80] or "NEGOBOT scene voice", "description": "NEGOBOT temporary scene voice"},
                files={"files": (sample_path.name, sample, "audio/wav" if sample_path.suffix.lower() == ".wav" else "audio/mpeg")},
                timeout=60,
            )
        response.raise_for_status()
        voice_id = str((response.json() or {}).get("voice_id") or "").strip()
    except (OSError, ValueError, requests.RequestException) as exc:
        raise VoiceCloneError(f"Não foi possível criar a voz clonada: {exc}") from exc
    if not voice_id:
        raise VoiceCloneError("A ElevenLabs não devolveu um voice_id para a amostra.")
    return voice_id


def _delete_elevenlabs_voice(voice_id: str) -> None:
    api_key = _elevenlabs_key()
    if not api_key or not voice_id:
        return
    base = str(os.getenv("ELEVENLABS_API_BASE") or "https://api.elevenlabs.io/v1").rstrip("/")
    try:
        response = requests.delete(f"{base}/voices/{voice_id}", headers={"xi-api-key": api_key}, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        logger.warning("Não foi possível remover a voz clonada temporária", exc_info=True)


def _elevenlabs_tts(text: str, output: Path, voice_id: str, language: str) -> bool:
    api_key = _elevenlabs_key()
    if not api_key:
        return False
    base = str(os.getenv("ELEVENLABS_API_BASE") or "https://api.elevenlabs.io/v1").rstrip("/")
    model = str(os.getenv("ELEVENLABS_MODEL") or ("eleven_multilingual_v2" if language.lower().startswith("pt") else "eleven_turbo_v2_5"))
    try:
        response = requests.post(
            f"{base}/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
            json={"text": text, "model_id": model},
            timeout=120,
        )
        response.raise_for_status()
        output.write_bytes(response.content)
        return output.exists() and output.stat().st_size > 0
    except (OSError, requests.RequestException) as exc:
        raise VoiceCloneError(f"A síntese ElevenLabs falhou: {exc}") from exc


def _offline_tts(text: str, output: Path, language: str) -> bool:
    """Gera voz localmente quando o endpoint público edge-tts está indisponível."""
    voice = "pt" if str(language or "pt").lower().startswith("pt") else "en"
    wav = output.with_suffix(".wav")
    try:
        _run(["espeak-ng", "-v", voice, "-s", "150", "-w", str(wav), str(text)], timeout=90)
        _run(["ffmpeg", "-y", "-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "3", str(output)], timeout=90)
        return output.exists() and output.stat().st_size > 0
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        logger.warning("Fallback TTS offline indisponível: %s", exc)
        return False
    finally:
        wav.unlink(missing_ok=True)


async def gerar_audio(texto: str, idioma: str = "pt", output_path: str = "audio.mp3") -> str:
    """Sintetiza voz através do edge-tts, com fallback offline."""
    try:
        import edge_tts

        voice = _resolved_edge_voice(idioma, None)
        communicator = edge_tts.Communicate(str(texto), voice)
        await communicator.save(output_path)
        if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            return output_path
    except Exception as exc:
        logger.warning("edge-tts indisponível; a usar fallback offline: %s", exc)
    if _offline_tts(str(texto), Path(output_path), idioma):
        return output_path
    raise RuntimeError("Não foi possível gerar um ficheiro de áudio válido.")


async def _tts(text: str, output: Path, language: str, voice: str | None, sample_path: Path | None = None) -> bool:
    if sample_path is not None:
        voice_id = _clone_voice(sample_path, f"NEGOBOT-{sample_path.stem[:40]}")
        try:
            return _elevenlabs_tts(text, output, voice_id, language)
        finally:
            _delete_elevenlabs_voice(voice_id)
    try:
        import edge_tts

        selected_voice = _resolved_edge_voice(language, voice)
        communicator = edge_tts.Communicate(text, selected_voice)
        await communicator.save(str(output))
        return output.exists() and output.stat().st_size > 0
    except Exception as exc:
        logger.warning("edge-tts indisponível; a tentar fallback offline: %s", exc)
        return _offline_tts(text, output, language)


def gerar_timestamps(audio_path: str) -> list[dict[str, Any]]:
    """Extrai timestamps palavra a palavra com faster-whisper."""
    from faster_whisper import WhisperModel

    model_name = os.getenv("WHISPER_MODEL", "base")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(audio_path, word_timestamps=True, vad_filter=True)
    words: list[dict[str, Any]] = []
    for segment in segments:
        for word in segment.words or []:
            text = str(word.word or "").strip()
            if text:
                words.append({"word": text, "start": float(word.start), "end": float(word.end)})
    return words


def _ass_time(seconds: float) -> str:
    total = max(0, int(seconds * 100))
    hours, remainder = divmod(total, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _write_ass(timestamps: list[dict[str, Any]], target: Path) -> None:
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "",
        "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,DejaVu Sans,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,1,0,0,0,100,100,0,0,1,4,1,5,50,50,160,1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    group: list[dict[str, Any]] = []
    for item in timestamps:
        group.append(item)
        if len(group) < 4 and item is not timestamps[-1]:
            continue
        text = " ".join(str(word["word"]).replace("{", "(").replace("}", ")") for word in group).upper()
        start = float(group[0]["start"])
        end = max(start + 0.15, float(group[-1]["end"]))
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}")
        group = []
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _burn_subtitles(video: Path, timestamps: list[dict[str, Any]], target: Path) -> None:
    if not timestamps:
        shutil.copyfile(video, target)
        return
    ass = target.with_suffix(".ass")
    _write_ass(timestamps, ass)
    _run(["ffmpeg", "-y", "-i", str(video), "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(target)], timeout=180)


def _fade_filter(duration: float, transition: str = "fade") -> str:
    base = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
    if transition != "fade":
        return base
    fade_duration = min(0.22, max(0.05, duration / 4))
    fade_out_start = max(0.0, duration - fade_duration)
    return f"{base},fade=t=in:st=0:d={fade_duration:.3f},fade=t=out:st={fade_out_start:.3f}:d={fade_duration:.3f}"


def _render_card(text: str, duration: float, output: Path, background: str = "#102c3a", transition: str = "fade") -> None:
    safe = _ffmpeg_text(text)
    drawtext = f"drawtext=text='{safe}':fontcolor=white:fontsize=54:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=12"
    vf = f"{drawtext},{_fade_filter(duration, transition).replace('scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30', 'format=yuv420p')}"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={background}:s=1080x1920:d={duration}", "-vf", vf, "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", str(output)], timeout=120)


def _render_background(source: Path, duration: float, output: Path, transition: str = "fade") -> None:
    filter_graph = _fade_filter(duration, transition)
    _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(source), "-t", str(max(0.1, duration)), "-an", "-vf", filter_graph, "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", str(output)], timeout=180)


def _render_image(source: Path, duration: float, output: Path, transition: str = "fade") -> None:
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(source), "-t", str(max(0.1, duration)), "-an", "-vf", _fade_filter(duration, transition), "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", str(output)], timeout=180)


def _generate_ai_image(text: str, output: Path) -> Path | None:
    prompt = quote(f"vertical cinematic background for {text}, no text, professional marketing, 9:16")
    url = f"https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1920&nologo=true"
    return _download_asset(url, output)


def _heygen_avatar(text: str, avatar_id: str, output: Path) -> Path:
    api_key = str(os.getenv("HEYGEN_API_KEY") or "").strip()
    if not api_key:
        raise AvatarProviderError("HEYGEN_API_KEY não está configurada para o modo Avatar AI.")
    base = str(os.getenv("HEYGEN_API_BASE") or "https://api.heygen.com").rstrip("/")
    create_path = str(os.getenv("HEYGEN_CREATE_PATH") or "/v3/videos")
    status_path = str(os.getenv("HEYGEN_STATUS_PATH") or "/v3/videos/{video_id}")
    payload = {"type": "avatar", "avatar_id": avatar_id, "title": f"NEGOBOT scene {avatar_id[:20]}", "resolution": "1080p", "aspect_ratio": "9:16", "output_format": "mp4", "script": text}
    try:
        response = requests.post(f"{base}{create_path}", headers={"x-api-key": api_key, "Content-Type": "application/json", "Idempotency-Key": f"negobot-{uuid.uuid4()}"}, json=payload, timeout=60)
        response.raise_for_status()
        create_data = (response.json() or {}).get("data") or {}
        video_id = str(create_data.get("id") or create_data.get("video_id") or "").strip()
        if not video_id:
            raise AvatarProviderError("O HeyGen não devolveu um video_id.")
        timeout = max(30, int(os.getenv("HEYGEN_TIMEOUT_SECONDS", "600")))
        deadline = time.monotonic() + timeout
        video_url = ""
        while time.monotonic() < deadline:
            resolved_status_path = status_path.format(video_id=video_id)
            status_response = requests.get(f"{base}{resolved_status_path}", headers={"x-api-key": api_key}, timeout=30)
            status_response.raise_for_status()
            data = status_response.json() or {}
            status_data = data.get("data") or data
            status = str(status_data.get("status") or "").lower()
            video_url = str(status_data.get("video_url") or "").strip()
            if status in {"completed", "complete", "ready"} and video_url:
                break
            if status in {"failed", "error", "cancelled"}:
                raise AvatarProviderError(f"O HeyGen terminou com estado {status}.")
            time.sleep(5)
        if not video_url:
            raise AvatarProviderError("O avatar excedeu o tempo de processamento configurado.")
        downloaded = _download_asset(video_url, output)
        if downloaded is None:
            raise AvatarProviderError("O vídeo do avatar não pôde ser descarregado.")
        return downloaded
    except (requests.RequestException, ValueError) as exc:
        raise AvatarProviderError(f"Falha na API de avatar: {exc}") from exc


def renderizar_video(lista_videos: list, audio_path: str, timestamps: list, output_path: str = "video_final.mp4") -> str:
    """Renderiza uma lista de vídeos verticais, cobrindo a duração do áudio."""
    audio = Path(audio_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = _probe_duration(audio)
    with tempfile.TemporaryDirectory(prefix="negobot-render-") as temporary:
        root = Path(temporary)
        parts: list[Path] = []
        remaining = duration
        for index, source_value in enumerate(lista_videos or []):
            source = Path(str(source_value))
            if not source.is_file():
                continue
            part_duration = min(remaining, max(0.1, _probe_duration(source)))
            part = root / f"part-{index:03d}.mp4"
            _render_background(source, part_duration, part)
            parts.append(part)
            remaining -= part_duration
            if remaining <= 0:
                break
        if not parts:
            fallback = root / "fallback.mp4"
            _render_card("NEGOBOT MOZ", duration, fallback)
            parts.append(fallback)
        concat = root / "concat.txt"
        concat.write_text("\n".join(f"file '{part.as_posix()}'" for part in parts) + "\n", encoding="utf-8")
        silent = root / "silent.mp4"
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-t", str(duration), "-c", "copy", "-movflags", "+faststart", str(silent)], timeout=240)
        captioned = root / "captioned.mp4"
        try:
            _burn_subtitles(silent, timestamps, captioned)
        except Exception as exc:
            logger.warning("Legendas palavra a palavra ignoradas: %s", exc)
            shutil.copyfile(silent, captioned)
        _run(["ffmpeg", "-y", "-i", str(captioned), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(output)], timeout=240)
    return str(output)


def _derive_keywords(job: dict[str, Any]) -> list[str]:
    supplied = job.get("background_keywords") or job.get("palavras_chave") or job.get("keywords")
    if isinstance(supplied, list) and supplied:
        return _normalise_keywords(supplied)
    title = str(job.get("title") or "business").strip()
    return [title[:80]]


def _mux_scene_audio(video: Path, audio: Path, duration: float, output: Path) -> None:
    _run(["ffmpeg", "-y", "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-t", str(duration), "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", "-movflags", "+faststart", str(output)], timeout=180)


def _mux_scene_silence(video: Path, duration: float, output: Path) -> None:
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-i", str(video), "-map", "1:v:0", "-map", "0:a:0", "-t", str(duration), "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", "-movflags", "+faststart", str(output)], timeout=180)


def _scene_text(scene: dict[str, Any], job: dict[str, Any]) -> str:
    return str(scene.get("text") or job.get("title") or "NEGOBOT-MOZ").strip()[:500]


def _render_scene_visual(scene: dict[str, Any], job: dict[str, Any], index: int, duration: float, job_dir: Path, pexels_assets: list[str], transition: str) -> Path:
    mode = str(scene.get("visual_mode") or ("upload_media" if scene.get("asset_url") else "ai_media"))
    internal_headers = _internal_asset_headers(job)
    source: Path | None = None
    kind = str(scene.get("asset_kind") or "")
    text = _scene_text(scene, job)
    if mode == "upload_media" and scene.get("asset_url"):
        suffix = ".jpg" if kind == "image" else ".mp4"
        source = _download_asset(str(scene["asset_url"]), job_dir / f"asset-{index:03d}{suffix}", headers=internal_headers)
    elif mode == "avatar_ai" and scene.get("avatar_id"):
        try:
            source = _heygen_avatar(text, str(scene["avatar_id"]), job_dir / f"avatar-{index:03d}.mp4")
            kind = "video"
        except AvatarProviderError as exc:
            logger.warning("Avatar indisponível na cena %s; fallback visual activo: %s", index, exc)
    elif mode == "ai_media":
        source = _generate_ai_image(text, job_dir / f"ai-{index:03d}.png")
        kind = "image" if source else kind
    if source is None and pexels_assets:
        source = Path(pexels_assets[index % len(pexels_assets)])
        kind = "video"
    part = job_dir / f"scene-visual-{index:03d}.mp4"
    try:
        if source and source.is_file():
            if kind == "image" or source.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                _render_image(source, duration, part, transition)
            else:
                _render_background(source, duration, part, transition)
        else:
            _render_card(text, duration, part, transition=transition)
    except Exception as exc:
        logger.warning("Visual ignorado na cena %s: %s", index, exc)
        _render_card(text, duration, part, transition=transition)
    return part


def render_job(job: dict[str, Any], output_dir: str, progress_callback: Any | None = None) -> str:
    """Renderiza cenas sequenciais com voz, avatar/media opcional e legendas individuais."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    job_dir = Path(tempfile.mkdtemp(prefix=f"video-{job['id']}-", dir=root))
    try:
        scenes = job.get("scenes") or []
        if not scenes:
            raise ValueError("O job precisa de pelo menos uma cena.")
        total_duration = sum(max(1.0, min(20.0, float(scene.get("duration_seconds") or 3.5))) for scene in scenes)
        transition = str(job.get("transition") or "fade")
        pexels_assets = baixar_videos_pexels(_derive_keywords(job), total_duration, str(job_dir / "pexels"))
        parts: list[Path] = []
        if progress_callback:
            progress_callback(10)
        for index, scene in enumerate(scenes):
            duration = max(1.0, min(20.0, float(scene.get("duration_seconds") or 3.5)))
            visual = _render_scene_visual(scene, job, index, duration, job_dir, pexels_assets, transition)
            audio = job_dir / f"scene-audio-{index:03d}.mp3"
            sample = None
            sample_url = str(scene.get("voice_sample_url") or "").strip()
            if sample_url:
                sample_mime = str(scene.get("voice_sample_mime") or "audio/mpeg").lower()
                sample_suffix = ".wav" if sample_mime == "audio/wav" else ".mp3"
                sample = _download_asset(sample_url, job_dir / f"voice-sample-{index:03d}{sample_suffix}", headers=_internal_asset_headers(job))
            has_audio = False
            text = _scene_text(scene, job)
            if text:
                try:
                    has_audio = asyncio.run(_tts(text, audio, str(job.get("language") or "pt"), scene.get("voice") or job.get("voice"), sample))
                except VoiceCloneError as exc:
                    logger.warning("Clonagem indisponível na cena %s; voz padrão usada: %s", index, exc)
                    try:
                        has_audio = asyncio.run(_tts(text, audio, str(job.get("language") or "pt"), scene.get("voice") or job.get("voice")))
                    except Exception:
                        has_audio = False
                except Exception as exc:
                    logger.warning("Voz indisponível na cena %s: %s", index, exc)
            captioned = job_dir / f"scene-captioned-{index:03d}.mp4"
            subtitles = bool(scene.get("subtitles", job.get("subtitles", True)))
            if has_audio and subtitles:
                try:
                    timestamps = gerar_timestamps(str(audio))
                    _burn_subtitles(visual, timestamps, captioned)
                except Exception as exc:
                    logger.warning("Legendas indisponíveis na cena %s: %s", index, exc)
                    shutil.copyfile(visual, captioned)
            else:
                shutil.copyfile(visual, captioned)
            final_scene = job_dir / f"scene-final-{index:03d}.mp4"
            if has_audio:
                _mux_scene_audio(captioned, audio, duration, final_scene)
            else:
                _mux_scene_silence(captioned, duration, final_scene)
            parts.append(final_scene)
            if progress_callback:
                progress_callback(15 + int(75 * (index + 1) / len(scenes)))
        concat_file = job_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{path.as_posix()}'" for path in parts) + "\n", encoding="utf-8")
        output = root / f"{job['id']}.mp4"
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", "-movflags", "+faststart", str(output)], timeout=300)
        if progress_callback:
            progress_callback(98)
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError("FFmpeg não produziu o vídeo final.")
        return str(output)
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def render_job_with_tts(job: dict[str, Any], output_dir: str, progress_callback: Any | None = None) -> str:
    return render_job(job, output_dir, progress_callback=progress_callback)
