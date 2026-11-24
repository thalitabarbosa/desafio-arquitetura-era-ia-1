"""F2 Sugerir resposta: POST /tickets/reply-suggestion (resposta síncrona, JSON)."""
import unittest

from _http import FIXTURES, last_calls, post, reset_provider


class SuggestionCharacterization(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def test_sugere_o_texto_fixado(self):
        case = FIXTURES["suggestion"][0]
        resp = post("/tickets/reply-suggestion", case["request"])
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.headers.get("Content-Type", "").startswith("application/json"))
        self.assertEqual(resp.json(), case["response"])
        call = last_calls(1)[0]
        self.assertEqual(call["task"], "suggest")
        self.assertTrue(call["model"].endswith("-large"), call["model"])

    def test_ticket_id_ausente_e_rejeitado(self):
        resp = post("/tickets/reply-suggestion", {"text": "Meu pedido não chegou"})
        self.assertEqual(resp.status, 422)
        self.assertEqual(resp.json()["detail"][0]["loc"], ["body", "ticket_id"])
        self.assertEqual(resp.json()["detail"][0]["type"], "missing")


if __name__ == "__main__":
    unittest.main()
