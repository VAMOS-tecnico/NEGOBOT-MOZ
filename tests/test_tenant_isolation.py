import unittest
from unittest.mock import patch

from flask import Flask

from config import Config
from routes.webhook_routes import PROCESSADOS, webhook_bp
from tests.fixtures.evolution_messages import message_payload
from tests.test_webhook_integration import ImmediateThread


class TestTenantIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.register_blueprint(webhook_bp)

    def setUp(self):
        PROCESSADOS.clear()
        self.previous_instance = getattr(Config, "EVOLUTION_INSTANCE_NAME", None)
        Config.EVOLUTION_INSTANCE_NAME = "assistente_negobot"
        self.client = self.app.test_client()

    def tearDown(self):
        Config.EVOLUTION_INSTANCE_NAME = self.previous_instance

    @patch("routes.webhook_routes.process_client_flow")
    def test_dois_tenants_sao_despachados_separadamente(self, client_flow):
        tenant_a = message_payload(text="Mensagem A", message_id="tenant-a-001", instance="tenant_a")
        tenant_b = message_payload(text="Mensagem B", message_id="tenant-b-001", instance="tenant_b")

        with patch("routes.webhook_routes.threading.Thread", ImmediateThread):
            first = self.client.post("/webhook", json=tenant_a)
            second = self.client.post("/webhook", json=tenant_b)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(client_flow.call_count, 2)
        routed_instances = [call.kwargs["nome_instancia_atual"] for call in client_flow.call_args_list]
        routed_messages = [call.kwargs["message_text"] for call in client_flow.call_args_list]
        self.assertEqual(routed_instances, ["tenant_a", "tenant_b"])
        self.assertEqual(routed_messages, ["Mensagem A", "Mensagem B"])

    @patch("routes.webhook_routes.process_central_flow")
    @patch("routes.webhook_routes.process_client_flow")
    def test_tenant_nao_e_enviado_para_fluxo_central(self, client_flow, central_flow):
        payload = message_payload(text="Mensagem privada", message_id="tenant-private-001", instance="tenant_privado")
        with patch("routes.webhook_routes.threading.Thread", ImmediateThread):
            response = self.client.post("/webhook", json=payload)

        self.assertEqual(response.status_code, 200)
        central_flow.assert_not_called()
        client_flow.assert_called_once()
        self.assertEqual(client_flow.call_args.kwargs["nome_instancia_atual"], "tenant_privado")


if __name__ == "__main__":
    unittest.main(verbosity=2)
