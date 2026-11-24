"""F3 Relatório de temas: POST /reports/topics (resposta síncrona, JSON).

O período fixado é um único dia (137 tickets, um lote): cabe nos 30 s da borda. O mês inteiro
termina em 504 na borda na v1; essa dor está no diagnóstico do README, não na suíte.
"""
import unittest

from _http import FIXTURES, last_calls, post, reset_provider


class ReportCharacterization(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def test_relatorio_de_um_dia(self):
        case = FIXTURES["report"]
        resp = post("/reports/topics", case["request"])
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.json(), case["response"])
        calls = [c for c in last_calls(5) if c["task"] == "topics"]
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["model"].endswith("-large"), calls[0]["model"])

    def test_inicio_depois_do_fim_e_rejeitado(self):
        resp = post("/reports/topics", {"start": "2026-08-31", "end": "2026-08-01"})
        self.assertEqual(resp.status, 422)
        self.assertEqual(resp.json(), {"detail": "A data inicial é posterior à data final"})

    def test_data_invalida_e_rejeitada(self):
        resp = post("/reports/topics", {"start": "2026-08-32", "end": "2026-08-31"})
        self.assertEqual(resp.status, 422)
        self.assertEqual(resp.json()["detail"][0]["loc"], ["body", "start"])


if __name__ == "__main__":
    unittest.main()
