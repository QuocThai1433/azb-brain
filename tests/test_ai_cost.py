"""Giảm chi phí AI: cache dùng chung giữa mọi người, lịch sử gọn, ghi chú bộ nhớ dùng Haiku, dùng lại kết quả đọc file trùng,
tiền đọc scan tính vào trần cá nhân.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_ai_cost
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend import ai, budget, db, documents
from tests.test_ai_speed import FakeClient, USER, _msg, _text


class SharedCacheTest(unittest.TestCase):
    def system_for(self, extra):
        fake = FakeClient([(["ok"], _msg([_text("ok")]))])
        with mock.patch.object(ai, "client", return_value=fake):
            ai._answer_anthropic([{"role": "user", "content": "hỏi"}], "claude-haiku-5-5", ai._system_prompt(extra), USER, ai.new_audit())
        return fake.calls[0]["system"]

    def test_cached_block_is_identical_for_different_people(self):
        a, b = self.system_for("Người đang hỏi: An. Ghi chú: thích bảng."), self.system_for("Người đang hỏi: Bình.")
        self.assertEqual(a[0], b[0])
        self.assertEqual(a[0]["cache_control"], {"type": "ephemeral"})
        self.assertIn("An", a[1]["text"])
        self.assertNotIn("cache_control", a[1])
        self.assertNotIn("An.", a[0]["text"])

    def test_dynamic_part_still_reaches_the_model(self):
        system = self.system_for("Người đang hỏi: An.")
        self.assertIn("Hôm nay là ngày", system[1]["text"])
        self.assertIn("Người đang hỏi: An.", system[1]["text"])


class HistoryTest(unittest.TestCase):
    def history(self, n_pairs, long=3000):
        msgs = []
        for i in range(n_pairs):
            msgs += [{"role": "user", "content": f"hỏi {i}"}, {"role": "assistant", "content": f"đáp {i} " + "chữ " * long}]
        return msgs + [{"role": "user", "content": "câu mới"}]

    def test_keeps_only_recent_messages_and_current_question(self):
        out, _ = ai._prepare_history(self.history(10))
        self.assertLessEqual(len(out), ai.MAX_HISTORY_MESSAGES + 1)
        self.assertEqual(out[-1]["content"], "câu mới")

    def test_old_answers_are_clipped_but_recent_ones_are_not(self):
        out, _ = ai._prepare_history(self.history(4))
        answers = [m["content"] for m in out if m["role"] == "assistant"]
        self.assertEqual(len(answers), 4)
        for old in answers[:-ai.RECENT_ANSWERS_FULL]:
            self.assertLessEqual(len(old), ai.OLD_ANSWER_CHARS + 2)
            self.assertTrue(old.endswith("…"))
        for recent in answers[-ai.RECENT_ANSWERS_FULL:]:
            self.assertGreater(len(recent), ai.OLD_ANSWER_CHARS)

    def test_short_answers_untouched(self):
        self.assertEqual(ai._clip_old("ngắn"), "ngắn")


class CompactToolResultTest(unittest.TestCase):
    def test_tool_results_use_compact_json(self):
        block = SimpleNamespace(type="tool_use", name="search", id="t1", input={"q": "x"})
        fake = FakeClient([([], SimpleNamespace(content=[block], stop_reason="tool_use")), (["ok"], _msg([_text("ok")]))])
        with mock.patch.object(ai, "client", return_value=fake), mock.patch.object(ai, "_run_tool", return_value={"a": 1, "b": [1, 2]}):
            ai._answer_anthropic([{"role": "user", "content": "hỏi"}], "claude-sonnet-5-5", "SYS", USER, ai.new_audit())
        sent = fake.calls[1]["messages"][-1]["content"][0]["content"]
        self.assertEqual(sent, '{"result":{"a":1,"b":[1,2]}}')


class MemoryUsesLightModelTest(unittest.TestCase):
    def test_light_first_tries_haiku_before_sonnet(self):
        tried = []

        def fake_create(**kw):
            tried.append(kw["model"])
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="{}")], usage=None)

        client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "x"}), \
                mock.patch.object(ai, "client", return_value=client), \
                mock.patch.object(ai, "log_usage"), mock.patch.dict(ai._cooldown, clear=True):
            self.assertEqual(ai.complete("s", "p", light_first=True), "{}")
            self.assertEqual(tried, [ai.CHAT_MODEL])
            tried.clear()
            ai.complete("s", "p")
            self.assertNotIn(ai.CHAT_MODEL, tried)


class DbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        for target, value in (("backend.db.DB_PATH", Path(self.tmp.name) / "azb.db"),
                              ("backend.documents.UPLOAD_DIR", Path(self.tmp.name) / "uploads")):
            p = mock.patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        documents.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        db.init_db()

    def add_doc(self, name, data, owner=None, status="pending"):
        path = documents.UPLOAD_DIR / name
        path.write_bytes(data)
        with db.connect() as c:
            c.execute("PRAGMA foreign_keys = OFF")  # chủ file chỉ cần là một id
            return c.execute("INSERT INTO documents (title, filename, stored_path, size_bytes, extract_status, owner_id, uploaded_by)"
                             " VALUES (?,?,?,?,?,?,?)", (name, name, str(path), len(data), status, owner, owner)).lastrowid


class SameFileReuseTest(DbCase):
    def test_second_upload_of_same_file_skips_ai(self):
        first = self.add_doc("a.txt", b"Noi dung that\n\nDoan hai", status="pending")
        documents.process_document(first)
        with db.connect() as c:
            self.assertEqual(c.execute("SELECT extract_status FROM documents WHERE id = ?", (first,)).fetchone()[0], "ok")
        twin = self.add_doc("b.txt", (documents.UPLOAD_DIR / "a.txt").read_bytes())
        with mock.patch.object(documents, "extract", side_effect=AssertionError("không được đọc lại")):
            documents.process_document(twin)
        with db.connect() as c:
            d = c.execute("SELECT extract_status, content, extract_note FROM documents WHERE id = ?", (twin,)).fetchone()
            n_src = c.execute("SELECT COUNT(*) FROM doc_chunks WHERE doc_id = ?", (first,)).fetchone()[0]
            n_twin = c.execute("SELECT COUNT(*) FROM doc_chunks WHERE doc_id = ?", (twin,)).fetchone()[0]
        self.assertEqual(d["extract_status"], "ok")
        self.assertIn("Noi dung that", d["content"])
        self.assertIn("Dùng lại", d["extract_note"])
        self.assertEqual(n_src, n_twin)
        self.assertGreater(n_twin, 0)

    def test_different_content_is_read_normally(self):
        first = self.add_doc("a.txt", b"Noi dung mot")
        documents.process_document(first)
        other = self.add_doc("b.txt", b"Noi dung hai")
        documents.process_document(other)
        with db.connect() as c:
            self.assertIn("hai", c.execute("SELECT content FROM documents WHERE id = ?", (other,)).fetchone()[0])

    def test_explicit_reread_of_ok_document_is_not_replaced_by_twin(self):
        first = self.add_doc("a.txt", b"Noi dung mot")
        documents.process_document(first)
        twin = self.add_doc("b.txt", b"Noi dung mot")
        documents.process_document(twin)
        with mock.patch.object(documents, "extract", return_value={"status": "ok", "pages": [(None, "Đọc lại")], "page_count": None,
                                                                   "note": ""}) as ext:
            documents.process_document(twin)  # đã 'ok': người dùng chủ ý đọc lại
        ext.assert_called_once()

    def test_old_documents_without_hash_still_match(self):
        first = self.add_doc("a.txt", b"Noi dung cu")
        documents.process_document(first)
        with db.connect() as c:
            c.execute("UPDATE documents SET content_hash = NULL")
        twin = self.add_doc("b.txt", b"Noi dung cu")
        with mock.patch.object(documents, "extract", side_effect=AssertionError("không được đọc lại")):
            documents.process_document(twin)
        with db.connect() as c:
            self.assertEqual(c.execute("SELECT extract_status FROM documents WHERE id = ?", (twin,)).fetchone()[0], "ok")


class OcrCountsTowardPersonalBudgetTest(DbCase):
    def test_usage_is_logged_for_file_owner(self):
        doc = self.add_doc("a.txt", b"x", owner=7)

        def fake_extract(path, use_ocr=True):
            ai.log_usage("ocr_pdf", "claude-sonnet-5-5", SimpleNamespace(input_tokens=1_000_000, output_tokens=0), "a.pdf")
            return {"status": "ok", "pages": [(None, "Chữ")], "page_count": None, "note": ""}

        with mock.patch.object(documents, "extract", fake_extract):
            documents.process_document(doc)
        with db.connect() as c:
            self.assertEqual(c.execute("SELECT user_id FROM ai_usage_log").fetchone()[0], 7)
            self.assertAlmostEqual(budget.spent_today(c, 7), 3.0)
            self.assertEqual(budget.spent_today(c, 8), 0)
        self.assertIsNone(ai.usage_user.get())  # không rò sang việc khác

    def test_user_over_budget_because_of_ocr_is_blocked(self):
        with db.connect() as c:
            c.execute("INSERT INTO ai_usage_log (kind, model, cost_usd, user_id) VALUES ('ocr_pdf','m',2.5,2)")
        with mock.patch.object(budget, "DAILY_BUDGET_USD", 100.0), mock.patch.object(budget, "USER_DAILY_BUDGET_USD", 2.0), db.connect() as c:
            self.assertIn("ngân sách", budget.check(c, {"id": 2, "role": "staff"}))
            self.assertIsNone(budget.check(c, {"id": 1, "role": "ceo"}))


if __name__ == "__main__":
    unittest.main()
