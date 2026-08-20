import hashlib
import hmac
import json
import os
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))
dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", dotenv_stub)
os.environ.setdefault("PLATFORM_SECRET_KEY", "platform-test-secret")
os.environ.setdefault("ADMIN_TOKEN", "admin-test-token")
os.environ.setdefault("TELEGRAM_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

import extensions
extensions.init_extensions = lambda _app: None
from app import app
import routes.platform_routes as platform_routes
from services.password_reset_service import consume_password_reset, request_password_reset, token_digest


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

    @patch("routes.platform_routes.get_me")
    @patch("routes.platform_routes.set_webhook")
    @patch("routes.platform_routes.get_webhook_info")
    def test_owner_can_connect_telegram_without_exposing_token(self, mock_info, mock_set, mock_me):
        self.db.collections["tenants"] = {"tenant-a": FakeSnapshot("tenant-a", {"tenant_id": "tenant-a", "channels": {}})}
        mock_me.return_value = {"id": 123, "username": "cliente_bot", "first_name": "Cliente"}
        mock_info.return_value = {"url": "https://negobot-api.duckdns.org/api/omnichannel/telegram/tenant-a", "pending_update_count": 0}
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.post("/api/platform/client/channels/telegram/connect", json={"bot_token": "123:SECRET"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("123:SECRET", response.get_data(as_text=True))
        stored = self.db.collections["tenants"]["tenant-a"].data["channels"]["telegram"]
        self.assertEqual(stored["status"], "connected")
        self.assertTrue(stored["token_ciphertext"].startswith("gAAAA"))
        self.assertTrue(stored["webhook_secret_ciphertext"].startswith("gAAAA"))
        self.assertNotIn("123:SECRET", stored["token_ciphertext"])
        mock_set.assert_called_once()

    @patch("routes.platform_routes.get_me")
    @patch("routes.platform_routes.set_webhook")
    @patch("routes.platform_routes.get_webhook_info")
    def test_first_telegram_connection_claims_central_trial(self, mock_info, mock_set, mock_me):
        self.db.collections["tenants"] = {"tenant-a": FakeSnapshot("tenant-a", {"tenant_id": "tenant-a", "account_email": "a@example.com", "central_account_id": "ca_a", "channels": {}})}
        mock_me.return_value = {"id": 321, "username": "primeiro_bot", "first_name": "Primeiro"}
        mock_info.return_value = {"url": "https://negobot-api.duckdns.org/api/omnichannel/telegram/tenant-a", "pending_update_count": 0}
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.post("/api/platform/client/channels/telegram/connect", json={"bot_token": "321:SECRET"})
        self.assertEqual(response.status_code, 200)
        registry = self.db.collections["central_trial_registry"]["ca_a"].data
        self.assertEqual(registry["started_channel"], "telegram")
        self.assertTrue(registry["trial_consumed"])
        self.assertEqual(self.db.collections["tenants"]["tenant-a"].data["trial_access_level"], "premium")

    def test_telegram_cipher_falls_back_to_existing_platform_key(self):
        from services.secret_store import decrypt_secret, encrypt_secret
        original = os.environ.pop("TELEGRAM_TOKEN_ENCRYPTION_KEY", None)
        try:
            encrypted = encrypt_secret("telegram-secret")
            self.assertNotEqual(encrypted, "telegram-secret")
            self.assertEqual(decrypt_secret(encrypted), "telegram-secret")
        finally:
            if original is not None:
                os.environ["TELEGRAM_TOKEN_ENCRYPTION_KEY"] = original

    def test_telegram_status_does_not_return_secrets(self):
        self.db.collections["tenants"] = {"tenant-a": FakeSnapshot("tenant-a", {"tenant_id": "tenant-a", "channels": {"telegram": {"status": "connected", "token_ciphertext": "gAAAA-secret", "webhook_secret_ciphertext": "gAAAA-webhook", "bot_username": "cliente_bot"}}})}
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.get("/api/platform/client/channels/telegram")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["has_token"])
        self.assertNotIn("token_ciphertext", body)
        self.assertNotIn("webhook_secret_ciphertext", body)

    def test_admin_session_cannot_open_client_channels_without_tenant(self):
        set_identity(self.client, {"id": "platform-owner", "name": "Administrador", "role": "owner", "tenant_id": None})
        response = self.client.get("/api/platform/client/channels")
        self.assertEqual(response.status_code, 403)

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

    def test_public_registration_accepts_minimal_payload_for_all_clients(self):
        response = self.client.post("/api/platform/auth/register", json={"email": "minimal@example.com", "password": "password-123"})
        self.assertEqual(response.status_code, 201)
        tenant_id = response.get_json()["tenant"]["id"]
        tenant = self.db.collections["tenants"][tenant_id].data
        self.assertEqual(tenant["trial_status"], "trial_pending_connection")
        self.assertFalse(tenant["profile_completed"])
        self.assertEqual(tenant["onboarding_status"], "incomplete")
        self.assertIsNone(tenant["selected_plan"])
        self.assertEqual(tenant["billing_region"], "mozambique")
        self.assertEqual(tenant["name"], "minimal")

    def test_public_registration_rejects_duplicate_email(self):
        email = "duplicate@example.com"
        self.db.collections["platform_users"] = {platform_routes._doc_id(email): FakeSnapshot(platform_routes._doc_id(email), {"email": email})}
        response = self.client.post("/api/platform/auth/register", json={"name": "Duplicado", "email": email, "password": "password-123", "billing_region": "mozambique"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("Já existe", response.get_json()["error"])

    def test_public_registration_rejects_email_with_case_or_whitespace_bypass(self):
        email = "CaseUser@example.com"
        canonical_id = platform_routes._doc_id(email)
        self.db.collections["platform_users"] = {
            canonical_id: FakeSnapshot(canonical_id, {"email": "caseuser@example.com", "status": "active"})
        }
        response = self.client.post(
            "/api/platform/auth/register",
            json={"name": "Duplicado", "email": "  caseuser@EXAMPLE.com  ", "password": "password-123"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Já existe", response.get_json()["error"])

    def test_public_registration_rejects_reserved_central_identity_without_user_document(self):
        email = "reserved@example.com"
        central_account_id = f"ca_{platform_routes._doc_id(email)[:24]}"
        self.db.collections["central_trial_registry"] = {
            central_account_id: FakeSnapshot(central_account_id, {"account_email": email, "trial_consumed": True})
        }
        response = self.client.post(
            "/api/platform/auth/register",
            json={"name": "Reservado", "email": email, "password": "password-123"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Já existe", response.get_json()["error"])
        self.assertFalse(any(snapshot.exists for snapshot in self.db.collections.get("tenants", {}).values()))

    def test_password_reset_token_is_single_use_and_changes_password(self):
        email = "reset@example.com"
        user_id = platform_routes._doc_id(email)
        self.db.collections["platform_users"] = {
            user_id: FakeSnapshot(user_id, {"email": email, "status": "active", "password_hash": "old-hash"})
        }
        with patch("services.password_reset_service.enqueue_email") as enqueue_email:
            self.assertTrue(request_password_reset(self.db, email, "https://app-negobotmoz.duckdns.org/plataforma"))
            payload = enqueue_email.call_args.kwargs
            reset_url = next(line for line in payload["body"].splitlines() if "/reset-password?token=" in line)
            self.assertEqual(payload["tenant_id"], f"user:{user_id}")
            self.assertEqual(payload["recipient"], email)
            self.assertEqual(payload["request_id"].split(":", 1)[0], "password-reset")
        token = parse_qs(urlparse(reset_url).query)["token"][0]
        self.assertTrue(self.db.collections["password_resets"][token_digest(token)].exists)
        self.assertTrue(consume_password_reset(self.db, token, "new-password-123"))
        self.assertFalse(consume_password_reset(self.db, token, "another-password-123"))
        self.assertNotEqual(self.db.collections["platform_users"][user_id].data["password_hash"], "old-hash")
        self.assertIsNotNone(self.db.collections["password_resets"][token_digest(token)].data["used_at"])

    def test_password_reset_rejects_expired_token(self):
        email = "expired@example.com"
        user_id = platform_routes._doc_id(email)
        token = "expired-token"
        self.db.collections["platform_users"] = {user_id: FakeSnapshot(user_id, {"email": email, "status": "active", "password_hash": "old-hash"})}
        self.db.collections["password_resets"] = {
            token_digest(token): FakeSnapshot(token_digest(token), {"user_id": user_id, "email": email, "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1), "used_at": None})
        }
        self.assertFalse(consume_password_reset(self.db, token, "new-password-123"))
        self.assertEqual(self.db.collections["platform_users"][user_id].data["password_hash"], "old-hash")

    def test_forgot_password_response_does_not_reveal_account_existence(self):
        known = self.client.post("/api/platform/auth/forgot-password", json={"email": "known@example.com"})
        unknown = self.client.post("/api/platform/auth/forgot-password", json={"email": "unknown@example.com"})
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.get_json(), unknown.get_json())

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


    def test_client_channel_catalog_is_tenant_scoped_and_explicit_about_restrictions(self):
        self.db.collections["tenants"] = {
            "tenant-a": FakeSnapshot("tenant-a", {"evolution_state": "open", "channels": {"telegram": {"status": "connected"}}}),
            "tenant-b": FakeSnapshot("tenant-b", {"evolution_state": "open", "channels": {"instagram": {"status": "connected"}}}),
        }
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        response = self.client.get("/api/platform/client/channels")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["tenant_id"], "tenant-a")
        channels = {item["key"]: item for item in payload["channels"]}
        self.assertEqual(channels["whatsapp"]["status"], "connected")
        self.assertEqual(channels["telegram"]["status"], "connected")
        self.assertEqual(channels["linkedin"]["status"], "pending_review")
        self.assertNotIn("tenant-b", json.dumps(payload))

    @patch("routes.omnichannel_routes.enqueue_omnichannel_event")
    def test_telegram_webhook_validates_secret_and_queues_normalized_event(self, enqueue):
        os.environ["TELEGRAM_WEBHOOK_SECRET"] = "telegram-test-secret"
        self.db.collections["tenants"] = {"tenant-a": FakeSnapshot("tenant-a", {"channels": {}})}
        enqueue.return_value = {"queued": True, "event_id": "event-a", "queue": "omnichannel_incoming_queue", "position": 1}
        payload = {"update_id": 10, "message": {"message_id": 7, "chat": {"id": 99}, "from": {"id": 88}, "text": "Olá"}}
        response = self.client.post("/api/omnichannel/telegram/tenant-a", json=payload, headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-test-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["accepted"])
        queued = enqueue.call_args.args[0]
        self.assertEqual(queued["tenant_id"], "tenant-a")
        self.assertEqual(queued["channel"], "telegram")
        self.assertEqual(queued["text"], "Olá")
        events = self.db.collections["omnichannel_events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(next(iter(events.values())).data["status"], "queued")
        self.assertEqual(self.db.collections["tenants"]["tenant-a"].data["channels"]["telegram"]["status"], "connected")

    def test_omnichannel_webhook_rejects_unknown_tenant(self):
        os.environ["TELEGRAM_WEBHOOK_SECRET"] = "telegram-test-secret"
        response = self.client.post("/api/omnichannel/telegram/unknown", json={"text": "Olá"}, headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-test-secret"})
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
