import unittest
from datetime import datetime, timedelta, timezone

from services.trial_service import (
    ACTIVE_STATUS,
    EXPIRED_STATUS,
    PENDING_STATUS,
    active_fields,
    is_expired,
    pending_fields,
    trial_expiry,
)


class TrialLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)

    def test_pending_qr_has_no_expiry_even_with_legacy_expiry(self):
        data = {**pending_fields("258840000000", self.start), "data_expiracao": self.start - timedelta(days=1)}
        self.assertEqual(data["trial_status"], PENDING_STATUS)
        self.assertIsNone(trial_expiry(data))
        self.assertFalse(is_expired(data, self.start))

    def test_open_starts_exactly_two_days(self):
        data = active_fields("258840000000", self.start)
        self.assertEqual(data["trial_status"], ACTIVE_STATUS)
        self.assertEqual(data["trial_expires_at"], self.start + timedelta(days=2))
        self.assertFalse(is_expired(data, self.start + timedelta(days=1, hours=23)))
        self.assertTrue(is_expired(data, self.start + timedelta(days=2)))

    def test_trial_duration_is_independent_of_billing_region(self):
        for region in ("mozambique", "international"):
            data = {**active_fields("258840000000", self.start), "billing_region": region}
            self.assertEqual(data["trial_expires_at"], self.start + timedelta(days=2))
            self.assertTrue(is_expired(data, self.start + timedelta(days=2)))

    def test_expired_status_is_expired(self):
        data = {"trial_status": EXPIRED_STATUS}
        self.assertTrue(is_expired(data, self.start))


if __name__ == "__main__":
    unittest.main(verbosity=2)
