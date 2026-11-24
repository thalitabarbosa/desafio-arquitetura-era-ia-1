"""F1 Classificar ticket: POST /tickets/classification."""
import unittest

from _http import FIXTURES, last_calls, post, reset_provider


class ClassificationCharacterization(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def test_classifica_os_exemplos_fixados(self):
        for case in FIXTURES["classification"]:
            with self.subTest(ticket=case["request"]["ticket_id"]):
                resp = post("/tickets/classification", case["request"])
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.json(), case["response"])

    def test_usa_modelo_large_na_tarefa_classify(self):
        post("/tickets/classification", FIXTURES["classification"][0]["request"])
        call = last_calls(1)[0]
        self.assertEqual(call["task"], "classify")
        self.assertTrue(call["model"].endswith("-large"), call["model"])

    def test_texto_ausente_e_rejeitado(self):
        resp = post("/tickets/classification", {"ticket_id": "TK-1"})
        self.assertEqual(resp.status, 422)
        self.assertEqual(resp.json()["detail"][0]["loc"], ["body", "text"])
        self.assertEqual(resp.json()["detail"][0]["type"], "missing")

    def test_ticket_id_vazio_e_rejeitado(self):
        resp = post("/tickets/classification", {"ticket_id": "", "text": "Meu pedido não chegou"})
        self.assertEqual(resp.status, 422)
        self.assertEqual(resp.json()["detail"][0]["loc"], ["body", "ticket_id"])
        self.assertEqual(resp.json()["detail"][0]["type"], "string_too_short")


if __name__ == "__main__":
    unittest.main()
