import base64
import io
import sys
import types
import unittest
import wave
from unittest.mock import patch

sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))

from config import Config
import services.groq_service  # noqa: F401 — garante que o alvo do mock existe antes do patch
from services.evolution_service import (
    _normalizar_audio_para_whisper,
    _webhook_payload,
    criar_e_configurar_instancia_automatica,
    send_whatsapp,
    transcrever_audio_mensagem,
)


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


def _valid_wav_bytes(duration_seconds=0.1):
    output = io.BytesIO()
    sample_rate = 16000
    frames = b"\x00\x00" * int(sample_rate * duration_seconds)
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)
    return output.getvalue()


class TestEvolutionService(unittest.TestCase):
    def setUp(self):
        self.old_url = getattr(Config, "EVOLUTION_API_URL", None)
        self.old_key = getattr(Config, "EVOLUTION_API_KEY", None)
        Config.EVOLUTION_API_URL = "https://evolution.test"
        Config.EVOLUTION_API_KEY = "test-evolution-key"

    def tearDown(self):
        Config.EVOLUTION_API_URL = self.old_url
        Config.EVOLUTION_API_KEY = self.old_key

    @patch("services.evolution_service.time.sleep")
    @patch("services.evolution_service.requests.post")
    @patch("services.evolution_service.requests.get")
    def test_instancia_existente_nao_e_apagada_nem_recriada(self, get, post, sleep):
        get.return_value = FakeResponse(200, {"instance": {"state": "connecting"}})
        post.return_value = FakeResponse(200, {"status": "SUCCESS"})
        old_webhook = getattr(Config, "WEBHOOK_URL", None)
        Config.WEBHOOK_URL = "https://webhook.test/webhook"
        try:
            self.assertTrue(criar_e_configurar_instancia_automatica("258840000000"))
        finally:
            Config.WEBHOOK_URL = old_webhook
        self.assertFalse(any("/instance/create" in call.args[0] for call in post.call_args_list))
        self.assertFalse(any("/instance/delete" in call.args[0] for call in post.call_args_list))
        self.assertFalse(any("/instance/logout" in call.args[0] for call in post.call_args_list))
        webhook_payload = post.call_args_list[-1].kwargs["json"]
        self.assertIn("webhook", webhook_payload)
        self.assertTrue(webhook_payload["webhook"]["enabled"])

    @patch("services.evolution_service.time.sleep")
    @patch("services.evolution_service.requests.post")
    @patch("services.evolution_service.requests.get")
    def test_nova_instancia_configura_webhook_depois_do_create(self, get, post, sleep):
        get.return_value = FakeResponse(404, {"error": "Not Found"})
        post.side_effect = [
            FakeResponse(201, {"status": "SUCCESS"}),
            FakeResponse(200, {"status": "SUCCESS"}),
            FakeResponse(200, {"status": "SUCCESS"}),
        ]
        old_webhook = getattr(Config, "WEBHOOK_URL", None)
        Config.WEBHOOK_URL = "https://webhook.test/webhook"
        try:
            self.assertTrue(criar_e_configurar_instancia_automatica("258840000000"))
        finally:
            Config.WEBHOOK_URL = old_webhook
        create_payload = post.call_args_list[0].kwargs["json"]
        self.assertEqual(create_payload["instanceName"], "258840000000")
        self.assertNotIn("webhook", create_payload)
        webhook_payload = post.call_args_list[-1].kwargs["json"]
        self.assertIn("webhook", webhook_payload)
        self.assertEqual(webhook_payload["webhook"]["url"], "https://webhook.test/webhook")

    def test_webhook_usa_evento_de_grupo_da_evolution_v2(self):
        events = _webhook_payload("https://webhook.test/webhook")["webhook"]["events"]
        self.assertIn("GROUP_UPDATE", events)
        self.assertNotIn("GROUPS_UPDATE", events)

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

    def test_normaliza_wav_valido(self):
        normalized = _normalizar_audio_para_whisper(_valid_wav_bytes())
        self.assertTrue(normalized.startswith(b"RIFF"))
        self.assertEqual(normalized[8:12], b"WAVE")

    def test_rejeita_bytes_ogg_invalidos(self):
        invalid_ogg = b"OggS" + b"audio-test"
        self.assertEqual(_normalizar_audio_para_whisper(invalid_ogg), b"")

    @patch("services.ai_queue_service.request_ai_transcription", return_value={"text": "Olá transcrito", "provider": "groq-whisper"})
    @patch("services.evolution_service.requests.post")
    def test_recupera_midia_por_id_normaliza_e_transcreve(self, post, transcribe):
        encoded = base64.b64encode(_valid_wav_bytes()).decode()
        post.return_value = FakeResponse(200, {"base64": encoded})
        payload = {
            "key": {"id": "msg-audio-001", "remoteJid": "258840000000@s.whatsapp.net"},
            "message": {"audioMessage": {"mimetype": "audio/wav"}},
            "messageType": "audioMessage",
        }
        result = transcrever_audio_mensagem(payload, instance_name="assistente_negobot")
        self.assertEqual(result, "Olá transcrito")
        request_payload = post.call_args.kwargs["json"]
        self.assertEqual(request_payload["message"]["key"]["id"], "msg-audio-001")
        self.assertTrue(request_payload["convertToMp4"])
        transcribe.assert_called_once()
        self.assertEqual(transcribe.call_args.kwargs["tenant_id"], "whatsapp_instance:assistente_negobot")
        self.assertEqual(transcribe.call_args.kwargs["request_id"], "audio:msg-audio-001")
        self.assertEqual(transcribe.call_args.kwargs["filename"], "audio.wav")

    @patch("services.ai_queue_service.request_ai_transcription")
    @patch("services.evolution_service.requests.post")
    def test_nao_envia_audio_invalido_ao_ai_worker(self, post, transcribe):
        invalid_ogg = b"OggS" + b"audio-test"
        encoded = base64.b64encode(invalid_ogg).decode()
        post.return_value = FakeResponse(200, {"base64": encoded})
        payload = {
            "key": {"id": "msg-audio-invalid"},
            "message": {"audioMessage": {"mimetype": "audio/ogg; codecs=opus"}},
        }
        self.assertEqual(transcrever_audio_mensagem(payload), "")
        transcribe.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
