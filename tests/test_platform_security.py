import os
import sys
import types
import unittest
from dataclasses import dataclass
from unittest.mock import patch

sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))
dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", dotenv_stub)
os.environ.setdefault("PLATFORM_SECRET_KEY", "platform-test-secret")
os.environ.setdefault("ADMIN_TOKEN", "admin-test-token")

import extensions
extensions.init_extensions = lambda _app: None
from app import app
import routes.platform_routes as platform_routes


@dataclass
class FakeSnapshot:
    id: str
    data: dict
    exists: bool = True

    def to_dict(self):
        return dict(self.data)

    @property
    def reference(self):
        return self

    def get(self):
        return self

    def set(self, values, merge=False):
        if merge:
            self.data.update(values)
        else:
            self.data = dict(values)
        self.exists = True


class FakeCollection:
    def __init__(self, db, name, filters=None):
        self.db = db
        self.name = name
        self.filters = filters or []

    def where(self, field, _operator, value):
        return FakeCollection(self.db, self.name, self.filters + [(field, value)])

    def limit(self, _amount):
        return self

    def stream(self):
        rows = list(self.db.collections.get(self.name, {}).values())
        for field, expected in self.filters:
            rows = [row for row in rows if row.data.get(field) == expected]
        return rows

    def document(self, document_id):
        collection = self.db.collections.setdefault(self.name, {})
        if document_id not in collection:
            collection[document_id] = FakeSnapshot(document_id, {}, exists=False)
        return collection[document_id]

    def add(self, values):
        document_id = f"generated-{len(self.db.collections.setdefault(self.name, {})) + 1}"
        document = FakeSnapshot(document_id, dict(values))
        self.db.collections[self.name][document_id] = document
        return document, document


class FakeDB:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return FakeCollection(self, name)


def set_identity(client, identity):
    with client.session_transaction() as session:
        session["platform_identity"] = identity


class PlatformSecurityTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="platform-test-secret")
        self.db = FakeDB()
        extensions.db = self.db
        platform_routes._LOGIN_ATTEMPTS.clear()
        self.client = app.test_client()

    def test_client_cannot_open_admin_endpoints(self):
        set_identity(self.client, {"id": "user-a", "name": "Cliente A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.get("/api/platform/admin/overview")
        self.assertEqual(response.status_code, 403)

    def test_team_list_filters_by_current_tenant(self):
        self.db.collections["platform_users"] = {
            "user-a": FakeSnapshot("user-a", {"name": "A", "email": "a@example.com", "role": "client", "tenant_role": "owner", "tenant_id": "tenant-a", "status": "active"}),
            "user-b": FakeSnapshot("user-b", {"name": "B", "email": "b@example.com", "role": "operator", "tenant_role": "operator", "tenant_id": "tenant-b", "status": "active"}),
        }
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.get("/api/platform/client/team")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.get_json()["users"]], ["user-a"])

    def test_owner_can_create_operator_inside_same_tenant(self):
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.post("/api/platform/client/team", json={"name": "Operador", "email": "operator@example.com", "password": "password-123"})
        self.assertEqual(response.status_code, 201)
        stored = self.db.collections["platform_users"]
        created = next(value.data for value in stored.values() if value.data.get("email") == "operator@example.com")
        self.assertEqual(created["tenant_id"], "tenant-a")
        self.assertEqual(created["role"], "operator")

    def test_operator_cannot_create_another_operator(self):
        set_identity(self.client, {"id": "user-op", "name": "Op", "role": "operator", "tenant_id": "tenant-a", "tenant_role": "operator"})
        response = self.client.post("/api/platform/client/team", json={"name": "Outro", "email": "other@example.com", "password": "password-123"})
        self.assertEqual(response.status_code, 403)

    def test_owner_cannot_update_user_from_other_tenant(self):
        self.db.collections["platform_users"] = {
            "user-b": FakeSnapshot("user-b", {"name": "B", "email": "b@example.com", "role": "operator", "tenant_role": "operator", "tenant_id": "tenant-b", "status": "active"}),
        }
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.patch("/api/platform/client/team/user-b", json={"status": "suspended"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.collections["platform_users"]["user-b"].data["status"], "active")

    def test_contact_search_is_scoped_to_tenant(self):
        self.db.collections["contacts"] = {
            "contact-a": FakeSnapshot("contact-a", {"tenant_id": "tenant-a", "name": "Ana", "phone": "258841111111", "tags": ["vip"], "opt_in": True}),
            "contact-b": FakeSnapshot("contact-b", {"tenant_id": "tenant-b", "name": "Ana", "phone": "258842222222", "tags": ["vip"], "opt_in": True}),
        }
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.get("/api/platform/client/contacts?search=ana")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.get_json()["contacts"]], ["contact-a"])

    def test_contact_update_and_archive_remain_in_tenant(self):
        self.db.collections["contacts"] = {
            "contact-a": FakeSnapshot("contact-a", {"tenant_id": "tenant-a", "name": "Ana", "phone": "258841111111", "tags": [], "opt_in": True}),
            "contact-b": FakeSnapshot("contact-b", {"tenant_id": "tenant-b", "name": "Bruno", "phone": "258842222222", "tags": [], "opt_in": True}),
        }
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        update = self.client.patch("/api/platform/client/contacts/contact-a", json={"tags": ["VIP", "cliente"], "opt_in": False})
        self.assertEqual(update.status_code, 200)
        self.assertEqual(self.db.collections["contacts"]["contact-a"].data["tags"], ["cliente", "vip"])
        archive = self.client.delete("/api/platform/client/contacts/contact-a")
        self.assertEqual(archive.status_code, 200)
        self.assertEqual(self.db.collections["contacts"]["contact-a"].data["status"], "archived")
        cross_tenant = self.client.patch("/api/platform/client/contacts/contact-b", json={"opt_in": False})
        self.assertEqual(cross_tenant.status_code, 404)
        self.assertTrue(self.db.collections["contacts"]["contact-b"].data["opt_in"])

    def test_login_rate_limit_applies_before_credential_lookup(self):
        for _ in range(8):
            response = self.client.post("/api/platform/auth/login", json={"identifier": "admin", "password": "wrong-password"})
            self.assertEqual(response.status_code, 401)
        response = self.client.post("/api/platform/auth/login", json={"identifier": "admin", "password": "wrong-password"})
        self.assertEqual(response.status_code, 429)

    def test_cross_origin_mutation_is_rejected(self):
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.post("/api/platform/client/team", headers={"Origin": "https://evil.example"}, json={"name": "Operador", "email": "evil@example.com", "password": "password-123"})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
