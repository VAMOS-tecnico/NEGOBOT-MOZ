import json
import unittest

from services.job_runtime import JobContractError, JobManualReview, process_once, validate_job


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.expirations = {}
        self.values = {}

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)

    def expire(self, key, seconds):
        self.expirations[key] = seconds

    def setex(self, key, seconds, value):
        self.values[key] = value
        self.expirations[key] = seconds


class JobRuntimeTests(unittest.TestCase):
    def test_validate_job_requires_tenant_scoped_identity(self):
        with self.assertRaises(JobContractError):
            validate_job({"job_id": "job-1", "kind": "ai"})

    def test_process_once_is_idempotent(self):
        client = FakeRedis()
        calls = []

        def handler(job):
            calls.append(job["tenant_id"])
            return {"provider": "test"}

        job = {"job_id": "job-1", "tenant_id": "tenant-a", "kind": "ai", "payload": {"text": "Olá"}}
        first = process_once(client, "ai", json.dumps(job), handler)
        second = process_once(client, "ai", job, handler)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(calls, ["tenant-a"])
        self.assertEqual(client.hashes["negobot:job:ai:job-1"]["tenant_id"], "tenant-a")

    def test_manual_review_does_not_claim_external_publication(self):
        client = FakeRedis()

        def handler(_job):
            raise JobManualReview("adapter_pending")

        result = process_once(client, "social", {"job_id": "job-2", "tenant_id": "tenant-b", "kind": "post"}, handler)
        self.assertEqual(result["status"], "manual_review")
        self.assertEqual(client.hashes["negobot:job:social:job-2"]["status"], "manual_review")


if __name__ == "__main__":
    unittest.main()
