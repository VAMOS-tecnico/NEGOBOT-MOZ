import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from campaign_worker import (
    clean_phone,
    in_silence_window,
    next_allowed_time,
    parse_datetime,
    _recipient_allowed,
)


class CampaignWorkerPolicyTests(unittest.TestCase):
    def test_clean_phone_removes_whatsapp_suffix(self):
        self.assertEqual(clean_phone("+258 84 123 4567@s.whatsapp.net"), "258841234567")
        self.assertEqual(clean_phone("120363000000@g.us"), "120363000000@g.us")

    def test_naive_datetime_uses_maputo_timezone(self):
        parsed = parse_datetime("2026-08-19T10:30", "Africa/Maputo")
        self.assertEqual(parsed, datetime(2026, 8, 19, 8, 30, tzinfo=timezone.utc))

    def test_explicit_datetime_offset_is_preserved(self):
        parsed = parse_datetime("2026-08-19T10:30:00+00:00", "Africa/Maputo")
        self.assertEqual(parsed, datetime(2026, 8, 19, 10, 30, tzinfo=timezone.utc))

    def test_silence_window_crossing_midnight(self):
        tenant = {"campaign_settings": {"timezone": "Africa/Maputo", "silence_start": "22:00", "silence_end": "08:00"}}
        self.assertTrue(in_silence_window(datetime(2026, 8, 19, 21, 30, tzinfo=timezone.utc), tenant))
        self.assertFalse(in_silence_window(datetime(2026, 8, 19, 7, 30, tzinfo=timezone.utc), tenant))

    def test_next_allowed_time_moves_to_silence_end(self):
        tenant = {"campaign_settings": {"timezone": "Africa/Maputo", "silence_start": "22:00", "silence_end": "08:00"}}
        result = next_allowed_time(datetime(2026, 8, 19, 21, 30, tzinfo=timezone.utc), tenant)
        self.assertEqual(result, datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc))

    def test_opt_in_is_required_at_send_time(self):
        self.assertTrue(_recipient_allowed({"opt_in": True}))
        self.assertFalse(_recipient_allowed({"opt_in": False}))
        self.assertFalse(_recipient_allowed({"opt_in": True, "do_not_contact": True}))

    @patch("campaign_worker.time.sleep")
    @patch("campaign_worker.send_whatsapp", side_effect=[False, False, True])
    def test_send_retries_transient_evolution_failure(self, send_mock, _sleep_mock):
        from campaign_worker import _send_with_retries

        self.assertTrue(_send_with_retries("tenant-instance", "258841234567", "Mensagem de teste"))
        self.assertEqual(send_mock.call_count, 3)


if __name__ == "__main__":
    unittest.main()
