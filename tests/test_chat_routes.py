import os
import io
import sys
import types
import unittest
from dataclasses import dataclass
from unittest.mock import patch

sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))
dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", dotenv_stub)
os.environ.setdefault("PLATFORM_SECRET_KEY", "platform-chat-test-secret")
os.environ.setdefault("ADMIN_TOKEN", "admin-chat-test-token")
os.environ.setdefault("TELEGRAM_TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

import extensions
extensions.init_extensions = lambda _app: None
from app import app
import routes.platform_routes as platform_routes


@dataclass
class Snapshot:
    db: "Database"
    path: str
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
        self.data = {**self.data, **values} if merge else dict(values)
        self.exists = True
        self.db.collections.setdefault(self.path, {})[self.id] = self

    def collection(self, name):
        return Collection(self.db, f"{self.path}/{self.id}/{name}")


class Collection:
    def __init__(self, db, path, filters=None):
        self.db = db
        self.path = path
        self.filters = filters or []

    def where(self, field, _operator, value):
        return Collection(self.db, self.path, self.filters + [(field, value)])

    def limit(self, _amount):
        return self

    def stream(self):
        rows = list(self.db.collections.get(self.path, {}).values())
        for field, expected in self.filters:
            rows = [row for row in rows if row.data.get(field) == expected]
        return rows

    def document(self, document_id=None):
        documents = self.db.collections.setdefault(self.path, {})
        document_id = document_id or f"generated-{len(documents) + 1}"
        if document_id not in documents:
            documents[document_id] = Snapshot(self.db, self.path, document_id, {}, False)
        return documents[document_id]

    def add(self, values):
        document = self.document()
        document.set(values)
        return document, document


class Database:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return Collection(self, name)

    def put(self, path, document_id, data):
        self.collection(path).document(document_id).set(data)


def set_identity(client, identity):
    with client.session_transaction() as session:
        session["platform_identity"] = identity


class ChatRouteTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="platform-chat-test-secret")
        self.db = Database()
        extensions.db = self.db
        platform_routes._LOGIN_ATTEMPTS.clear()
        self.client = app.test_client()
        set_identity(self.client, {"id": "user-a", "name": "A", "role": "client", "tenant_id": "tenant-a", "tenant_role": "owner"})
        self.db.put("tenants", "tenant-a", {"tenant_id": "tenant-a", "instance_name": "inst-a"})

    def test_conversations_merge_whatsapp_base_contacts_and_instance_history(self):
        self.db.put("contacts", "manual", {"tenant_id": "tenant-a", "name": "Manual", "phone": "258840000001"})
        self.db.put("contacts", "foreign", {"tenant_id": "tenant-b", "name": "Foreign", "phone": "258840000002"})
        self.db.put("clientes_bot/tenant-a/base_contactos", "ana", {"phone": "258841234567", "nome": "Ana WhatsApp"})
        self.db.put("clientes_bot/tenant-a/base_contactos", "bruno", {"phone": "258848765432", "nome": "Bruno WhatsApp"})
        self.db.put("clientes_bot/inst-a/conversas", "258841234567", {"ultima_mensagem": "Olá", "ultima_interacao": "2026-08-22T08:00:00+00:00"})
        self.db.put("clientes_bot/inst-a/conversas", "258849999999", {"ultima_mensagem": "Histórico", "ultima_interacao": "2026-08-22T09:00:00+00:00"})
        self.db.put("clientes_bot/other-inst/conversas", "258847777777", {"ultima_mensagem": "Não mostrar"})

        response = self.client.get("/api/platform/client/conversations")
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()["conversations"]
        by_phone = {row["phone"]: row for row in rows}
        self.assertEqual(set(by_phone), {"258840000001", "258841234567", "258848765432", "258849999999"})
        self.assertEqual(by_phone["258841234567"]["name"], "Ana WhatsApp")
        self.assertEqual(by_phone["258849999999"]["last_message"], "Histórico")
        self.assertNotIn("258847777777", by_phone)

    def test_numeric_group_history_is_classified_as_group(self):
        group_jid = "120363000000000000@g.us"
        numeric_id = group_jid.split("@", 1)[0]
        self.db.put("whatsapp_groups", "group-doc", {"tenant_id": "tenant-a", "group_jid": group_jid, "name": "Grupo Real", "status": "active", "admin_verified": True})
        self.db.put("clientes_bot/inst-a/conversas", numeric_id, {"ultima_mensagem": "Mensagem do grupo"})
        response = self.client.get("/api/platform/client/conversations")
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()["conversations"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["phone"], group_jid)
        self.assertEqual(rows[0]["kind"], "group")
        self.assertEqual(rows[0]["name"], "Grupo Real")

    @patch("routes.platform_routes.listar_chats_whatsapp")
    @patch("routes.platform_routes.get_connection_state", return_value="open")
    def test_open_instance_merges_remote_evolution_chats(self, _state, list_chats):
        list_chats.return_value = [
            {"id": "258845555555@s.whatsapp.net", "name": "Live WhatsApp", "lastMessage": {"conversation": "Mensagem remota"}},
            {"id": "120363000000000000@g.us", "subject": "Grupo remoto"},
        ]
        response = self.client.get("/api/platform/client/conversations")
        self.assertEqual(response.status_code, 200)
        rows = {row["phone"]: row for row in response.get_json()["conversations"]}
        self.assertEqual(rows["258845555555"]["name"], "Live WhatsApp")
        self.assertEqual(rows["258845555555"]["last_message"], "Mensagem remota")
        self.assertEqual(rows["120363000000000000@g.us"]["kind"], "group")

    def test_history_is_aggregated_and_cross_tenant_target_is_rejected(self):
        self.db.put("clientes_bot/tenant-a/base_contactos", "ana", {"phone": "258841234567", "nome": "Ana"})
        self.db.put("clientes_bot/inst-a/conversas", "258841234567", {"ultima_mensagem": "Olá"})
        self.db.put("clientes_bot/inst-a/conversas/258841234567/historico", "message-1", {"role": "user", "text": "Olá", "timestamp": "2026-08-22T08:00:00+00:00"})
        self.db.put("clientes_bot/other-inst/conversas", "258842222222", {"ultima_mensagem": "Privado"})

        response = self.client.get("/api/platform/client/conversations/258841234567/messages")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["messages"][0]["text"], "Olá")

        rejected = self.client.get("/api/platform/client/conversations/258842222222/messages")
        self.assertEqual(rejected.status_code, 403)
        self.assertNotIn("Privado", rejected.get_data(as_text=True))

    @patch("routes.platform_routes.send_media", return_value=True)
    @patch("routes.platform_routes.get_connection_state", return_value="open")
    def test_send_image_persists_metadata_without_file_bytes(self, _state, send_media):
        self.db.put("clientes_bot/tenant-a/base_contactos", "ana", {"phone": "258841234567", "nome": "Ana"})
        response = self.client.post(
            "/api/platform/client/conversations/258841234567/media",
            data={"caption": "Fotografia", "file": (io.BytesIO(b"fake-image"), "foto.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        send_media.assert_called_once()
        stored = self.db.collections["clientes_bot/inst-a/conversas/258841234567/historico"]
        message = next(iter(stored.values())).data
        self.assertEqual(message["media_type"], "image")
        self.assertEqual(message["file_name"], "foto.png")
        self.assertNotIn("fake-image", repr(message))

    @patch("routes.platform_routes.requests.get")
    @patch("routes.platform_routes.get_profile_picture_url", return_value="https://files.example/profile.jpg")
    @patch("routes.platform_routes.get_connection_state", return_value="open")
    def test_profile_image_is_proxied_as_same_origin_image(self, _state, profile_url, remote_get):
        self.db.put("clientes_bot/tenant-a/base_contactos", "ana", {"phone": "258841234567", "nome": "Ana"})
        remote_response = types.SimpleNamespace(content=b"jpeg-bytes", headers={"Content-Type": "image/jpeg"})
        remote_response.raise_for_status = lambda: None
        remote_get.return_value = remote_response
        response = self.client.get("/api/platform/client/conversations/258841234567/profile/image")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        self.assertEqual(response.data, b"jpeg-bytes")
        profile_url.assert_called_once_with("258841234567", instance_name="inst-a")

    @patch("routes.platform_routes.get_connection_state", return_value="offline")
    def test_send_rejects_when_tenant_instance_is_offline(self, _state):
        self.db.put("clientes_bot/tenant-a/base_contactos", "ana", {"phone": "258841234567", "nome": "Ana"})
        response = self.client.post("/api/platform/client/conversations/258841234567/messages", json={"text": "Resposta"})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("Resposta", self.db.collections.get("clientes_bot/inst-a/conversas/258841234567/historico", {}))


if __name__ == "__main__":
    unittest.main()

