import io
import os
import unittest
from unittest.mock import patch

import extensions
from routes import platform_routes
from tests.test_assistant_knowledge import FakeDB, set_identity
from app import app


class VideoAssetRouteTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="platform-test-secret")
        self.db = FakeDB()
        extensions.db = self.db
        self.client = app.test_client()
        set_identity(self.client, "tenant-video-a")

    def test_upload_returns_opaque_asset_metadata_without_bytes_in_firestore(self):
        with patch.dict(os.environ, {"VIDEO_ASSET_BASE_URL": "https://app.example"}, clear=False), patch.object(platform_routes, "store_blob", return_value="local:video-assets/tenant-video-a/asset-a/clip.mp4"):
            response = self.client.post(
                "/api/platform/client/videos/assets",
                data={"file": (io.BytesIO(b"fake-video"), "clip.mp4")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 201)
        asset = response.get_json()["asset"]
        self.assertEqual(asset["kind"], "video")
        self.assertTrue(asset["asset_url"].startswith("https://app.example/api/platform/client/videos/assets/"))
        stored = next(iter(self.db.collections["video_assets"].values())).data
        self.assertEqual(stored["tenant_id"], "tenant-video-a")
        self.assertNotIn("fake-video", repr(stored))

    def test_recorded_webm_is_stored_as_audio_asset(self):
        with patch.dict(os.environ, {"VIDEO_ASSET_BASE_URL": "https://app.example"}, clear=False), patch.object(platform_routes, "store_blob", return_value="local:video-assets/tenant-video-a/asset-b/voice.webm"):
            response = self.client.post(
                "/api/platform/client/videos/assets",
                data={"file": (io.BytesIO(b"fake-audio"), "voice.webm", "audio/webm")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 201)
        asset = response.get_json()["asset"]
        self.assertEqual(asset["kind"], "audio")
        self.assertEqual(asset["mime_type"], "audio/webm")

    def test_internal_stream_requires_service_token_and_matching_tenant(self):
        collection = self.db.collection("video_assets")
        collection.document("asset-a").set({"tenant_id": "tenant-video-a", "file_name": "clip.mp4", "mime_type": "video/mp4", "storage_key": "local:clip"})
        with patch.dict(os.environ, {"VIDEO_SERVICE_TOKEN": "service-secret"}, clear=False), patch.object(platform_routes, "read_blob", return_value=b"video-data"):
            response = self.client.get("/api/platform/client/videos/assets/asset-a", headers={"X-Video-Service-Token": "service-secret", "X-Video-Tenant-Id": "tenant-video-a"})
            wrong_tenant = self.client.get("/api/platform/client/videos/assets/asset-a", headers={"X-Video-Service-Token": "service-secret", "X-Video-Tenant-Id": "tenant-video-b"})
            no_token = self.client.get("/api/platform/client/videos/assets/asset-a")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"video-data")
        self.assertEqual(response.mimetype, "video/mp4")
        self.assertEqual(wrong_tenant.status_code, 404)
        self.assertEqual(no_token.status_code, 404)

    def test_other_tenant_cannot_delete_video_asset(self):
        collection = self.db.collection("video_assets")
        collection.document("asset-b").set({"tenant_id": "tenant-video-b", "file_name": "other.mp4", "storage_key": "local:other"})
        response = self.client.delete("/api/platform/client/videos/assets/asset-b")
        self.assertEqual(response.status_code, 404)
        self.assertIn("asset-b", collection.documents)


if __name__ == "__main__":
    unittest.main()
