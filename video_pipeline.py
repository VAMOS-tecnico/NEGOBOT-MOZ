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
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

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


def _download_url(url: str, target: Path, max_bytes: int = MAX_ASSET_BYTES) -> Path:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Os assets devem usar URLs HTTPS públicas.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=DEFAULT_PEXELS_TIMEOUT, stream=True, headers={"User-Agent": "NEGOBOT-video/1.0"}) as response:
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


def _download_asset(url: str, target: Path) -> Path | None:
    try:
        return _download_url(url, target)
    except (OSError, requests.RequestException, ValueError) as exc:
        logger.warning("Asset externo ignorado: %s", exc)
        return None


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


async def _tts(text: str, output: Path, language: str, voice: str | None) -> bool:
    try:
        import edge_tts

        selected_voice = voice or ("pt-BR-AntonioNeural" if language.lower().startswith("pt") else "en-US-ChristopherNeural")
        communicator = edge_tts.Communicate(text, selected_voice)
        await communicator.save(str(output))
        return output.exists() and output.stat().st_size > 0
    except Exception as exc:
        logger.warning("TTS indisponível para o job: %s", exc)
        return False


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


def _render_card(text: str, duration: float, output: Path, background: str = "#102c3a") -> None:
    safe = _ffmpeg_text(text)
    drawtext = f"drawtext=text='{safe}':fontcolor=white:fontsize=54:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=12"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={background}:s=1080x1920:d={duration}", "-vf", drawtext, "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", str(output)], timeout=120)


def _render_background(source: Path, duration: float, output: Path) -> None:
    filter_graph = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
    _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(source), "-t", str(max(0.1, duration)), "-an", "-vf", filter_graph, "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart", str(output)], timeout=180)


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


def render_job(job: dict[str, Any], output_dir: str) -> str:
    """Renderiza um job com Pexels opcional e fallback determinístico."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    job_dir = Path(tempfile.mkdtemp(prefix=f"video-{job['id']}-", dir=root))
    try:
        scenes = job.get("scenes") or []
        if not scenes:
            raise ValueError("O job precisa de pelo menos uma cena.")
        total_duration = sum(float(scene.get("duration_seconds") or 3.5) for scene in scenes)
        pexels_assets = baixar_videos_pexels(_derive_keywords(job), total_duration, str(job_dir / "pexels"))
        parts: list[Path] = []
        for index, scene in enumerate(scenes):
            duration = max(1.0, min(20.0, float(scene.get("duration_seconds") or 3.5)))
            source: Path | None = None
            asset_url = scene.get("asset_url")
            if asset_url:
                source = _download_asset(str(asset_url), job_dir / f"asset-{index:03d}.mp4")
            if source is None and pexels_assets:
                source = Path(pexels_assets[index % len(pexels_assets)])
            part = job_dir / f"scene-{index:03d}.mp4"
            try:
                if source and source.is_file():
                    _render_background(source, duration, part)
                else:
                    _render_card(str(scene.get("text") or job.get("title") or "NEGOBOT-MOZ"), duration, part)
            except Exception as exc:
                logger.warning("Fundo de vídeo ignorado na cena %s: %s", index, exc)
                _render_card(str(scene.get("text") or job.get("title") or "NEGOBOT-MOZ"), duration, part)
            parts.append(part)
        concat_file = job_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{path.as_posix()}'" for path in parts) + "\n", encoding="utf-8")
        silent = job_dir / "silent.mp4"
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", "-movflags", "+faststart", str(silent)], timeout=240)
        audio = job_dir / "voice.mp3"
        spoken_text = str(job.get("narracao") or " ".join(str(scene.get("text") or "") for scene in scenes)).strip()
        has_audio = False
        if spoken_text:
            try:
                has_audio = asyncio.run(_tts(spoken_text, audio, str(job.get("language") or "pt"), job.get("voice")))
            except RuntimeError:
                has_audio = False
        captioned = job_dir / "captioned.mp4"
        if has_audio and job.get("subtitles", True):
            try:
                timestamps = gerar_timestamps(str(audio))
                _burn_subtitles(silent, timestamps, captioned)
            except Exception as exc:
                logger.warning("Whisper/legendas indisponível; vídeo seguirá sem legendas: %s", exc)
                shutil.copyfile(silent, captioned)
        else:
            shutil.copyfile(silent, captioned)
        output = root / f"{job['id']}.mp4"
        if has_audio:
            _run(["ffmpeg", "-y", "-i", str(captioned), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(output)], timeout=240)
        else:
            shutil.copyfile(captioned, output)
        if not output.exists() or output.stat().st_size == 0:
            raise RuntimeError("FFmpeg não produziu o vídeo final.")
        return str(output)
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def render_job_with_tts(job: dict[str, Any], output_dir: str) -> str:
    return render_job(job, output_dir)
