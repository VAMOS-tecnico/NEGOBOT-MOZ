import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import video_service
import video_worker


class FakeRedis:
    def __init__(self, hashes=None):
        self.hashes = hashes or {}

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def hset(self, key, mapping=None, **kwargs):
        values = mapping or kwargs
        self.hashes.setdefault(key, {}).update({key: str(value) for key, value in values.items()})

    def scan_iter(self, match=None):
        return iter(self.hashes.keys())


class VideoLifecycleTests(unittest.TestCase):
    def test_download_stream_deletes_only_after_complete_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "job.mp4"
            output.write_bytes(b"video-data-123")
            redis_client = FakeRedis({
                "negobot:video:job:job-a": {
                    "payload": '{"id":"job-a","tenant_id":"tenant-a","title":"Oferta Agosto"}',
                    "status": "completed",
                    "progress": "100",
                    "output_path": str(output),
                }
            })
            async def consume(iterator):
                chunks = []
                async for chunk in iterator:
                    chunks.append(chunk)
                return b"".join(chunks)
            with patch.object(video_service, "OUTPUT_DIR", root), patch.object(video_service, "queue_client", return_value=redis_client):
                response = video_service.download_job("job-a", "tenant-a")
                body = asyncio.run(consume(response.body_iterator))
            self.assertEqual(body, b"video-data-123")
            self.assertFalse(output.exists())
            self.assertEqual(redis_client.hashes["negobot:video:job:job-a"]["status"], "deleted")
            self.assertEqual(redis_client.hashes["negobot:video:job:job-a"]["deletion_reason"], "download_completed")

    def test_job_state_never_exposes_server_path(self):
        redis_client = FakeRedis({
            "negobot:video:job:job-a": {
                "payload": '{"id":"job-a","tenant_id":"tenant-a","title":"Oferta"}',
                "status": "completed",
                "progress": "100",
                "output_path": "/var/lib/negobot/videos/job-a.mp4",
            }
        })
        with patch.object(video_service, "OUTPUT_DIR", Path("/var/lib/negobot/videos")), patch.object(video_service, "queue_client", return_value=redis_client):
            result = video_service.get_job("job-a", "tenant-a")
        self.assertNotIn("output_path", result["job"])
        self.assertFalse(result["job"]["output_available"])

    def test_preview_keeps_file_and_returns_inline_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "job.mp4"
            output.write_bytes(b"preview-data")
            redis_client = FakeRedis({
                "negobot:video:job:job-preview": {
                    "payload": '{"id":"job-preview","tenant_id":"tenant-a","title":"Oferta Preview"}',
                    "status": "completed",
                    "progress": "100",
                    "output_path": str(output),
                }
            })
            with patch.object(video_service, "OUTPUT_DIR", root), patch.object(video_service, "queue_client", return_value=redis_client):
                response = video_service.preview_job("job-preview", "tenant-a")
            self.assertEqual(response.media_type, "video/mp4")
            self.assertIn("inline", response.headers.get("content-disposition", ""))
            self.assertTrue(output.exists())

    def test_wrong_tenant_cannot_preview(self):
        redis_client = FakeRedis({
            "negobot:video:job:job-preview": {
                "payload": '{"id":"job-preview","tenant_id":"tenant-a","title":"Oferta"}',
                "status": "completed",
                "progress": "100",
                "output_path": "/var/lib/negobot/videos/job-preview.mp4",
            }
        })
        with patch.object(video_service, "queue_client", return_value=redis_client):
            with self.assertRaises(Exception) as raised:
                video_service.preview_job("job-preview", "tenant-b")
        self.assertEqual(getattr(raised.exception, "status_code", None), 404)

    def test_wrong_tenant_cannot_download(self):
        redis_client = FakeRedis({
            "negobot:video:job:job-a": {
                "payload": '{"id":"job-a","tenant_id":"tenant-a","title":"Oferta"}',
                "status": "completed",
                "progress": "100",
                "output_path": "/var/lib/negobot/videos/job-a.mp4",
            }
        })
        with patch.object(video_service, "queue_client", return_value=redis_client):
            with self.assertRaises(Exception) as raised:
                video_service.download_job("job-a", "tenant-b")
        self.assertEqual(getattr(raised.exception, "status_code", None), 404)

    def test_output_path_cannot_escape_video_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(video_service, "OUTPUT_DIR", root):
                self.assertIsNone(video_service._safe_output_path(str(root.parent / "outside.mp4")))
                self.assertIsNone(video_service._safe_output_path(str(root / "nested" / ".." / ".." / "outside.mp4")))

    def test_retention_removes_old_completed_output_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_file = root / "old.mp4"
            fresh_file = root / "fresh.mp4"
            old_file.write_bytes(b"old")
            fresh_file.write_bytes(b"fresh")
            now = 2_000_000_000.0
            os.utime(old_file, (now - 8 * 86400, now - 8 * 86400))
            os.utime(fresh_file, (now - 2 * 86400, now - 2 * 86400))
            redis_client = FakeRedis({
                "negobot:video:job:old": {"status": "completed", "output_path": str(old_file), "updated_at": "invalid"},
                "negobot:video:job:fresh": {"status": "completed", "output_path": str(fresh_file), "updated_at": "invalid"},
                "negobot:video:job:processing": {"status": "processing", "output_path": str(old_file), "updated_at": "invalid"},
            })
            with patch.object(video_worker, "OUTPUT_DIR", str(root)), patch.object(video_worker, "RETENTION_DAYS", 7), patch.object(video_worker.time, "time", return_value=now):
                removed = video_worker.cleanup_expired_outputs(redis_client)
            self.assertEqual(removed, 1)
            self.assertFalse(old_file.exists())
            self.assertTrue(fresh_file.exists())
            self.assertEqual(redis_client.hashes["negobot:video:job:old"]["status"], "deleted")
            self.assertEqual(redis_client.hashes["negobot:video:job:processing"]["status"], "processing")


if __name__ == "__main__":
    unittest.main()
