"""Requisitos de experiência da main, medidos pela borda com o provider no modo normal (ADR 0004)."""
import json
import unittest

from _client import TICKET, app_get, app_post, provider_calls, reset_provider, stream_post, wait_report


class Flows(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def test_f1_entrega_o_resultado_em_ate_3s(self):
        status, _, body, elapsed = app_post("/tickets/classification", TICKET)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ticket_id": "TK-00042", "category": "delivery", "priority": "high"})
        self.assertLessEqual(elapsed, 3.0)

    def test_f2_primeiro_trecho_em_ate_1_5s_e_antes_da_metade(self):
        result = stream_post("/tickets/reply-suggestion", TICKET)
        self.assertEqual(result["status"], 200)
        self.assertTrue(result["headers"]["Content-Type"].startswith("text/event-stream"))
        self.assertLessEqual(result["first_chunk_s"], 1.5)
        self.assertLess(result["first_chunk_s"], result["total_s"] / 2)
        chunks = [e for e in result["events"] if e[0] == "message"]
        self.assertGreater(len(chunks), 10, "o texto chegou em bloco: algo no caminho está acumulando")
        self.assertEqual(result["events"][-1][:2], ("end", {"ticket_id": "TK-00042"}))

    def test_f3_aceita_o_mes_em_ate_1s_e_entrega_5000_tickets(self):
        status, headers, body, elapsed = app_post("/reports/topics", {"start": "2026-08-01", "end": "2026-08-31"})
        self.assertEqual(status, 202)
        self.assertLessEqual(elapsed, 1.0)
        self.assertIn("Retry-After", headers)
        final, data, final_headers, _ = wait_report(headers["Location"], limit_s=300)
        self.assertEqual(final, 303, data)
        status, _, body, _ = app_get(final_headers["Location"])
        self.assertEqual(status, 200)
        report = json.loads(body)
        self.assertEqual(report["total_tickets"], 5000)
        self.assertEqual(sum(t["count"] for t in report["topics"]), 5000)
        topics_calls = [c for c in provider_calls(5000) if c["task"] == "topics" and c["status"] == 200]
        self.assertEqual(len(topics_calls), 34)  # 5000 tickets em lotes de 150


if __name__ == "__main__":
    unittest.main()
