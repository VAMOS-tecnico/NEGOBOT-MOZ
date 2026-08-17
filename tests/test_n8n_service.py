import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import Mock, patch

from services import n8n_service


class N8nServiceTests(unittest.TestCase):
    def setUp(self):
        self.previous = {key: os.environ.get(key) for key in ("N8N_CAMPAIGN_WEBHOOK_URL", "N8N_WEBHOOK_SECRET", "N8N_WEBHOOK_RETRIES", "N8N_WEBHOOK_TIMEOUT")}
        os.environ["N8N_CAMPAIGN_WEBHOOK_URL"] = "https://n8n.example/webhook/campaign"
        os.environ["N8N_WEBHOOK_SECRET"] = "secret-test"
        os.environ["N8N_WEBHOOK_RETRIES"] = "3"
        os.environ["N8N_WEBHOOK_TIMEOUT"] = "3"

    def tearDown(self):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @patch("services.n8n_service.time.sleep")
    @patch("services.n8n_service.requests.post")
    def test_dispatch_assina_correlaciona_e_envia_json(self, post, _sleep):
        response = Mock(status_code=202)
        post.return_value = response
        result = n8n_service.dispatch_campaign_event("campaign.dispatch", {"campaign_id": "cmp-1", "channels": ["instagram"]}, request_id="req-1")
        self.assertTrue(result["sent"])
        self.assertEqual(result["request_id"], "req-1")
        kwargs = post.call_args.kwargs
        raw = kwargs["data"]
        body = json.loads(raw)
        self.assertEqual(body["request_id"], "req-1")
        expected = hmac.new(b"secret-test", raw, hashlib.sha256).hexdigest()
        self.assertEqual(kwargs["headers"]["X-NEGOBOT-Signature"], expected)
        self.assertEqual(kwargs["headers"]["X-NEGOBOT-Event"], "campaign.dispatch")

    @patch("services.n8n_service.time.sleep")
    @patch("services.n8n_service.requests.post")
    def test_dispatch_faz_retry_em_erro_5xx(self, post, _sleep):
        post.side_effect = [Mock(status_code=503), Mock(status_code=502), Mock(status_code=204)]
        result = n8n_service.dispatch_campaign_event("campaign.dispatch", {"campaign_id": "cmp-2"}, request_id="req-2")
        self.assertTrue(result["sent"])
        self.assertEqual(post.call_count, 3)

    def test_dispatch_indica_nao_configurado_sem_segredo(self):
        os.environ.pop("N8N_WEBHOOK_SECRET", None)
        result = n8n_service.dispatch_campaign_event("campaign.dispatch", {"campaign_id": "cmp-3"})
        self.assertFalse(result["sent"])
        self.assertFalse(result["configured"])


if __name__ == "__main__":
    unittest.main()
