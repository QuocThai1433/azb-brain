"""Haiku mặc định + đề nghị nâng Sonnet/Opus cho câu suy luận, giới hạn vòng/thinking của model nhẹ và trần chi tiêu AI mỗi ngày.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_ai_budget
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import ai, budget, db


class QuestionTierTest(unittest.TestCase):
    def test_three_tiers(self):
        self.assertEqual(ai.question_tier("Ai là trưởng phòng nhân sự?"), 0)
        self.assertEqual(ai.question_tier("So sánh doanh thu các khối"), 1)
        self.assertEqual(ai.question_tier("Đánh giá rủi ro từ việc kiêm nhiệm hiện nay"), 2)
        self.assertEqual(ai.question_tier("Phân tích, so sánh và đề xuất giải pháp"), 2)  # nhiều yêu cầu suy luận trong một câu
        self.assertEqual(ai.question_tier("x" * (ai.DEEP_QUESTION_CHARS + 1)), 2)

    def test_hard_keywords_with_or_without_accents(self):
        for q in ("Nguyên nhân doanh thu thấp hơn kế hoạch", "Giải pháp giảm chênh lệch nhân sự", "vi sao du an cham tien do",
                  "Lập bảng so sánh các khối", "Dự báo xu hướng năm sau", "phan tich doanh thu"):
            self.assertGreaterEqual(ai.question_tier(q), 1, q)

    def test_plain_lookups_stay_at_tier_zero(self):
        for q in ("Ai là trưởng phòng nhân sự?", "Quy trình mua hàng ở đâu", "Số điện thoại bảo vệ", "Danh sách nhân viên khối thi công"):
            self.assertEqual(ai.question_tier(q), 0, q)

    def test_long_question_needs_reasoning(self):
        self.assertEqual(ai.question_tier("a " * 200), 1)


class UpgradeOfferTest(unittest.TestCase):
    def test_lookup_has_no_offer(self):
        self.assertIsNone(ai.upgrade_offer("Ai phụ trách phòng kế toán?"))

    def test_reasoning_offers_sonnet_only(self):
        offer = ai.upgrade_offer("So sánh doanh thu các khối")
        self.assertEqual([o["id"] for o in offer["options"]], [ai.SMART_MODEL])

    def test_high_reasoning_offers_opus_then_sonnet(self):
        offer = ai.upgrade_offer("Đánh giá rủi ro từ việc kiêm nhiệm hiện nay")
        self.assertEqual([o["id"] for o in offer["options"]], [ai.DEEP_MODEL, ai.SMART_MODEL])


class DefaultModelTest(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test", "GROQ_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)
        self.tried = []
        patch = mock.patch.object(ai, "_answer_with", side_effect=lambda p, h, m, *a: self.tried.append(m) or {"answer": "ok"})
        patch.start()
        self.addCleanup(patch.stop)
        self.user = {"id": 1, "username": "u", "role": "ceo", "full_name": "U", "employee_id": None}

    def ask(self, text, model=None):
        with mock.patch.object(ai, "PROVIDER", "anthropic"):
            return ai.answer([{"role": "user", "content": text}], self.user, model=model)

    def test_no_choice_uses_haiku_even_for_hard_question(self):
        self.ask("Đánh giá rủi ro từ việc kiêm nhiệm hiện nay")  # nâng model là do người dùng chọn, server không tự đổi
        self.assertEqual(self.tried, [ai.CHAT_MODEL])

    def test_explicit_model_is_respected(self):
        for m in ("claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"):
            self.tried.clear()
            self.ask("Sơ đồ tổ chức AZB", model=m)
            self.assertEqual(self.tried, [m])

    def test_old_auto_id_falls_back_to_haiku(self):
        self.ask("Sơ đồ tổ chức AZB", model="auto")
        self.assertEqual(self.tried, [ai.CHAT_MODEL])

    def test_status_lists_three_models_and_defaults_to_haiku(self):
        with mock.patch.object(ai, "PROVIDER", "anthropic"):
            st = ai.status()
        self.assertEqual([m["id"] for m in st["models"]], ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"])
        self.assertEqual(st["default_model"], ai.CHAT_MODEL)


class PrecheckEndpointTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from backend import app as app_module, auth
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)
        db.init_db()
        with db.connect() as c:
            c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (1, 'ceo', 'ceo', 'x')")
            token = auth.create_session(c, 1)
        self.client = TestClient(app_module.app)
        self.client.cookies.set(auth.SESSION_COOKIE, token)

    def test_precheck_returns_offer_without_calling_ai(self):
        with mock.patch.object(ai, "answer", side_effect=AssertionError("không được gọi AI")):
            r = self.client.post("/api/chat/precheck", json={"content": "Đánh giá rủi ro từ việc kiêm nhiệm"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["offer"]["tier"], 2)

    def test_precheck_lookup_has_no_offer(self):
        r = self.client.post("/api/chat/precheck", json={"content": "Ai phụ trách phòng kế toán?"})
        self.assertIsNone(r.json()["offer"])

    def test_precheck_requires_login(self):
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/api/chat/precheck", json={"content": "x"}).status_code, 401)


class LightModelTest(unittest.TestCase):
    """Model nhẹ: không bật thinking và dùng ít vòng tra cứu hơn."""

    def run_model(self, model):
        calls = []

        class Stream:
            text_stream = iter(())

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                tool = mock.Mock(type="tool_use", id="t", input={}, spec=["type", "id", "input", "name"])
                tool.name = "list_targets"
                return mock.Mock(content=[tool], stop_reason="tool_use", usage=None)

        class Messages:
            def stream(self, **kw):
                calls.append(kw)
                return Stream()

        with mock.patch.object(ai, "client", return_value=mock.Mock(messages=Messages())), \
                mock.patch.object(ai, "_run_tool", return_value={}), \
                mock.patch.object(ai, "message_text", return_value=""):
            ai._answer_anthropic([{"role": "user", "content": "hi"}], model, "SYS",
                                 {"id": 1, "role": "ceo", "username": "u"}, ai.new_audit())
        return calls

    def test_haiku_has_no_thinking_and_fewer_rounds(self):
        calls = self.run_model("claude-haiku-5-5")
        self.assertTrue(all("thinking" not in c for c in calls))
        self.assertEqual(len(calls), ai.LIGHT_TOOL_ROUNDS + 1)  # + vòng "dừng tra cứu"

    def test_sonnet_keeps_thinking_and_full_rounds(self):
        calls = self.run_model("claude-sonnet-5-5")
        self.assertTrue(all(c.get("thinking") == {"type": "adaptive"} for c in calls))
        self.assertEqual(len(calls), ai.MAX_TOOL_ROUNDS + 1)


class BudgetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)
        db.init_db()
        self.staff = {"id": 2, "role": "staff"}
        self.ceo = {"id": 1, "role": "ceo"}

    def spend(self, user_id, usd):
        with db.connect() as c:
            c.execute("INSERT INTO ai_query_log (user_id, question, cost_usd) VALUES (?, 'q', ?)", (user_id, usd))

    def check(self, user, daily=10.0, per_user=2.0):
        with mock.patch.object(budget, "DAILY_BUDGET_USD", daily), mock.patch.object(budget, "USER_DAILY_BUDGET_USD", per_user), \
                db.connect() as c:
            return budget.check(c, user)

    def test_under_budget_is_allowed(self):
        self.spend(2, 1.0)
        self.assertIsNone(self.check(self.staff))

    def test_user_over_personal_budget_is_blocked(self):
        self.spend(2, 2.5)
        self.assertIn("ngân sách", self.check(self.staff))

    def test_ceo_is_exempt_from_personal_budget(self):
        self.spend(1, 5.0)
        self.assertIsNone(self.check(self.ceo))

    def test_company_budget_blocks_everyone_and_counts_ocr(self):
        self.spend(2, 1.0)
        with db.connect() as c:
            c.execute("INSERT INTO ai_usage_log (kind, model, cost_usd) VALUES ('ocr_pdf', 'm', 9.5)")
        self.assertIn("công ty", self.check(self.ceo))
        self.assertIn("công ty", self.check(self.staff))

    def test_zero_disables_limits(self):
        self.spend(2, 100.0)
        self.assertIsNone(self.check(self.staff, daily=0, per_user=0))


if __name__ == "__main__":
    unittest.main()
