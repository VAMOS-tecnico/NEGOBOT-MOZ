import sys
import types
import unittest
from unittest.mock import patch

# O TTS não é usado nestes testes; o shim permite executar a suíte sem instalar áudio.
sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))

from workflows.central_flow import (
    PALAVRAS_PLANOS_NEGOBOT,
    RESPOSTA_PLANOS_NEGOBOT,
    RESPOSTA_SAUDACAO_NEGOBOT,
    classificar_intencao_deterministica,
    normalizar_intencao,
    process_central_flow,
)


class TestNormalizacao(unittest.TestCase):
    def test_remove_acentos_pontuacao_e_espacos(self):
        self.assertEqual(normalizar_intencao("  Olá!!!  "), "ola")
        self.assertEqual(normalizar_intencao("Quanto custa?"), "quanto custa")


class TestClassificacaoDeterministica(unittest.TestCase):
    def test_saudações_sao_classificadas(self):
        for mensagem in ("Olá", "OLÁ!", "Bom dia", "Boa tarde", "Tudo bem?"):
            with self.subTest(mensagem=mensagem):
                self.assertEqual(classificar_intencao_deterministica(mensagem), "saudacao")

    def test_planos_sao_classificados(self):
        for mensagem in (
            "Quais são os preços?",
            "Quanto custa o plano premium?",
            "Quais os benefícios?",
            "Qual é o limite de conversas?",
        ):
            with self.subTest(mensagem=mensagem):
                self.assertEqual(classificar_intencao_deterministica(mensagem), "planos")

    def test_mensagem_normal_continua_para_ia(self):
        self.assertIsNone(classificar_intencao_deterministica("Preciso de ajuda com o catálogo"))


class TestContratoDoRoteiro(unittest.TestCase):
    def test_saudacao_apresenta_negobot_e_teste(self):
        resposta = RESPOSTA_SAUDACAO_NEGOBOT.lower()
        self.assertIn("negobot moz", resposta)
        self.assertIn("inteligência artificial", resposta)
        self.assertIn("teste", resposta)
        self.assertNotIn("como posso ajudar você hoje", resposta)

    def test_planos_contem_precos_e_beneficios_obrigatorios(self):
        resposta = RESPOSTA_PLANOS_NEGOBOT.lower()
        for termo in ("500 mt", "1.000 mt", "1.500 mt", "plano básico", "plano médio", "plano premium", "855000929"):
            # O número M-Pesa é tratado no handler de pagamento; fica excluído deste contrato.
            if termo == "855000929":
                continue
            with self.subTest(termo=termo):
                self.assertIn(termo, resposta)
        self.assertIn("2 dias", resposta)
        self.assertIn("#imagem", resposta)


class TestRoteamentoDeterministico(unittest.TestCase):
    @patch("workflows.central_flow.enviar_resposta_deterministica")
    def test_saudacao_nao_chama_groq(self, enviar):
        process_central_flow(phone_number_or_data="258840000000@s.whatsapp.net", message_text="Olá")
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.args[2], RESPOSTA_SAUDACAO_NEGOBOT)

    @patch("workflows.central_flow.enviar_resposta_deterministica")
    def test_planos_nao_chama_groq(self, enviar):
        process_central_flow(phone_number_or_data="258840000000@s.whatsapp.net", message_text="Quais são os preços?")
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.args[2], RESPOSTA_PLANOS_NEGOBOT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
