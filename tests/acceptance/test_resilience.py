"""Cenários de falha do provider (ADR 0007). Cada teste deixa o provider de volta no modo normal."""
import json
import time
import unittest

from _client import (EXTRACT_TICKET, TICKET, app_post, fail, provider_calls, reset_provider, stream_post,
                     wait_report)

MAX_ATTEMPTS_PER_DESTINATION = 2  # declarado no README (num_retries: 1 no gateway)


def calls_for(task: str) -> list[dict]:
    return [c for c in provider_calls() if c["task"] == task]


class Resilience(unittest.TestCase):
    def setUp(self):
        reset_provider()

    def tearDown(self):
        reset_provider()

    def test_f1_primario_em_error_500_cai_no_large_do_outro_provider(self):
        fail("openai", "error_500", "gpt-fake-large")
        status, _, body, _ = app_post("/tickets/classification", TICKET)
        self.assertEqual(status, 200, body)
        calls = calls_for("classify")
        primary = [c for c in calls if c["model"] == "gpt-fake-large"]
        self.assertTrue(1 <= len(primary) <= MAX_ATTEMPTS_PER_DESTINATION, calls)
        self.assertTrue(all(c["status"] == 500 for c in primary))
        self.assertEqual((calls[-1]["model"], calls[-1]["status"]), ("claude-fake-large", 200))

    def test_f1_primario_em_timeout_responde_em_ate_15s(self):
        fail("openai", "timeout", "gpt-fake-large")
        status, _, body, elapsed = app_post("/tickets/classification", TICKET)
        self.assertIn(status, (200, 503), body)
        self.assertNotEqual(status, 504)
        self.assertLessEqual(elapsed, 15.0)

    def test_f2_erro_no_meio_do_stream_vira_evento_error(self):
        fail("anthropic", "midstream_error", "claude-fake-large")
        result = stream_post("/tickets/reply-suggestion", TICKET)
        self.assertEqual(result["status"], 200)
        names = [e[0] for e in result["events"]]
        self.assertIn("message", names)
        self.assertEqual(result["events"][-1][:2],
                         ("error", {"ticket_id": "TK-00042", "message": "A geração foi interrompida"}))

    def test_f3_com_os_dois_providers_fora_falha_com_motivo_em_ate_60s(self):
        fail("openai", "error_500")
        fail("anthropic", "error_500")
        status, headers, _, _ = app_post("/reports/topics", {"start": "2026-08-01", "end": "2026-08-31"})
        self.assertEqual(status, 202)
        final, data, _, elapsed = wait_report(headers["Location"], limit_s=60)
        self.assertEqual(final, 200)
        self.assertEqual(data["state"], "failed")
        self.assertTrue(data.get("reason"))
        self.assertLessEqual(elapsed, 60)


class WithoutLargeModels(unittest.TestCase):
    """Os dois modelos large em error_500: cada feature faz o que a tabela de fallback do README diz."""

    def setUp(self):
        reset_provider()
        fail("openai", "error_500", "gpt-fake-large")
        fail("anthropic", "error_500", "claude-fake-large")

    def tearDown(self):
        reset_provider()

    def test_f1_responde_com_o_mini(self):
        status, _, body, _ = app_post("/tickets/classification", TICKET)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["category"], "delivery")
        self.assertEqual((calls_for("classify")[-1]["model"], calls_for("classify")[-1]["status"]),
                         ("gpt-fake-mini", 200))

    def test_f2_responde_com_o_mini_em_streaming(self):
        result = stream_post("/tickets/reply-suggestion", TICKET)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["events"][-1][:2], ("end", {"ticket_id": "TK-00042"}))
        self.assertEqual(calls_for("suggest")[-1]["model"], "gpt-fake-mini")

    def test_f3_relatorio_sai_com_o_mini(self):
        status, headers, _, _ = app_post("/reports/topics", {"start": "2026-08-01", "end": "2026-08-01"})
        self.assertEqual(status, 202)
        final, data, _, _ = wait_report(headers["Location"], limit_s=60)
        self.assertEqual(final, 303, data)
        self.assertEqual(calls_for("topics")[-1]["model"], "gpt-fake-mini")

    def test_f4_falha_explicitamente_sem_usar_mini(self):
        start = time.monotonic()
        status, _, body, _ = app_post("/tickets/extraction", EXTRACT_TICKET)
        self.assertEqual(status, 503, body)
        self.assertIn("detail", json.loads(body))
        self.assertLessEqual(time.monotonic() - start, 15)
        models = {c["model"] for c in calls_for("extract")}
        self.assertEqual(models, {"gpt-fake-large", "claude-fake-large"})


if __name__ == "__main__":
    unittest.main()
