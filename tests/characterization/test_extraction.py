"""F4 Extrair dados do pedido: POST /tickets/extraction."""
import unittest

from _http import FIXTURES, last_calls, post, reset_provider


class ExtractionCharacterization(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def test_extrai_os_exemplos_fixados(self):
        # Inclui um ticket com nota fiscal de 6 dígitos antes do número do pedido (TK-00002)
        # e tickets sem pedido ou sem produto, que devolvem null.
        for case in FIXTURES["extraction"]:
            with self.subTest(ticket=case["request"]["ticket_id"]):
                resp = post("/tickets/extraction", case["request"])
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.json(), case["response"])

    def test_usa_modelo_large_na_tarefa_extract(self):
        post("/tickets/extraction", FIXTURES["extraction"][0]["request"])
        call = last_calls(1)[0]
        self.assertEqual(call["task"], "extract")
        self.assertTrue(call["model"].endswith("-large"), call["model"])

    def test_texto_vazio_e_rejeitado(self):
        resp = post("/tickets/extraction", {"ticket_id": "TK-1", "text": ""})
        self.assertEqual(resp.status, 422)
        self.assertEqual(resp.json()["detail"][0]["loc"], ["body", "text"])
        self.assertEqual(resp.json()["detail"][0]["type"], "string_too_short")


if __name__ == "__main__":
    unittest.main()
