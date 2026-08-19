import unittest
from datetime import datetime, timedelta, timezone

from services.central_account_service import (
    registry_is_expired,
    trial_fields_from_registry,
    claim_trial_for_account,
)


class FakeSnapshot:
    def __init__(self, data=None, exists=False):
        self.data = dict(data or {})
        self.exists = exists

    def to_dict(self):
        return dict(self.data)


class FakeDocument:
    def __init__(self, collection, key):
        self.collection = collection
        self.key = key

    def get(self):
        return self.collection.setdefault(self.key, FakeSnapshot())

    def set(self, values, merge=False):
        snapshot = self.collection.setdefault(self.key, FakeSnapshot())
        if merge:
            snapshot.data.update(values)
        else:
            snapshot.data = dict(values)
        snapshot.exists = True


class FakeQuery:
    def __init__(self, collection, field, value):
        self.collection = collection
        self.field = field
        self.value = value

    def limit(self, _amount):
        return self

    def stream(self):
        return [snapshot for snapshot in self.collection.rows.values() if snapshot.data.get(self.field) == self.value]


class FakeCollection:
    def __init__(self):
        self.rows = {}

    def document(self, key):
        return FakeDocument(self.rows, key)

    def where(self, field, _operator, value):
        return FakeQuery(self, field, value)


class FakeDB:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


class CentralTrialTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.start = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)

    def test_first_channel_claims_single_premium_trial(self):
        claimed, first = claim_trial_for_account(self.db, "ca_demo", "tenant-a", "telegram", email="a@example.com", now=self.start)
        self.assertTrue(claimed)
        self.assertEqual(first["started_channel"], "telegram")
        self.assertEqual(first["expires_at"], self.start + timedelta(days=2))
        self.assertEqual(first["trial_access_level"], "premium")

        second, stored = claim_trial_for_account(self.db, "ca_demo", "tenant-a", "whatsapp", email="a@example.com", now=self.start + timedelta(hours=1))
        self.assertFalse(second)
        self.assertEqual(stored["started_channel"], "telegram")
        self.assertEqual(stored["expires_at"], self.start + timedelta(days=2))

    def test_same_identity_cannot_claim_second_account_trial(self):
        first_claim, _ = claim_trial_for_account(self.db, "ca_first", "tenant-a", "telegram", email="same@example.com", now=self.start)
        self.assertTrue(first_claim)
        second_claim, blocker = claim_trial_for_account(self.db, "ca_second", "tenant-b", "whatsapp", email="same@example.com", now=self.start)
        self.assertFalse(second_claim)
        self.assertTrue(blocker["blocked_by_identity"])

    def test_registry_expiry_is_shared_by_channels(self):
        _, record = claim_trial_for_account(self.db, "ca_demo", "tenant-a", "whatsapp", now=self.start)
        self.assertFalse(registry_is_expired(record, self.start + timedelta(days=1, hours=23)))
        self.assertTrue(registry_is_expired(record, self.start + timedelta(days=2)))
        fields = trial_fields_from_registry(record, "telegram", "bot-name")
        self.assertEqual(fields["trial_connected_at"], self.start)
        self.assertEqual(fields["trial_expires_at"], self.start + timedelta(days=2))
        self.assertEqual(fields["trial_started_channel"], "whatsapp")
        self.assertEqual(fields["trial_last_connected_channel"], "telegram")


if __name__ == "__main__":
    unittest.main(verbosity=2)
