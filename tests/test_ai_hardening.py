"""Củng cố trợ lý AI: che SĐT/email trong nội dung tài liệu, quyền insights, trường cho phép, cắt kết quả dài, tool trùng,
model dự phòng không đắt hơn, nguồn tài liệu, giữ chỗ ngân sách, số vòng và trần chi phí mỗi câu.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_ai_hardening
"""
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from backend import ai, budget, db
from tests.test_security import DbCase


class ToolResultTest(DbCase):
    def test_phone_and_email_in_document_text_never_reach_the_model(self):
        text = "Liên hệ anh An 0912 345 678 hoặc an.nguyen@azb.com.vn để biết thêm"
        with db.connect() as c:
            c.execute("INSERT INTO documents (id, unit_id, title, doc_type, filename, stored_path, access_level, extract_status,"
                      " content, char_count) VALUES (20, 2, 'Danh bạ', 'khac', 'f.txt', '', 'internal', 'ok', ?, ?)", (text, len(text)))
            c.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) VALUES (?, 20, 0, 1)", (text,))
        out = json.dumps(self.tool("read_document", {"doc_id": 20, "from_chunk": 0}, self.ceo), ensure_ascii=False)
        self.assertNotIn("0912", out)
        self.assertNotIn("an.nguyen", out)
        self.assertIn("[đã ẩn]", out)

    def test_duplicate_call_in_same_question_is_not_resent(self):
        audit = ai.new_audit()
        first = ai._run_tool("get_org_overview", {}, self.ceo, audit)
        again = ai._run_tool("get_org_overview", {}, self.ceo, audit)
        self.assertNotIn("lap_lai", json.dumps(first, ensure_ascii=False))
        self.assertIn("lap_lai", again)
        self.assertNotIn("lap_lai", ai._run_tool("get_org_overview", {}, self.ceo, ai.new_audit()))  # câu hỏi khác thì gọi lại được

    def test_failed_call_can_be_retried(self):
        audit = ai.new_audit()
        self.assertIn("error", ai._run_tool("read_document", {"doc_id": 3, "from_chunk": 0}, self.mgr, audit))
        self.assertIn("error", ai._run_tool("read_document", {"doc_id": 3, "from_chunk": 0}, self.mgr, audit))

    def test_long_result_is_cut_and_flagged(self):
        with mock.patch.object(ai, "TOOL_RESULT_CHARS", 50):
            out = ai._cap_result({"x": "a" * 500})
        self.assertTrue(out["da_cat_bot"])
        self.assertEqual(len(out["noi_dung_cat"]), 50)
        self.assertEqual(ai._cap_result({"x": "ngắn"}), {"x": "ngắn"})


class AllowlistTest(DbCase):
    def test_unit_detail_only_sends_allowed_fields(self):
        with db.connect() as c:
            c.execute("INSERT INTO positions (unit_id, title, employee_id, is_head, notes) VALUES (2, 'Trưởng phòng', 1, 1, 'ghi chú vị trí')")
            c.execute("INSERT INTO processes (unit_id, name, content) VALUES (2, 'Quy trình mua hàng', 'BƯỚC 1 rất dài')")
        out = self.tool("get_unit_detail", {"unit_id": 2}, self.ceo)
        text = json.dumps(out, ensure_ascii=False)
        for secret in ("NV001", "ghi chú riêng", "ghi chú vị trí", "0912345678", "1990-05-05", "Vô thời hạn", "BƯỚC 1 rất dài"):
            self.assertNotIn(secret, text)
        self.assertEqual(out["members"][0]["full_name"], "Nguyễn Văn An")
        self.assertEqual(out["processes"][0]["name"], "Quy trình mua hàng")

    def test_get_process_still_returns_full_content(self):
        with db.connect() as c:
            pid = c.execute("INSERT INTO processes (unit_id, name, content) VALUES (2, 'QT', 'BƯỚC 1')").lastrowid
        self.assertEqual(self.tool("get_process", {"process_id": pid}, self.ceo)["content"], "BƯỚC 1")


class InsightsPermissionTest(DbCase):
    def test_insights_follow_feature_permission(self):
        self.assertIn("error", self.tool("get_org_insights", {}, self.mgr))
        self.assertIn("error", self.tool("get_org_insights", {}, {**self.view, "permissions": ["ai_use"]}))
        self.assertNotIn("error", self.tool("get_org_insights", {}, {**self.mgr, "permissions": ["insights"]}))
        self.assertNotIn("error", self.tool("get_org_insights", {}, self.ceo))


class PagingTest(DbCase):
    def test_list_documents_pages(self):
        with mock.patch.object(ai, "LIST_PAGE", 2):
            first = self.tool("list_documents", {"unit_id": 0, "kind": "tat_ca"}, self.ceo)
            self.assertEqual(len(first["documents"]), 2)
            self.assertTrue(first["has_more"])
            rest = self.tool("list_documents", {"unit_id": 0, "kind": "tat_ca", "offset": first["next_offset"]}, self.ceo)
            self.assertEqual(len(rest["documents"]), 2)
            self.assertEqual({d["doc_id"] for d in first["documents"]} & {d["doc_id"] for d in rest["documents"]}, set())

    def test_list_employees_filters_by_unit(self):
        self.assertEqual([e["full_name"] for e in self.tool("list_employees", {"unit_id": 2}, self.ceo)], ["Nguyễn Văn An"])
        self.assertEqual(self.tool("list_employees", {"unit_id": 3}, self.ceo), [])


