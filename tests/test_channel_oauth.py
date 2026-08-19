import os
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from services import channel_oauth_service as oauth
from services.secret_store import decrypt_secret


class FakeSnapshot:
    def __init__(self, data=None, exists=True):
        self.data = dict(data or {})
        self.exists = exists

    def to_dict(self):
        return dict(self.data)


class FakeDocument:
    def __init__(self, collection, key):
        self.collection = collection
        self.key = key

    def get(self):
        return self.collection.get(self.key, FakeSnapshot(exists=False))

    def set(self, value, merge=False):
        current = self.collection.get(self.key, FakeSnapshot()).data if merge else {}
        current.update(value)
        self.collection[self.key] = FakeSnapshot(current)


class FakeCollection(dict):
    def document(self, key):
        return FakeDocument(self, key)


class FakeDb:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


class ChannelOAuthTests(unittest.TestCase):
    def setUp(self):
        self.previous = {key: os.environ.get(key) for key in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI", "PLATFORM_SECRET_KEY")}
        os.environ["PLATFORM_SECRET_KEY"] = "oauth-test-platform-secret"
        os.environ["TIKTOK_CLIENT_KEY"] = "tiktok-client"
        os.environ["TIKTOK_CLIENT_SECRET"] = "tiktok-secret"
        os.environ["TIKTOK_REDIRECT_URI"] = "https://negobot-api.duckdns.org/api/platform/client/channels/tiktok/callback"
        self.db = FakeDb()
        self.db.collection("tenants").document("tenant-a").set({"tenant_id": "tenant-a", "channels": {}})

    def tearDown(self):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_start_oauth_keeps_state_short_lived_and_tenant_scoped(self):
        result = oauth.start_oauth(self.db, "tiktok", "tenant-a", "user-a")
        query = parse_qs(urlparse(result["authorize_url"]).query)
        state = query["state"][0]
        stored = self.db.collection("oauth_states")[oauth._state_id(state)].data
        self.assertEqual(result["status"], "pending_authorization")
        self.assertEqual(stored["tenant_id"], "tenant-a")
        self.assertEqual(stored["platform_user_id"], "user-a")
        self.assertEqual(stored["status"], "pending")
        self.assertNotIn("tiktok-secret", result["authorize_url"])

    @patch("services.channel_oauth_service.requests.get")
    @patch("services.channel_oauth_service.requests.post")
    def test_complete_oauth_encrypts_tokens_and_writes_only_current_tenant(self, post, get):
        started = oauth.start_oauth(self.db, "tiktok", "tenant-a", "user-a")
        state = parse_qs(urlparse(started["authorize_url"]).query)["state"][0]
        token_response = Mock()
        token_response.json.return_value = {"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_in": 3600, "scope": "user.info.basic"}
        token_response.raise_for_status.return_value = None
        post.return_value = token_response
        profile_response = Mock()
        profile_response.json.return_value = {"data": {"open_id": "tt-user-1", "display_name": "Customer TikTok"}}
        profile_response.raise_for_status.return_value = None
        get.return_value = profile_response

        result = oauth.complete_oauth(self.db, "tiktok", "auth-code", state)
        stored = self.db.collection("tenants")["tenant-a"].data["channels"]["tiktok"]
        self.assertTrue(result["connected"])
        self.assertEqual(result["tenant_id"], "tenant-a")
        self.assertEqual(stored["external_account_id"], "tt-user-1")
        self.assertEqual(decrypt_secret(stored["access_token_ciphertext"]), "access-secret")
        self.assertEqual(decrypt_secret(stored["refresh_token_ciphertext"]), "refresh-secret")
        self.assertNotIn("access-secret", stored["access_token_ciphertext"])
        self.assertEqual(self.db.collection("oauth_states")[oauth._state_id(state)].data["status"], "consumed")

    def test_callback_channel_mismatch_is_rejected_before_provider_call(self):
        started = oauth.start_oauth(self.db, "tiktok", "tenant-a", "user-a")
        state = parse_qs(urlparse(started["authorize_url"]).query)["state"][0]
        with patch("services.channel_oauth_service.requests.post") as post:
            with self.assertRaises(ValueError):
                oauth.complete_oauth(self.db, "instagram", "auth-code", state)
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
