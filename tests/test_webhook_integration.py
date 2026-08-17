import unittest
from unittest.mock import patch

from flask import Flask

from config import Config
from routes.webhook_routes import PROCESSADOS, webhook_bp
from tests.fixtures.evolution_messages import (
    INSTANCE,
    audio_message_payload,
    group_message_payload,
    message_payload,
    unknown_event_payload,
)


class ImmediateThread:
    """Executa o alvo no mesmo processo para testar o background sem esperar."""

    def __init__(self, target=None, args=(), kwargs=None, **_extra):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)


class TestWebhookIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.register_blueprint(webhook_bp)

    def setUp(self):
        PROCESSADOS.clear()
        self.previous_instance = getattr(Config, "EVOLUTION_INSTANCE_NAME", None)
        Config.EVOLUTION_INSTANCE_NAME = INSTANCE
        self.client = self.app.test_client()

    def tearDown(self):
        Config.EVOLUTION_INSTANCE_NAME = self.previous_instance

    def post(self, payload):
        with patch("routes.webhook_routes.threading.Thread", ImmediateThread):
            return self.client.post("/webhook", json=payload)

    @patch("routes.webhook_routes.process_central_flow")
    def test_mensagem_texto_eh_roteada_para_fluxo_central(self, central_flow):
        payload = message_payload(text="Olá", instance=INSTANCE)
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        central_flow.assert_called_once()
        self.assertEqual(central_flow.call_args.kwargs["message_text"], "Olá")

    @patch("routes.webhook_routes.process_client_flow")
    @patch("routes.webhook_routes.Config.EVOLUTION_INSTANCE_NAME", "assistente_negobot")
    def test_instancia_diferente_eh_roteada_para_fluxo_cliente(self, client_flow):
        payload = message_payload(text="Olá cliente", instance="cliente_teste")
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        client_flow.assert_called_once()
        self.assertEqual(client_flow.call_args.kwargs["nome_instancia_atual"], "cliente_teste")

    @patch("routes.webhook_routes.process_central_flow")
    def test_from_me_eh_ignorado(self, central_flow):
        response = self.post(message_payload(from_me=True, message_id="msg-from-me"))
        self.assertEqual(response.status_code, 200)
        central_flow.assert_not_called()

    @patch("routes.webhook_routes.process_central_flow")
    def test_grupo_eh_ignorado(self, central_flow):
        response = self.post(group_message_payload())
        self.assertEqual(response.status_code, 200)
        central_flow.assert_not_called()

    @patch("routes.webhook_routes.process_central_flow")
    def test_mensagem_duplicada_eh_processada_uma_vez(self, central_flow):
        payload = message_payload(message_id="msg-duplicate")
        first = self.post(payload)
        second = self.post(payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        central_flow.assert_called_once()

    @patch("routes.webhook_routes.process_central_flow")
    def test_evento_desconhecido_nao_roteia_fluxo(self, central_flow):
        response = self.post(unknown_event_payload())
        self.assertEqual(response.status_code, 200)
        central_flow.assert_not_called()

    @patch("routes.webhook_routes.process_central_flow")
    @patch("routes.webhook_routes.transcrever_audio_mensagem", return_value="Quais são os preços?")
    def test_audio_transcrito_e_encaminhado(self, transcribe, central_flow):
        response = self.post(audio_message_payload(message_id="msg-audio-ok"))
        self.assertEqual(response.status_code, 200)
        transcribe.assert_called_once()
        central_flow.assert_called_once()
        self.assertEqual(central_flow.call_args.kwargs["message_text"], "Quais são os preços?")

    @patch("routes.webhook_routes.process_central_flow")
    @patch("routes.webhook_routes.send_whatsapp")
    @patch("routes.webhook_routes.transcrever_audio_mensagem", return_value="")
    def test_audio_invalido_recebe_fallback(self, transcribe, send_text, central_flow):
        response = self.post(audio_message_payload(message_id="msg-audio-fail"))
        self.assertEqual(response.status_code, 200)
        transcribe.assert_called_once()
        central_flow.assert_not_called()
        send_text.assert_called_once()
        self.assertIn("não consegui transcrevê-la", send_text.call_args.args[1])

    def test_payload_vazio_responde_200(self):
        response = self.post({})
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
