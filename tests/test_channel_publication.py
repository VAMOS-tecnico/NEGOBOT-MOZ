import unittest
from datetime import datetime, timedelta, timezone

from services import channel_publication_service as service


class FakeQueue:
    def __init__(self):
        self.zset = {}
        self.list = []

    def zadd(self, key, values):
        self.zset.update(values)
        return len(values)

    def zrangebyscore(self, key, _minimum, maximum, start=0, num=50):
        return [item for item, score in self.zset.items() if score <= maximum][start:start + num]

    def zrem(self, key, item):
        if item in self.zset:
            del self.zset[item]
            return 1
        return 0

    def rpush(self, key, item):
        self.list.append((key, item))
        return len(self.list)


class ChannelPublicationTests(unittest.TestCase):
    def test_capability_is_closed_until_adapter_exists(self):
        capability = service.channel_capability()
        self.assertFalse(capability["adapter_configured"])
        self.assertFalse(capability["can_publish"])
        self.assertEqual(capability["status"], "pending_authorization")

    def test_only_newsletter_jids_are_accepted(self):
        self.assertEqual(service.normalize_channel_jid("12345@newsletter"), "12345@newsletter")
        with self.assertRaises(ValueError):
            service.normalize_channel_jid("120363@g.us")

    def test_cta_requires_absolute_http_url(self):
        self.assertEqual(service.validate_cta_url("https://negobotmoz.duckdns.org/"), "https://negobotmoz.duckdns.org/")
        with self.assertRaises(ValueError):
            service.validate_cta_url("javascript:alert(1)")

    def test_publication_data_is_tenant_scoped_and_renders_cta(self):
        data = service.create_publication_data({
            "title": "Promoção",
            "body": "Temos produtos novos.",
            "channel_jid": "12345@newsletter",
            "cta_url": "https://negobotmoz.duckdns.org/",
            "cta_label": "Ver catálogo",
        }, "tenant-a")
        self.assertEqual(data["tenant_id"], "tenant-a")
        self.assertIn("Ver catálogo: https://negobotmoz.duckdns.org/", data["rendered_body"])
        self.assertEqual(data["status"], "draft")

    def test_future_publication_is_promoted_only_when_due(self):
        queue = FakeQueue()
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        result = service.enqueue_publication("pub-1", future, queue=queue)
        self.assertTrue(result["scheduled"])
        self.assertEqual(queue.list, [])
        queue.zset["pub-1"] = datetime.now(timezone.utc).timestamp() - 1
        self.assertEqual(service.promote_scheduled(queue), 1)
        self.assertEqual(queue.list, [(service.PUBLICATION_QUEUE, "pub-1")])


if __name__ == "__main__":
    unittest.main()
