import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.trial_service import PENDING_STATUS, pending_fields
from routes import webhook_routes


class Snapshot:
    def __init__(self, exists, data=None):
        self.exists = exists
        self._data = data or {}

    def to_dict(self):
        return dict(self._data)


class TrialConnectionWebhookTests(unittest.TestCase):
    def make_db(self, canonical, legacy, tenant_refs=None):
        db = MagicMock()
        client_bot = MagicMock()
        clients = MagicMock()
        tenants = MagicMock()
        canonical_ref = MagicMock()
        legacy_ref = MagicMock()
        canonical_ref.path = "clientes_bot/258840000000"
        legacy_ref.path = "clientes_bot/cliente_258840000000"
        canonical_ref.get.return_value = canonical
        legacy_ref.get.return_value = legacy
        client_bot.document.side_effect = lambda name: canonical_ref if name == "258840000000" else legacy_ref
        query = MagicMock()
        query.limit.return_value.stream.return_value = tenant_refs or []
        tenants.where.return_value = query
        db.collection.side_effect = lambda name: {
            "clientes_bot": client_bot,
            "clientes": clients,
            "tenants": tenants,
        }[name]
        return db, canonical_ref, legacy_ref, clients

    def test_open_starts_pending_trial(self):
        start = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
        db, canonical_ref, legacy_ref, clients = self.make_db(
            Snapshot(False),
            Snapshot(True, pending_fields("258840000000", start)),
        )
        with patch.object(webhook_routes.extensions, "db", db), patch.object(
            webhook_routes.Config, "EVOLUTION_INSTANCE_NAME", "assistente_negobot"
        ):
            webhook_routes._mark_trial_connection_open("258840000000", {"data": {"state": "open"}})
        fields = canonical_ref.set.call_args.args[0]
        self.assertEqual(fields["trial_status"], "trial_active")
        self.assertTrue(fields["trial_connection_confirmed"])
        self.assertEqual(fields["evolution_state"], "open")
        self.assertEqual(legacy_ref.set.call_args.kwargs["merge"], True)
        self.assertEqual(clients.document.call_args.args[0], "258840000000")

    def test_unknown_instance_is_ignored(self):
        db, canonical_ref, legacy_ref, clients = self.make_db(Snapshot(False), Snapshot(False))
        with patch.object(webhook_routes.extensions, "db", db), patch.object(
            webhook_routes.Config, "EVOLUTION_INSTANCE_NAME", "assistente_negobot"
        ):
            webhook_routes._mark_trial_connection_open("258899999999", {"data": {"state": "open"}})
        canonical_ref.set.assert_not_called()
        legacy_ref.set.assert_not_called()
        clients.document.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
