import json
import unittest
from unittest.mock import patch

from services import ai_queue_service


class FakeRedis:
    def __init__(self, result=None):
        self.result = result
        self.items = []

    def rpush(self, queue, payload):
        self.items.append((queue, json.loads(payload)))
        return len(self.items)

    def get(self, key):
        return self.result


class AIQueueServiceTests(unittest.TestCase):
    def test_publishes_tenant_scoped_job_and_reads_matching_result(self):
        result = json.dumps({"job_id": "req-1", "tenant_id": "tenant-a", "text": "Olá", "provider": "groq"})
        client = FakeRedis(result)
        with patch.object(ai_queue_service, "_client", return_value=client):
            response = ai_queue_service.request_ai_text(
                tenant_id="tenant-a",
                messages=[{"role": "user", "content": "Olá"}],
                request_id="req-1",
                timeout_seconds=2,
            )
        self.assertEqual(response["text"], "Olá")
        self.assertEqual(client.items[0][0], "negobot:ai_jobs")
        self.assertEqual(client.items[0][1]["job_id"], "req-1")
        self.assertEqual(client.items[0][1]["tenant_id"], "tenant-a")
        self.assertEqual(client.items[0][1]["kind"], "text_generation")

    def test_rejects_result_from_another_tenant(self):
        result = json.dumps({"job_id": "req-2", "tenant_id": "tenant-b", "text": "não"})
        client = FakeRedis(result)
        with patch.object(ai_queue_service, "_client", return_value=client):
            with self.assertRaises(ai_queue_service.AIQueueError) as error:
                ai_queue_service.request_ai_text(
                    tenant_id="tenant-a",
                    messages=[{"role": "user", "content": "Olá"}],
                    request_id="req-2",
                    timeout_seconds=2,
                )
        self.assertEqual(str(error.exception), "ai_result_tenant_mismatch")

    def test_requires_tenant(self):
        with self.assertRaises(ai_queue_service.AIQueueError) as error:
            ai_queue_service.request_ai_text(tenant_id="", messages=[{"role": "user", "content": "Olá"}])
        self.assertEqual(str(error.exception), "tenant_id_obrigatorio")


if __name__ == "__main__":
    unittest.main()
