import unittest
from types import SimpleNamespace

from backend import ai


class UsageTest(unittest.TestCase):
    def test_defaults_are_cheap(self):
        self.assertEqual(ai.MAX_TOOL_ROUNDS, 4)
        self.assertIn("sonnet", ai.ANTHROPIC_MODEL)
        self.assertEqual(ai.ANTHROPIC_EFFORT, "low")

    def test_usage_accumulates_over_rounds(self):
        audit = ai.new_audit()
        u = SimpleNamespace(input_tokens=1000, output_tokens=500, cache_read_input_tokens=2000, cache_creation_input_tokens=0)
        ai.record_usage(audit, "claude-sonnet-5-5", u)
        ai.record_usage(audit, "claude-sonnet-5-5", u)
        usage = audit["usage"]
        self.assertEqual((usage["input"], usage["output"], usage["cache_read"]), (2000, 1000, 4000))
        self.assertGreater(usage["cost_usd"], 0)

    def test_opus_costs_more_than_haiku(self):
        u = SimpleNamespace(input_tokens=1000, output_tokens=1000)
        a, b = ai.new_audit(), ai.new_audit()
        ai.record_usage(a, "claude-opus-5-5", u)
        ai.record_usage(b, "claude-haiku-5-5", u)
        self.assertGreater(a["usage"]["cost_usd"], b["usage"]["cost_usd"])

    def test_groq_not_priced(self):
        audit = ai.new_audit()
        ai.record_usage(audit, "openai/gpt-oss-120b", SimpleNamespace(input_tokens=10, output_tokens=10))
        self.assertEqual(audit["usage"]["cost_usd"], 0)



class UsageLogTest(__import__("tests.test_security", fromlist=["DbCase"]).DbCase):
    def test_log_usage_writes_row_and_never_raises(self):
        from backend import db
        u = SimpleNamespace(input_tokens=1000, output_tokens=2000, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        ai.log_usage("ocr_pdf", "claude-sonnet-5-5", u, "a.pdf (trang 1-4)")
        ai.log_usage("ocr_pdf", "claude-sonnet-5-5", None, "bỏ qua khi không có usage")
        with db.connect() as c:
            rows = c.execute("SELECT kind, label, model, input_tokens, output_tokens, cost_usd FROM ai_usage_log").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0][0], rows[0][1], rows[0][3], rows[0][4]), ("ocr_pdf", "a.pdf (trang 1-4)", 1000, 2000))
        self.assertGreater(rows[0][5], 0)


if __name__ == "__main__":
    unittest.main()
