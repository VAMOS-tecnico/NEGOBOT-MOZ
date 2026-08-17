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
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger("negobot-video-pipeline")


def _safe_text(value: str) -> str:
    return re.sub(r"[^\w\s,.!?;:'-]", "", str(value or "")).strip()[:500]


def _run(command: list[str], timeout: int = 90) -> None:
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def _download_asset(url: str, target: Path) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    response = requests.get(url, timeout=20, stream=True, headers={"User-Agent": "NEGOBOT-video/1.0"})
    response.raise_for_status()
    content_length = int(response.headers.get("content-length") or 0)
    if content_length > 25 * 1024 * 1024:
        raise ValueError("Asset demasiado grande.")
    written = 0
    with target.open("wb") as handle:
        for chunk in response.iter_content(1024 * 256):
            written += len(chunk)
            if written > 25 * 1024 * 1024:
                raise ValueError("Asset demasiado grande.")
            handle.write(chunk)
    return target


async def _tts(text: str, output: Path, language: str, voice: str | None) -> bool:
    try:
        import edge_tts
        selected_voice = voice or ("pt-MZ-CarlotaNeural" if language.lower().startswith("pt") else "en-US-JennyNeural")
        communicator = edge_tts.Communicate(text, selected_voice)
        await communicator.save(str(output))
        return output.exists() and output.stat().st_size > 0
    except Exception as exc:
        logger.warning("TTS indisponível para o job: %s", exc)
        return False


def _render_card(text: str, duration: float, output: Path, background: str = "#102c3a") -> None:
    safe = _safe_text(text).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    drawtext = f"drawtext=text='{safe}':fontcolor=white:fontsize=54:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=12"
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={background}:s=1080x1920:d={duration}", "-vf", drawtext, "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-movflags", "+faststart", str(output)], timeout=90)


def render_job(job: dict[str, Any], output_dir: str) -> str:
    """Renderiza um job e devolve o caminho do MP4 final.

    O pipeline usa cartões de fallback quando não há assets externos. Isso
    mantém o serviço funcional e previsível; assets HTTPS podem ser adicionados
    numa fase seguinte sem permitir caminhos locais ou downloads ilimitados.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    job_dir = Path(tempfile.mkdtemp(prefix=f"video-{job['id']}-", dir=root))
    try:
        scenes = job.get("scenes") or []
        parts: list[Path] = []
        for index, scene in enumerate(scenes):
            asset_url = scene.get("asset_url")
            if asset_url:
                try:
                    _download_asset(asset_url, job_dir / f"asset-{index}")
                except Exception as exc:
                    logger.warning("Asset ignorado no job %s: %s", job.get("id"), exc)
            part = job_dir / f"scene-{index:03d}.mp4"
            _render_card(str(scene.get("text") or job.get("title") or "NEGOBOT-MOZ"), float(scene.get("duration_seconds") or 3.5), part)
            parts.append(part)
        concat_file = job_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{path.as_posix()}'" for path in parts), encoding="utf-8")
        output = root / f"{job['id']}.mp4"
        _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", "-movflags", "+faststart", str(output)], timeout=180)
        audio = job_dir / "voice.mp3"
        spoken_text = " ".join(str(scene.get("text") or "") for scene in scenes).strip()
        has_audio = False
        if spoken_text:
            try:
                has_audio = asyncio.run(_tts(spoken_text, audio, str(job.get("language") or "pt-MZ"), job.get("voice")))
            except RuntimeError:
                has_audio = False
        if has_audio:
            muxed = root / f"{job['id']}-audio.mp4"
            _run(["ffmpeg", "-y", "-i", str(output), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(muxed)], timeout=180)
            os.replace(muxed, output)
        if not output.exists():
            raise RuntimeError("FFmpeg não produziu o vídeo final.")
        return str(output)
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def render_job_with_tts(job: dict[str, Any], output_dir: str) -> str:
    # Mantém o worker síncrono, mas executa o TTS dentro do mesmo job se possível.
    return render_job(job, output_dir)
