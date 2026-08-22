import json
import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import video_pipeline
from pydantic import ValidationError
from video_service import Scene, VideoJobRequest


class FakeResponse:
    def __init__(self, payload=None, body=b"video-bytes", status_code=200):
        self.payload = payload
        self.body = body
        self.status_code = status_code
        self.headers = {"content-length": str(len(body))}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload

    def iter_content(self, chunk_size):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class VideoPipelineTests(unittest.TestCase):
    def test_pexels_downloads_portrait_assets_until_duration(self):
        search = FakeResponse({
            "videos": [{
                "id": 42,
                "duration": 8,
                "video_files": [{"link": "https://cdn.example/video.mp4", "width": 1080, "height": 1920}],
            }]
        })
        download = FakeResponse(body=b"mp4-content")
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"PEXELS_API_KEY": "test-key"}, clear=False), patch.object(video_pipeline.requests, "get", side_effect=[search, download]) as request:
            result = video_pipeline.baixar_videos_pexels(["business"], 5, directory)
            self.assertEqual(len(result), 1)
            self.assertTrue(Path(result[0]).is_file())
            self.assertEqual(Path(result[0]).read_bytes(), b"mp4-content")
            self.assertEqual(request.call_args_list[0].kwargs["params"]["orientation"], "portrait")
            self.assertEqual(request.call_args_list[0].kwargs["params"]["per_page"], 3)

    def test_pexels_without_key_uses_fallback(self):
        with patch.dict("os.environ", {}, clear=True), tempfile.TemporaryDirectory() as directory:
            self.assertEqual(video_pipeline.baixar_videos_pexels(["business"], 5, directory), [])

    def test_groq_roteiro_validates_contract(self):
        class FakeCompletions:
            def create(self, **kwargs):
                self.kwargs = kwargs
                message = types.SimpleNamespace(content=json.dumps({
                    "narracao": "Descubra uma forma simples de melhorar o seu negócio.",
                    "palavras_chave": ["business", "growth", "team"],
                }))
                return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

        class FakeGroq:
            def __init__(self, **kwargs):
                self.chat = types.SimpleNamespace(completions=FakeCompletions())

        with patch.dict(sys.modules, {"groq": types.SimpleNamespace(Groq=FakeGroq)}), patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=False):
            result = video_pipeline.gerar_roteiro("crescimento de vendas", "pt")
        self.assertIn("narracao", result)
        self.assertEqual(len(result["palavras_chave"]), 3)

    def test_advanced_scene_contract_is_validated(self):
        scene = Scene(text="Apresenta a oferta", duration_seconds=4, visual_mode="upload_media", asset_kind="image", voice="pt_mz_female", voice_sample_url="https://app.example/assets/voice", subtitles=False)
        self.assertEqual(scene.visual_mode, "upload_media")
        self.assertEqual(scene.asset_kind, "image")
        self.assertFalse(scene.subtitles)
        job = VideoJobRequest(tenant_id="tenant-a", title="Oferta", scenes=[scene], transition="fade")
        self.assertEqual(job.transition, "fade")

    def test_heygen_v3_adapter_uses_vertical_contract(self):
        created = FakeResponse({"data": {"id": "video-123"}})
        ready = FakeResponse({"data": {"status": "completed", "video_url": "https://files.example/video.mp4"}})
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"HEYGEN_API_KEY": "test-key", "HEYGEN_TIMEOUT_SECONDS": "30"}, clear=False), patch.object(video_pipeline.requests, "post", return_value=created) as post, patch.object(video_pipeline.requests, "get", return_value=ready), patch.object(video_pipeline, "_download_asset", return_value=Path(directory) / "avatar.mp4") as download:
            result = video_pipeline._heygen_avatar("Fala sobre a oferta", "avatar-abc", Path(directory) / "avatar.mp4")
        self.assertEqual(result.name, "avatar.mp4")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["type"], "avatar")
        self.assertEqual(payload["aspect_ratio"], "9:16")
        self.assertEqual(payload["resolution"], "1080p")
        self.assertTrue(post.call_args.kwargs["headers"]["Idempotency-Key"].startswith("negobot-"))
        self.assertEqual(download.call_args.args[0], "https://files.example/video.mp4")

    def test_advanced_scene_rejects_private_or_invalid_asset_urls(self):
        with self.assertRaises(ValidationError):
            Scene(text="Cena", visual_mode="upload_media", asset_url="http://private.local/video.mp4")
        with self.assertRaises(ValidationError):
            Scene(text="Cena", voice="voz com espaços")

    def test_tts_falls_back_to_offline_after_edge_tts_error(self):
        class BrokenCommunicate:
            def __init__(self, *args, **kwargs):
                pass

            async def save(self, path):
                raise RuntimeError("403 Invalid response status")

        edge_module = types.SimpleNamespace(Communicate=BrokenCommunicate)
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {"edge_tts": edge_module}), patch.object(video_pipeline, "_offline_tts", return_value=True) as fallback:
            result = asyncio.run(video_pipeline._tts("Olá, esta é uma narração de teste.", Path(directory) / "audio.mp3", "pt-MZ", "pt_mz_male"))
        self.assertTrue(result)
        fallback.assert_called_once()

    def test_offline_tts_converts_espeak_wav_to_mp3_and_cleans_temp_file(self):
        def fake_run(command, timeout=90):
            if command[0] == "espeak-ng":
                Path(command[command.index("-w") + 1]).write_bytes(b"wav")
            elif command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"mp3")

        with tempfile.TemporaryDirectory() as directory, patch.object(video_pipeline, "_run", side_effect=fake_run):
            output = Path(directory) / "audio.mp3"
            self.assertTrue(video_pipeline._offline_tts("Olá", output, "pt-MZ"))
            self.assertTrue(output.is_file())
            self.assertFalse(output.with_suffix(".wav").exists())

    def test_voice_aliases_are_resolved_without_provider_call(self):
        self.assertEqual(video_pipeline._resolved_edge_voice("pt-MZ", "pt_mz_male"), "pt-BR-AntonioNeural")
        self.assertEqual(video_pipeline._resolved_edge_voice("en", "en_us_female"), "en-US-AriaNeural")

    def test_render_job_composes_multiple_fallback_scenes_without_external_apis(self):
        def no_provider(coroutine):
            coroutine.close()
            return False

        with tempfile.TemporaryDirectory() as directory, patch.object(video_pipeline, "baixar_videos_pexels", return_value=[]), patch.object(video_pipeline, "_generate_ai_image", return_value=None), patch.object(video_pipeline.asyncio, "run", side_effect=no_provider):
            output = video_pipeline.render_job({"id": "job-scenes", "tenant_id": "tenant-a", "title": "Oferta", "language": "pt-MZ", "transition": "fade", "scenes": [{"text": "Cena um", "duration_seconds": 1}, {"text": "Cena dois", "duration_seconds": 1, "subtitles": False}]}, directory)
            path = Path(output)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 1000)
            self.assertFalse((Path(directory) / "video-job-scenes-" ).exists())

    def test_groq_roteiro_rejects_invalid_contract(self):
        class FakeGroq:
            def __init__(self, **kwargs):
                message = types.SimpleNamespace(content=json.dumps({"narracao": "texto", "palavras_chave": ["one"]}))
                self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kwargs: types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])))

        with patch.dict(sys.modules, {"groq": types.SimpleNamespace(Groq=FakeGroq)}), patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}, clear=False):
            with self.assertRaises(ValueError):
                video_pipeline.gerar_roteiro("tema", "en")


if __name__ == "__main__":
    unittest.main()
