import json
import os
import unittest
from unittest.mock import patch

from services import ai_pool_service
from services.incoming_queue import enqueue_incoming_event, validate_event
import incoming_worker


class FakeRedis:
    def __init__(self):
        self.items = []

    def rpush(self, queue, value):
        self.items.append((queue, value))
        return len(self.items)


class AiPoolTests(unittest.TestCase):
    def setUp(self):
        ai_pool_service._CURSOR = iter(range(1000))

    def test_round_robin_distributes_configured_providers(self):
        env = {
            "GROQ_API_KEY": "g-key",
            "GROQ_MODEL": "g-model",
            "CEREBRAS_API_KEY": "c-key",
            "CEREBRAS_MODEL": "c-model",
            "OPENROUTER_API_KEY": "",
        }
        calls = []

        def post(url, **kwargs):
            calls.append(url)
            return type("Response", (), {"status_code": 200, "json": lambda self: {"choices": [{"message": {"content": "ok"}}]}})()

        with patch.dict(os.environ, env, clear=False), patch("services.ai_pool_service.requests.post", side_effect=post):
            for _ in range(4):
                result = ai_pool_service.generate_text([{"role": "user", "content": "Olá"}])
                self.assertEqual(result["text"], "ok")

        self.assertEqual(len(calls), 4)
        self.assertEqual(sum("groq" in url for url in calls), 2)
        self.assertEqual(sum("cerebras" in url for url in calls), 2)

    def test_fallback_openrouter_after_primary_failure(self):
        env = {"GROQ_API_KEY": "g-key", "GROQ_MODEL": "g-model", "OPENROUTER_API_KEY": "o-key", "OPENROUTER_MODEL": "openrouter/free"}

        class Failed:
            status_code = 429
            text = "rate limit"

            def json(self):
                return {}

        class Success:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": "fallback"}}]}

        with patch.dict(os.environ, env, clear=False), patch("services.ai_pool_service.requests.post", side_effect=[Failed(), Success()]) as post:
            result = ai_pool_service.generate_text([])

        self.assertEqual(result["provider"], "openrouter")
        self.assertTrue(result["fallback"])
        self.assertEqual(post.call_count, 2)
        self.assertIn("openrouter", post.call_args_list[-1].args[0])

    def test_no_configured_provider_returns_friendly_message(self):
        keys = [provider["key"] for provider in ai_pool_service._PRIMARY_PROVIDERS] + ["GITHUB_TOKEN", "OPENROUTER_API_KEY"]
        with patch.dict(os.environ, {key: "" for key in keys}, clear=False), patch("services.ai_pool_service.requests.post") as post:
            result = ai_pool_service.generate_text([])
        self.assertEqual(result["provider"], "none")
        self.assertIn("processar muitas mensagens", result["text"])
        post.assert_not_called()


class IncomingQueueTests(unittest.TestCase):
    def test_validates_message_event_shape(self):
        self.assertTrue(validate_event({"event": "messages.upsert", "data": {"key": {"id": "1"}}}))
        self.assertFalse(validate_event({"event": "messages.upsert", "data": []}))
        self.assertTrue(validate_event({"event": "connection.update", "data": {}}))

    def test_enqueues_fifo_envelope(self):
        fake = FakeRedis()
        payload = {"event": "messages.upsert", "data": {"key": {"id": "msg-1"}}}
        with patch("services.incoming_queue._redis_client", return_value=fake):
            result = enqueue_incoming_event(payload)
        self.assertTrue(result["queued"])
        self.assertEqual(result["position"], 1)
        queue, raw = fake.items[0]
        self.assertEqual(queue, "whatsapp_incoming_queue")
        envelope = json.loads(raw)
        self.assertEqual(envelope["payload"]["data"]["key"]["id"], "msg-1")

    def test_worker_processes_envelope_and_calls_legacy_handler(self):
        payload = {"event": "messages.upsert", "data": {"key": {"id": "msg-2"}}}
        raw = json.dumps({"event_id": "evt-2", "enqueued_at": 1.0, "payload": payload})
        with patch("incoming_worker.processar_webhook_background") as handler:
            accepted = incoming_worker.process_queue_item(("whatsapp_incoming_queue", raw))
        self.assertTrue(accepted)
        handler.assert_called_once()
        processed_payload = handler.call_args.args[0]
        self.assertEqual(processed_payload["data"]["key"]["id"], "msg-2")
        self.assertEqual(processed_payload["_negobot_queue_enqueued_at"], 1.0)

    def test_worker_initializes_firestore_before_consuming(self):
        with patch.object(incoming_worker.extensions, "db", None), patch.object(
            incoming_worker.extensions, "init_extensions", return_value=object()
        ) as init_extensions:
            incoming_worker._ensure_firestore()
        init_extensions.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
