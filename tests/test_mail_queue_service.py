import json
import unittest
from unittest.mock import patch

from services import mail_queue_service


class FakeRedis:
    def __init__(self):
        self.items = []

    def rpush(self, queue, payload):
        self.items.append((queue, json.loads(payload)))
        return len(self.items)


class MailQueueServiceTests(unittest.TestCase):
    def test_enqueues_tenant_scoped_email(self):
        client = FakeRedis()
        with patch.object(mail_queue_service, "_client", return_value=client):
            result = mail_queue_service.enqueue_email(
                tenant_id="tenant-a",
                recipient="client@example.com",
                subject="Reset",
                body="Use this link",
                request_id="password-reset:abc",
            )
        self.assertTrue(result["queued"])
        self.assertEqual(client.items[0][0], "negobot:mail_jobs")
        envelope = client.items[0][1]
        self.assertEqual(envelope["job_id"], "password-reset:abc")
        self.assertEqual(envelope["tenant_id"], "tenant-a")
        self.assertEqual(envelope["kind"], "email_delivery")
        self.assertEqual(envelope["payload"]["to"], "client@example.com")

    def test_requires_tenant_and_recipient(self):
        with self.assertRaises(mail_queue_service.MailQueueError):
            mail_queue_service.enqueue_email(tenant_id="", recipient="x@example.com", subject="x", body="x")
        with self.assertRaises(mail_queue_service.MailQueueError):
            mail_queue_service.enqueue_email(tenant_id="tenant-a", recipient="", subject="x", body="x")


if __name__ == "__main__":
    unittest.main()
