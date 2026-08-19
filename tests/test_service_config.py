import os
import unittest
from unittest.mock import patch

from services.service_config import EnvironmentContractError, enforce_profile, environment_report


class ServiceConfigTests(unittest.TestCase):
    def test_api_accepts_platform_secret_or_admin_token(self):
        env = {"FIREBASE_CONFIG": "configured", "REDIS_URL": "redis://test", "PLATFORM_SECRET_KEY": "configured"}
        report = environment_report("api", env)
        self.assertTrue(report["ok"])
        self.assertTrue(report["configured"]["PLATFORM_SECRET_KEY"])
        self.assertNotIn("configured", repr(report["configured"]))

    def test_api_rejects_when_firebase_and_session_secret_are_missing(self):
        with self.assertRaises(EnvironmentContractError) as context:
            enforce_profile("api", {"REDIS_URL": "redis://test"})
        self.assertIn("FIREBASE_CONFIG", str(context.exception))
        self.assertIn("one-of(PLATFORM_SECRET_KEY,ADMIN_TOKEN)", str(context.exception))

    def test_campaign_requires_evolution_and_firebase(self):
        report = environment_report("campaign", {"FIREBASE_CONFIG": "yes", "REDIS_URL": "yes"})
        self.assertFalse(report["ok"])
        self.assertEqual(report["required_missing"], ["EVOLUTION_API_URL", "EVOLUTION_API_KEY"])

    def test_billing_does_not_require_redis_for_autopay(self):
        self.assertTrue(environment_report("billing", {"FIREBASE_CONFIG": "yes"})["ok"])

    def test_report_only_contains_presence_booleans(self):
        env = {"FIREBASE_CONFIG": "SECRET-VALUE", "REDIS_URL": "redis://test", "ADMIN_TOKEN": "PRIVATE"}
        report = environment_report("api", env)
        self.assertTrue(report["ok"])
        self.assertTrue(all(isinstance(value, bool) for value in report["configured"].values()))
        self.assertNotIn("SECRET-VALUE", repr(report))
        self.assertNotIn("PRIVATE", repr(report))

    def test_current_profile_defaults_without_reading_values(self):
        with patch.dict(os.environ, {}, clear=True):
            from services.service_config import current_profile
            self.assertEqual(current_profile(), "api")


if __name__ == "__main__":
    unittest.main()
