import unittest

from services.payment_service import TABELA_PLANOS, identificar_plano_por_valor
from services.plan_service import ADDONS, DEMO_ENTITLEMENTS, entitlements_for_tenant, plan_channel_limit, public_plan_rows


class PlanCatalogTests(unittest.TestCase):
    def test_prices_and_ids_remain_compatible(self):
        self.assertEqual(TABELA_PLANOS[500.0]["id"], "basico")
        self.assertEqual(TABELA_PLANOS[1000.0]["id"], "medio")
        self.assertEqual(TABELA_PLANOS[1500.0]["id"], "premium")
        self.assertEqual(identificar_plano_por_valor(500)["id"], "basico")
        self.assertEqual(identificar_plano_por_valor(1000)["id"], "medio")
        self.assertEqual(identificar_plano_por_valor(1500)["id"], "premium")

    def test_paid_entitlements_expose_limits_and_channels(self):
        version = "2026-08-v2"
        basic = entitlements_for_tenant({"plano": "basico", "status_plano": "ativo", "plan_rules_version": version})
        medium = entitlements_for_tenant({"plano": "medio", "status_plano": "ativo", "plan_rules_version": version})
        premium = entitlements_for_tenant({"plano": "premium", "status_plano": "ativo", "plan_rules_version": version})
        self.assertEqual(basic["contact_limit"], 1500)
        self.assertEqual(basic["campaigns_per_month"], 2)
        self.assertEqual(plan_channel_limit({"plano": "basico", "status_plano": "ativo"}), 1)
        self.assertEqual(medium["conversation_limit"], 5000)
        self.assertEqual(medium["additional_channel_slots"], 1)
        self.assertEqual(premium["conversation_limit"], 15000)
        self.assertEqual(premium["additional_channel_slots"], 3)
        self.assertTrue(premium["mass_broadcast"])

    def test_demo_never_gets_paid_entitlements(self):
        result = entitlements_for_tenant({"plano": "premium", "status_plano": "demonstracao"})
        self.assertEqual(result["plan_id"], DEMO_ENTITLEMENTS["plan_id"])
        self.assertEqual(result["additional_channel_slots"], 0)
        self.assertFalse(result["mass_broadcast"])

    def test_existing_paid_medium_and_premium_are_grandfathered(self):
        legacy = entitlements_for_tenant({"plano": "medio", "status_plano": "ativo", "limite_conversas": None})
        self.assertIsNone(legacy["conversation_limit"])
        self.assertIsNone(legacy["campaigns_per_month"])
        current = entitlements_for_tenant({"plano": "medio", "status_plano": "ativo", "plan_rules_version": "2026-08-v2"})
        self.assertEqual(current["conversation_limit"], 5000)
        self.assertEqual(current["campaigns_per_month"], 10)

    def test_public_catalog_and_addons_are_serializable(self):
        rows = public_plan_rows()
        self.assertEqual([row["id"] for row in rows], ["basico", "medio", "premium"])
        self.assertEqual(rows[1]["campaigns_per_month"], 10)
        self.assertEqual(rows[2]["team_seats"], 5)
        self.assertEqual([row["price_usd"] for row in rows], [8, 16, 24])
        self.assertIn("canais_plus", ADDONS)
        self.assertEqual(ADDONS["canais_plus"]["price_mt"], 500)
        self.assertEqual(ADDONS["canais_plus"]["price_usd"], 8)
        self.assertEqual(ADDONS["utilizador_adicional"]["price_usd"], 2)


if __name__ == "__main__":
    unittest.main()
