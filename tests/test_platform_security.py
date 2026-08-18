import hashlib
import hmac
import json
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

    def document(self, document_id=None):
        collection = self.db.collections.setdefault(self.name, {})
        if document_id is None:
            document_id = f"generated-{len(collection) + 1}"
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

    def test_lemonsqueezy_webhook_rejects_invalid_signature(self):
        os.environ["LEMONSQUEEZY_WEBHOOK_SECRET"] = "lemon-test-secret"
        response = self.client.post("/api/platform/webhooks/lemonsqueezy", data=b"{}", content_type="application/json", headers={"X-Signature": "invalid"})
        self.assertEqual(response.status_code, 401)

    def test_lemonsqueezy_webhook_activates_tenant_idempotently(self):
        os.environ["LEMONSQUEEZY_WEBHOOK_SECRET"] = "lemon-test-secret"
        os.environ["LEMONSQUEEZY_VARIANT_PREMIUM"] = "333"
        self.db.collections["payment_intents"] = {
            "intent-1": FakeSnapshot("intent-1", {"tenant_id": "tenant-a", "plan_id": "premium", "status": "pending"})
        }
        payload = {
            "meta": {"event_name": "subscription_payment_success", "custom_data": {"tenant_id": "tenant-a", "payment_intent_id": "intent-1", "plan_id": "premium"}},
            "data": {"type": "subscriptions", "id": "sub-1", "attributes": {"variant_id": 333, "status": "active", "renews_at": "2026-09-17T00:00:00Z"}},
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"lemon-test-secret", raw, hashlib.sha256).hexdigest()
        response = self.client.post("/api/platform/webhooks/lemonsqueezy", data=raw, content_type="application/json", headers={"X-Signature": signature})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "confirmed")
        self.assertEqual(self.db.collections["payment_intents"]["intent-1"].data["status"], "confirmed")
        self.assertEqual(self.db.collections["tenants"]["tenant-a"].data["plan"], "premium")
        duplicate = self.client.post("/api/platform/webhooks/lemonsqueezy", data=raw, content_type="application/json", headers={"X-Signature": signature})
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.get_json()["duplicate"])

    def test_public_plan_question_returns_deterministic_table(self):
        response = self.client.post("/api/platform/public/assistant/chat", json={"message": "Quais são os preços e benefícios dos planos?", "source": "platform"})
        self.assertEqual(response.status_code, 200)
        answer = response.get_json()["answer"]
        self.assertIn("Básico — 500 MT/mês", answer)
        self.assertIn("Médio — 1.000 MT/mês", answer)
        self.assertIn("Premium — 1.500 MT/mês", answer)
        self.assertIn("855000929", answer)

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

    def test_campaign_templates_are_tenant_scoped(self):
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        created = self.client.post("/api/platform/client/templates", json={"name": "Boas-vindas", "body": "Olá {nome}, bem-vindo."})
        self.assertEqual(created.status_code, 201)
        template_id = created.get_json()["template"]["id"]
        listed = self.client.get("/api/platform/client/templates")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([item["id"] for item in listed.get_json()["templates"]], [template_id])
        cross_tenant = self.client.patch(f"/api/platform/client/templates/{template_id}", json={"status": "archived"})
        self.assertEqual(cross_tenant.status_code, 200)
        self.db.collections["campaign_templates"][template_id].data["tenant_id"] = "tenant-b"
        cross_tenant_update = self.client.patch(f"/api/platform/client/templates/{template_id}", json={"status": "active"})
        self.assertEqual(cross_tenant_update.status_code, 404)

    def test_payment_history_is_tenant_scoped(self):
        self.db.collections["payment_intents"] = {
            "payment-a": FakeSnapshot("payment-a", {"tenant_id": "tenant-a", "transaction_id": "TXA123", "status": "pending", "client_phone": "258841111111"}),
            "payment-b": FakeSnapshot("payment-b", {"tenant_id": "tenant-b", "transaction_id": "TXB456", "status": "confirmed", "client_phone": "258842222222"}),
        }
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.get("/api/platform/client/payments/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.get_json()["payments"]], ["payment-a"])

    def test_public_registration_creates_isolated_pending_trial_and_session(self):
        response = self.client.post("/api/platform/auth/register", json={"name": "Loja Maputo", "email": "novo@example.com", "password": "password-123", "billing_region": "international", "plan_id": "premium"})
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["authenticated"])
        tenant_id = payload["tenant"]["id"]
        tenant = self.db.collections["tenants"][tenant_id].data
        self.assertEqual(tenant["trial_status"], "trial_pending_connection")
        self.assertEqual(tenant["billing_region"], "international")
        self.assertEqual(tenant["selected_plan"], "premium")
        self.assertEqual(self.db.collections["platform_users"][platform_routes._doc_id("novo@example.com")].data["tenant_id"], tenant_id)
        with self.client.session_transaction() as session:
            self.assertEqual(session["platform_identity"]["tenant_id"], tenant_id)

    def test_public_registration_rejects_duplicate_email(self):
        email = "duplicate@example.com"
        self.db.collections["platform_users"] = {platform_routes._doc_id(email): FakeSnapshot(platform_routes._doc_id(email), {"email": email})}
        response = self.client.post("/api/platform/auth/register", json={"name": "Duplicado", "email": email, "password": "password-123", "billing_region": "mozambique"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("Já existe", response.get_json()["error"])

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

    def test_support_ticket_is_scoped_to_tenant(self):
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        created = self.client.post("/api/platform/client/support/tickets", json={"subject": "Falha no QR Code", "message": "O QR Code não aparece depois do pagamento.", "priority": "high"})
        self.assertEqual(created.status_code, 201)
        ticket_id = created.get_json()["ticket"]["id"]
        self.assertEqual(self.client.get("/api/platform/client/support/tickets").get_json()["tickets"][0]["tenant_id"], "tenant-a")
        self.db.collections["support_tickets"][ticket_id].data["tenant_id"] = "tenant-b"
        cross_tenant = self.client.patch(f"/api/platform/client/support/tickets/{ticket_id}", json={"status": "closed"})
        self.assertEqual(cross_tenant.status_code, 404)

    def test_admin_metrics_returns_global_counts_only_for_admin(self):
        self.db.collections["tenants"] = {"tenant-a": FakeSnapshot("tenant-a", {"status": "active"}), "tenant-b": FakeSnapshot("tenant-b", {"status": "suspended"})}
        self.db.collections["platform_users"] = {"user-a": FakeSnapshot("user-a", {"status": "active"})}
        self.db.collections["support_tickets"] = {"ticket-a": FakeSnapshot("ticket-a", {"status": "open"})}
        set_identity(self.client, {"id": "owner", "name": "Owner", "role": "owner", "tenant_id": None})
        response = self.client.get("/api/platform/admin/metrics")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["tenants"]["total"], 2)
        self.assertEqual(payload["support"]["open"], 1)


if __name__ == "__main__":
    unittest.main()
