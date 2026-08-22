import unittest
from unittest.mock import patch

import extensions
import routes.webhook_routes as webhook_routes


class FakeSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = dict(data)
        self.exists = True

    def to_dict(self):
        return dict(self._data)


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.id = document_id

    @property
    def path(self):
        return f"{self.collection.name}/{self.id}"

    def get(self):
        data = self.collection.documents.get(self.id)
        return FakeSnapshot(self.id, data) if data is not None else FakeSnapshot(self.id, {})

    def set(self, values, merge=False):
        if merge:
            self.collection.documents.setdefault(self.id, {}).update(dict(values))
        else:
            self.collection.documents[self.id] = dict(values)


class FakeQuery:
    def __init__(self, collection, field, value):
        self.collection = collection
        self.field = field
        self.value = value

    def limit(self, _count):
        return self

    def stream(self):
        return [
            FakeSnapshot(document_id, data)
            for document_id, data in self.collection.documents.items()
            if data.get(self.field) == self.value
        ]


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.documents = {}

    def document(self, document_id):
        return FakeDocument(self, document_id)

    def where(self, field, _operator, value):
        return FakeQuery(self, field, value)


class FakeDB:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection(name))


class ConnectionUpdateRegressionTests(unittest.TestCase):
    def test_connection_update_grava_tenant_usando_document_reference(self):
        database = FakeDB()
        database.collection("tenants").document("tenant-1").set({
            "instance_name": "258840000000",
            "telefone_proprietario": "258840000000",
            "central_account_id": "ca_test",
        })
        previous_db = extensions.db
        extensions.db = database
        try:
            with patch.object(webhook_routes.Config, "EVOLUTION_INSTANCE_NAME", "assistente_negobot"), \
                 patch.object(webhook_routes, "is_paid_plan", return_value=False), \
                 patch.object(webhook_routes, "registry_status", return_value={}), \
                 patch.object(webhook_routes, "claim_trial_for_account", return_value=(True, {"trial_consumed": True})), \
                 patch.object(webhook_routes, "trial_fields_from_registry", return_value={"trial_status": "active"}):
                webhook_routes._handle_connection_update({
                    "event": "CONNECTION_UPDATE",
                    "instance": "258840000000",
                    "data": {"state": "open"},
                })
        finally:
            extensions.db = previous_db

        stored = database.collection("tenants").documents["tenant-1"]
        self.assertEqual(stored["evolution_state"], "open")
        self.assertEqual(stored["instance_name"], "258840000000")
        self.assertEqual(stored["trial_status"], "active")


if __name__ == "__main__":
    unittest.main()
