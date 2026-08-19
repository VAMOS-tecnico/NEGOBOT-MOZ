import unittest
from unittest.mock import patch

from services.runtime_health import liveness_report, readiness_report


class RuntimeHealthTests(unittest.TestCase):
    def test_liveness_is_process_only(self):
        self.assertEqual(liveness_report(), {"status": "ok"})

    def test_readiness_reports_offline_without_leaking_values(self):
        with patch.dict("os.environ", {"REDIS_URL": "redis://unavailable.invalid:6379/1"}, clear=True):
            report = readiness_report()
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(set(report["checks"]), {"firebase", "redis"})
        self.assertTrue(all(value in {"online", "offline"} for value in report["checks"].values()))
        self.assertNotIn("unavailable.invalid", repr(report))


if __name__ == "__main__":
    unittest.main()
