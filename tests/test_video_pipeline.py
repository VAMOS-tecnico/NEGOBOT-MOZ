import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import video_pipeline


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
