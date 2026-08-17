import base64
import io
import unittest
from unittest.mock import Mock, patch

from config import Config
from services.evolution_service import send_whatsapp, transcrever_audio_mensagem


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


class TestEvolutionService(unittest.TestCase):
    def setUp(self):
        self.old_url = getattr(Config, "EVOLUTION_API_URL", None)
        self.old_key = getattr(Config, "EVOLUTION_API_KEY", None)
        Config.EVOLUTION_API_URL = "https://evolution.test"
        Config.EVOLUTION_API_KEY = "test-evolution-key"

    def tearDown(self):
        Config.EVOLUTION_API_URL = self.old_url
        Config.EVOLUTION_API_KEY = self.old_key

    @patch("services.evolution_service.requests.post")
    def test_send_text_envia_payload_v2(self, post):
        post.return_value = FakeResponse(200, {"status": "PENDING"})
        self.assertTrue(send_whatsapp("258840000000", "Olá", instance_name="assistente_negobot"))
        post.assert_called_once()
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        self.assertIn("/message/sendText/assistente_negobot", url)
        self.assertEqual(payload["number"], "258840000000")
        self.assertEqual(payload["text"], "Olá")

    @patch("services.evolution_service.requests.post")
    def test_send_text_faz_fallback_se_v2_devolve_400(self, post):
        post.side_effect = [FakeResponse(400, text="invalid payload"), FakeResponse(200)]
        self.assertTrue(send_whatsapp("258840000000", "Olá", instance_name="assistente_negobot"))
        self.assertEqual(post.call_count, 2)
        self.assertIn("textMessage", post.call_args.kwargs["json"])

    @patch("services.evolution_service.requests.post")
    def test_send_text_trata_erro_5xx(self, post):
        post.return_value = FakeResponse(500, text="server error")
        self.assertFalse(send_whatsapp("258840000000", "Olá", instance_name="assistente_negobot"))

    @patch("services.groq_service.transcrever_audio_groq", return_value="Olá transcrito")
    @patch("services.evolution_service.requests.post")
    def test_recupera_midia_por_id_e_transcreve(self, post, transcribe):
        fake_ogg = b"OggS" + b"audio-test"
        encoded = base64.b64encode(fake_ogg).decode()
        post.return_value = FakeResponse(200, {"base64": encoded})
        payload = {
            "key": {"id": "msg-audio-001", "remoteJid": "258840000000@s.whatsapp.net"},
            "message": {"audioMessage": {"mimetype": "audio/ogg; codecs=opus"}},
            "messageType": "audioMessage",
        }
        result = transcrever_audio_mensagem(payload, instance_name="assistente_negobot")
        self.assertEqual(result, "Olá transcrito")
        request_payload = post.call_args.kwargs["json"]
        self.assertEqual(request_payload["message"]["key"]["id"], "msg-audio-001")
        self.assertTrue(request_payload["convertToMp4"])
        transcribe.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
