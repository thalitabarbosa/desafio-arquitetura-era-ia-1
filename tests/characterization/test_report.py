"""F3 Relatório de temas: POST /reports/topics.

Contrato da main (ADR 0004): Asynchronous Request-Reply. O relatório obtido no fim é o mesmo
fixado na v1-coupled para o período de um dia.
"""
import time
import unittest

from _http import FIXTURES, get, last_calls, post, reset_provider


class ReportCharacterization(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def test_relatorio_de_um_dia(self):
        case = FIXTURES["report"]
        resp = post("/reports/topics", case["request"])
        self.assertEqual(resp.status, 202)
        status_url = resp.headers["Location"]
        self.assertTrue(status_url.startswith("/reports/topics/status/"))
        self.assertTrue(resp.headers["Retry-After"].isdigit())

        deadline = time.monotonic() + 60
        while True:
            status = get(status_url)
            if status.status == 303:
                break
            self.assertEqual(status.status, 200)
            self.assertIn(status.json()["state"], ("pending", "running"))
            self.assertLess(time.monotonic(), deadline, "relatório não ficou pronto em 60 s")
            time.sleep(1)

        result = get(status.headers["Location"])
        self.assertEqual(result.status, 200)
        self.assertEqual(result.json(), case["response"])
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

    def test_tarefa_inexistente(self):
        self.assertEqual(get("/reports/topics/status/nao-existe").status, 404)


if __name__ == "__main__":
    unittest.main()
