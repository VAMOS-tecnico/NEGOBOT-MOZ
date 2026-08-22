import time
import unittest
from unittest.mock import patch

import services.group_automation_service as groups


class FakeDocument:
    def __init__(self, data=None, exists=True):
        self._data = data or {}
        self.exists = exists
        self.id = "fake"
        self.deleted = False

    def to_dict(self):
        return dict(self._data)

    @property
    def reference(self):
        return self

    def get(self):
        return self

    def set(self, data, merge=False):
        self._data.update(data)

    def delete(self):
        self.deleted = True


class FakeCollection:
    def __init__(self, documents=None, document_map=None):
        self.documents = documents or []
        self.document_map = document_map or {}

    def where(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def stream(self):
        return self.documents

    def document(self, name):
        return self.document_map.get(name, FakeDocument({}, False))


class FakeDb:
    def __init__(self, tenant, group):
        self.collections = {
            "tenants": FakeCollection([FakeDocument(tenant)]),
            "whatsapp_groups": FakeCollection(document_map={groups.group_document_id(group["group_jid"]): FakeDocument(group)}),
            "group_automation_events": FakeCollection(),
        }

    def collection(self, name):
        return self.collections[name]


class GroupAutomationTests(unittest.TestCase):
    def setUp(self):
        self.tenant = {"instance_name": "tenant-instance", "telefone_proprietario": "258841234567", "diretrizes_corporativas": "Responde com brevidade."}
        self.group = {
            "tenant_id": "fake",
            "instance_name": "tenant-instance",
            "group_jid": "120363000000@g.us",
            "name": "Grupo próprio",
            "admin_verified": True,
            "bot_is_admin": True,
            "status": "active",
            "automation_enabled": True,
            "mention_required": True,
            "welcome_enabled": False,
            "keywords": [{"trigger": "preço", "response": "Consulte o catálogo actualizado da empresa."}],
        }

    def payload(self, text):
        return {
            "event": "messages.upsert",
            "instance": "tenant-instance",
            "data": {"key": {"id": "message-1", "remoteJid": "120363000000@g.us", "fromMe": False}, "message": {"conversation": text}},
        }

    def test_verify_admin_accepts_is_admin(self):
        self.assertEqual(groups.verify_bot_admin(self.tenant, "tenant-instance", [{"id": "258841234567@c.us", "isAdmin": True}]), (True, "admin_verified", "258841234567@s.whatsapp.net"))

    def test_verify_admin_rejects_regular_participant(self):
        verified, reason, _ = groups.verify_bot_admin(self.tenant, "tenant-instance", [{"id": "258841234567@c.us", "isAdmin": False}])
        self.assertFalse(verified)
        self.assertEqual(reason, "connected_identity_not_admin")

    def test_verify_admin_accepts_c_us_and_device_jids(self):
        participants = [{"id": "258841234567:7@c.us", "isAdmin": True}]
        self.assertEqual(groups.verify_bot_admin(self.tenant, "tenant-instance", participants), (True, "admin_verified", "258841234567@s.whatsapp.net"))

    def test_verify_admin_prefers_phone_number_over_lid(self):
        participants = [{"id": "123456789012345@lid", "phoneNumber": "258841234567", "admin": "admin"}]
        self.assertEqual(groups.verify_bot_admin(self.tenant, "tenant-instance", participants), (True, "admin_verified", "258841234567@s.whatsapp.net"))

    def test_disconnected_groups_are_hidden_immediately(self):
        document = FakeDocument({**self.group, "instance_name": "tenant-instance"})
        database = FakeDb(self.tenant, self.group)
        database.collections["whatsapp_groups"].documents = [document]
        groups.extensions.db = database
        self.assertEqual(groups.archive_groups_for_instance("tenant-instance"), 1)
        self.assertEqual(document.to_dict()["status"], "archived")
        self.assertFalse(document.to_dict()["visible"])

    def test_archived_groups_are_deleted_only_after_retention_window(self):
        document = FakeDocument({"instance_name": "tenant-instance", "status": "archived", "archived_at": time.time() - 7200})
        database = FakeDb(self.tenant, self.group)
        database.collections["whatsapp_groups"].documents = [document]
        groups.extensions.db = database
        self.assertEqual(groups.purge_archived_groups(max_age_seconds=3600), 1)
        self.assertTrue(document.deleted)

    @patch("services.group_automation_service.send_whatsapp", return_value=True)
    def test_keyword_requires_mention(self, send_mock):
        groups.extensions.db = FakeDb(self.tenant, self.group)
        groups.handle_group_message(self.payload("preço"))
        send_mock.assert_not_called()

    @patch("services.group_automation_service.send_whatsapp", return_value=True)
    def test_verified_group_keyword_sends_to_group_jid(self, send_mock):
        groups.extensions.db = FakeDb(self.tenant, self.group)
        groups.handle_group_message(self.payload("@Bot preço"))
        send_mock.assert_called_once_with("120363000000@g.us", "Consulte o catálogo actualizado da empresa.", instance_name="tenant-instance")

    @patch("services.group_automation_service.send_whatsapp", return_value=True)
    def test_unverified_group_never_sends(self, send_mock):
        rejected = {**self.group, "admin_verified": False, "bot_is_admin": False, "status": "rejected"}
        groups.extensions.db = FakeDb(self.tenant, rejected)
        groups.handle_group_message(self.payload("@Bot preço"))
        send_mock.assert_not_called()

    @patch("services.group_automation_service.send_whatsapp", return_value=True)
    def test_cross_tenant_group_never_sends(self, send_mock):
        foreign = {**self.group, "tenant_id": "other-tenant"}
        groups.extensions.db = FakeDb(self.tenant, foreign)
        groups.handle_group_message(self.payload("@Bot preço"))
        send_mock.assert_not_called()

    @patch("services.group_automation_service.fetch_group_participants", return_value=[{"id": "258841234567@c.us", "isAdmin": True}])
    @patch("services.group_automation_service.send_whatsapp", return_value=True)
    def test_welcome_only_after_admin_revalidation(self, send_mock, participants_mock):
        configured = {**self.group, "welcome_enabled": True, "welcome_message": "Bem-vindo ao grupo!"}
        groups.extensions.db = FakeDb(self.tenant, configured)
        payload = {"event": "group_participants_update", "instance": "tenant-instance", "data": {"id": "120363000000@g.us", "action": "add", "participants": ["258849999999@c.us"]}}
        groups.handle_group_participant_event(payload)
        participants_mock.assert_called_once()
        send_mock.assert_called_once_with("120363000000@g.us", "Bem-vindo ao grupo!", instance_name="tenant-instance")


if __name__ == "__main__":
    unittest.main()
