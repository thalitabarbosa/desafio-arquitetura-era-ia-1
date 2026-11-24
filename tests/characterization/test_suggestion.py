"""F2 Sugerir resposta: POST /tickets/reply-suggestion.

Contrato da main (ADR 0004): streaming SSE. O texto completo, juntando os trechos, é o mesmo
fixado na v1-coupled.
"""
import unittest

from _http import FIXTURES, last_calls, post, reset_provider, sse_events


class SuggestionCharacterization(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def test_sugere_o_texto_fixado_em_streaming(self):
        case = FIXTURES["suggestion"][0]
        resp = post("/tickets/reply-suggestion", case["request"])
        self.assertEqual(resp.status, 200)
        self.assertTrue(resp.headers.get("Content-Type", "").startswith("text/event-stream"))
        events = sse_events(resp.body)
        text = "".join(data["chunk"] for name, data in events if name == "message")
        self.assertEqual(text, case["response"]["suggestion"])
        self.assertEqual(events[-1], ("end", {"ticket_id": case["request"]["ticket_id"]}))
        call = last_calls(1)[0]
        self.assertEqual(call["task"], "suggest")
        self.assertTrue(call["model"].endswith("-large"), call["model"])
        self.assertTrue(call["stream"])

    def test_ticket_id_ausente_e_rejeitado(self):
        resp = post("/tickets/reply-suggestion", {"text": "Meu pedido não chegou"})
        self.assertEqual(resp.status, 422)
        self.assertEqual(resp.json()["detail"][0]["loc"], ["body", "ticket_id"])
        self.assertEqual(resp.json()["detail"][0]["type"], "missing")


if __name__ == "__main__":
    unittest.main()
