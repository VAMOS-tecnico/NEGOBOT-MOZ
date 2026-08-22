import os
import unittest
from unittest.mock import Mock, patch

from services import evolution_instance_cleanup as cleanup


class EvolutionInstanceCleanupTests(unittest.TestCase):
    def test_open_instance_is_never_candidate_even_with_old_disconnect_reason(self):
        item = {
            "name": "client-open",
            "connectionStatus": "open",
            "disconnectionReasonCode": 401,
            "disconnectionObject": "device_removed",
        }
        self.assertEqual(cleanup._is_candidate(item, 1800), (False, "connected"))

    def test_close_instance_is_candidate(self):
        item = {"name": "client-close", "connectionStatus": "close"}
        self.assertEqual(cleanup._is_candidate(item, 1800), (True, "close"))

    def test_connecting_without_owner_requires_grace_window(self):
        item = {"name": "client-connecting", "connectionStatus": "connecting", "ownerJid": None, "createdAt": "2020-01-01T00:00:00Z"}
        self.assertEqual(cleanup._is_candidate(item, 1800), (True, "connecting_without_owner_after_grace"))

    @patch.dict(os.environ, {"EVOLUTION_AUTO_DELETE_DISCONNECTED": "true", "EVOLUTION_CENTRAL_INSTANCE_NAME": "central"}, clear=False)
    @patch.object(cleanup.Config, "EVOLUTION_API_URL", "https://evolution.test")
    @patch.object(cleanup.Config, "EVOLUTION_API_KEY", "key")
    @patch("services.evolution_instance_cleanup.requests.delete")
    @patch("services.evolution_instance_cleanup.requests.get")
    def test_cleanup_deletes_only_disconnected_and_preserves_open(self, get_mock, delete_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [
            {"name": "central", "connectionStatus": "close"},
            {"name": "open-client", "connectionStatus": "open", "disconnectionReasonCode": 401},
            {"name": "closed-client", "connectionStatus": "close"},
        ]
        get_mock.return_value = response
        delete_response = Mock(status_code=200)
        delete_mock.return_value = delete_response

        result = cleanup.cleanup_orphan_instances()

        self.assertEqual(result["scanned"], 3)
        self.assertEqual(result["candidates"], 1)
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(delete_mock.call_count, 1)
        self.assertIn("closed-client", delete_mock.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