class SourceTest(DbCase):
    def test_search_and_read_tell_who_uploaded_and_review_state(self):
        with db.connect() as c:
            c.execute("UPDATE documents SET uploaded_by = 2, page_count = 2 WHERE id = 1")
            c.execute("UPDATE users SET full_name = 'Chị Mai' WHERE id = 2")
        hit = next(r for r in self.tool("search_documents", {"query": "alpha noibo", "unit_id": 0}, self.ceo)["results"] if r["doc_id"] == 1)
        self.assertEqual(hit["uploaded_by"], "Chị Mai")
        self.assertIn("chưa được đối chiếu", hit["doi_chieu"])
        with db.connect() as c:
            c.execute("INSERT INTO doc_page_review (doc_id, page_no, status) VALUES (1, 1, 'verified')")
        read = self.tool("read_document", {"doc_id": 1, "from_chunk": 0}, self.ceo)
        self.assertEqual(read["doi_chieu"], "đã đối chiếu 1/2 trang")


class FallbackTest(unittest.TestCase):
    def test_fallback_never_goes_to_a_pricier_model(self):
        self.assertEqual(ai._model_chain("claude-haiku-5-5"), ["claude-haiku-5-5"])
        self.assertEqual(ai._model_chain("claude-sonnet-5-5"), ["claude-sonnet-5-5", "claude-haiku-5-5"])
        self.assertEqual(ai._model_chain("claude-opus-5-5"), ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"])

    def test_no_other_provider_code_left(self):
        self.assertFalse(hasattr(ai, "GROQ_URL"))
        self.assertFalse(hasattr(ai, "_answer_groq"))


class BudgetReserveTest(DbCase):
    def test_in_flight_questions_are_counted(self):
        with mock.patch.object(budget, "DAILY_BUDGET_USD", 0.3), mock.patch.object(budget, "RESERVE_USD", 0.3), \
                db.connect() as c:
            self.assertIsNone(budget.reserve(c, self.ceo))
            try:
                self.assertIsNotNone(budget.reserve(c, self.ceo))  # chỗ giữ của câu đang chạy làm đầy ngân sách
            finally:
                budget.release(self.ceo["id"])
            self.assertIsNone(budget.reserve(c, self.ceo))  # trả chỗ xong thì hỏi lại được
            budget.release(self.ceo["id"])

    def test_exec_has_own_daily_cap(self):
        with db.connect() as c:
            c.execute("INSERT INTO ai_query_log (user_id, cost_usd) VALUES (1, 7)")
            with mock.patch.object(budget, "DAILY_BUDGET_USD", 100), mock.patch.object(budget, "EXEC_DAILY_BUDGET_USD", 6):
                self.assertIsNotNone(budget.check(c, self.ceo))
                self.assertIsNone(budget.check(c, self.mgr))  # người khác không bị ảnh hưởng
            with mock.patch.object(budget, "DAILY_BUDGET_USD", 100), mock.patch.object(budget, "EXEC_DAILY_BUDGET_USD", 0):
                self.assertIsNone(budget.check(c, self.ceo))


class RoundsAndQuestionBudgetTest(unittest.TestCase):
    def run_model(self, model, question, input_tokens=0):
        calls = []

        class Stream:
            text_stream = iter(())

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                tool = SimpleNamespace(type="tool_use", id="t", input={}, name="list_targets")
                return SimpleNamespace(content=[tool], stop_reason="tool_use",
                                       usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=0))

        class Messages:
            def stream(self, **kw):
                calls.append(kw)
                return Stream()

        with mock.patch.object(ai, "client", return_value=SimpleNamespace(messages=Messages())), \
                mock.patch.object(ai, "_run_tool", return_value={}), mock.patch.object(ai, "message_text", return_value=""):
            ai._answer_anthropic([{"role": "user", "content": question}], model, "SYS",
                                 {"id": 1, "role": "ceo", "username": "u"}, ai.new_audit())
        return calls

    def test_reasoning_question_gets_more_rounds(self):
        plain = self.run_model("claude-sonnet-5-5", "Sơ đồ tổ chức AZB")
        hard = self.run_model("claude-sonnet-5-5", "So sánh và đối chiếu hai quy trình")
        self.assertEqual(len(plain), ai.MAX_TOOL_ROUNDS + 1)
        self.assertEqual(len(hard), ai.MAX_TOOL_ROUNDS + ai.EXTRA_REASON_ROUNDS + 1)

    def test_question_budget_stops_the_lookup_loop(self):
        with mock.patch.object(ai, "QUESTION_BUDGET_USD", 1.0):
            calls = self.run_model("claude-sonnet-5-5", "So sánh và đối chiếu hai quy trình", input_tokens=1_000_000)  # ~3 USD/vòng
        self.assertEqual(len(calls), 2)  # một vòng tra cứu rồi buộc kết luận, không chạy hết các vòng
        with mock.patch.object(ai, "QUESTION_BUDGET_USD", 0):
            calls = self.run_model("claude-sonnet-5-5", "Sơ đồ tổ chức AZB", input_tokens=1_000_000)
        self.assertEqual(len(calls), ai.MAX_TOOL_ROUNDS + 1)  # 0 = tắt trần


if __name__ == "__main__":
    unittest.main()
