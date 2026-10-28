"""Tự đọc lại file lỗi OCR tạm thời (AI quá tải / hết hạn mức): chỉ file đúng loại lỗi, dừng khi còn quá tải, có trần số lần.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_ocr_autoretry
Không gọi API thật: process_document được thay bằng hàm giả.
"""
import unittest
from unittest import mock

from backend import db, documents, ocr_autoretry
from tests.test_ai_cost import DbCase

OVERLOAD = "AI đang quá tải (503). Hãy thử lại sau ít phút."
QUOTA = "AI đang hết hạn mức đọc ảnh/scan (429). Tài liệu chưa đọc được, hãy thử lại sau ít phút."


class IsTransientTest(unittest.TestCase):
    def test_matches_only_friendly_transient_notes(self):
        self.assertTrue(ocr_autoretry.is_transient(OVERLOAD))
        self.assertTrue(ocr_autoretry.is_transient(QUOTA))
        self.assertFalse(ocr_autoretry.is_transient("Ảnh quá lớn (trên 5 MB) – hãy giảm kích thước rồi tải lại."))
        self.assertFalse(ocr_autoretry.is_transient("404 NOT_FOUND. model không còn"))
        self.assertFalse(ocr_autoretry.is_transient(None))


class SweepTest(DbCase):
    def setUp(self):
        super().setUp()
        ocr_autoretry._tries.clear()
        self.addCleanup(ocr_autoretry._tries.clear)

    def failed_doc(self, name, note):
        doc = self.add_doc(name, b"x", status="failed")
        with db.connect() as c:
            c.execute("UPDATE documents SET extract_note = ? WHERE id = ?", (note, doc))
        return doc

    def status(self, doc):
        with db.connect() as c:
            return tuple(c.execute("SELECT extract_status, extract_note FROM documents WHERE id = ?", (doc,)).fetchone())

    def ok_processor(self, calls):
        def fake(doc_id, use_ocr=True):
            calls.append(doc_id)
            with db.connect() as c:
                c.execute("UPDATE documents SET extract_status = 'ok', extract_note = NULL WHERE id = ?", (doc_id,))
        return fake

    def test_retries_transient_failures_and_skips_other_errors(self):
        a = self.failed_doc("a.pdf", OVERLOAD)
        b = self.failed_doc("b.pdf", "Ảnh quá lớn (trên 5 MB) – hãy giảm kích thước rồi tải lại.")
        c = self.failed_doc("c.pdf", QUOTA)
        calls = []
        with mock.patch.object(documents, "process_document", self.ok_processor(calls)):
            self.assertEqual(ocr_autoretry.sweep(), 2)
        self.assertEqual(calls, [a, c])
        self.assertEqual(self.status(a)[0], "ok")
        self.assertEqual(self.status(b)[0], "failed")

    def test_stops_the_batch_while_ai_is_still_overloaded(self):
        a = self.failed_doc("a.pdf", OVERLOAD)
        self.failed_doc("b.pdf", OVERLOAD)
        calls = []

        def still_down(doc_id, use_ocr=True):
            calls.append(doc_id)
            with db.connect() as c:
                c.execute("UPDATE documents SET extract_status = 'failed', extract_note = ? WHERE id = ?", (OVERLOAD, doc_id))

        with mock.patch.object(documents, "process_document", still_down):
            self.assertEqual(ocr_autoretry.sweep(), 0)
        self.assertEqual(calls, [a])  # file thứ hai không bị gọi: AI vẫn đang quá tải

    def test_gives_up_after_max_tries_and_tells_the_user(self):
        a = self.failed_doc("a.pdf", OVERLOAD)
        calls = []

        def still_down(doc_id, use_ocr=True):
            calls.append(doc_id)
            with db.connect() as c:
                c.execute("UPDATE documents SET extract_status = 'failed', extract_note = ? WHERE id = ?", (OVERLOAD, doc_id))

        with mock.patch.object(documents, "process_document", still_down), mock.patch.object(ocr_autoretry, "MAX_TRIES", 2):
            for _ in range(4):
                ocr_autoretry.sweep()
        self.assertEqual(calls, [a, a])  # đúng 2 lần, các lượt sau bỏ qua
        self.assertIn("Đã tự thử lại 2 lần", self.status(a)[1])

    def test_ignores_files_that_are_not_failed(self):
        self.add_doc("ok.pdf", b"x", status="ok")
        with mock.patch.object(documents, "process_document") as proc:
            self.assertEqual(ocr_autoretry.sweep(), 0)
        proc.assert_not_called()

    def test_deleted_file_does_not_break_the_sweep(self):
        a = self.failed_doc("a.pdf", OVERLOAD)

        def vanish(doc_id, use_ocr=True):
            with db.connect() as c:
                c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

        with mock.patch.object(documents, "process_document", vanish):
            self.assertEqual(ocr_autoretry.sweep(), 0)
        self.assertIsNone(self._row(a))

    def _row(self, doc):
        with db.connect() as c:
            return c.execute("SELECT id FROM documents WHERE id = ?", (doc,)).fetchone()


class SchedulerTest(unittest.TestCase):
    def test_disabled_when_interval_is_zero(self):
        with mock.patch.object(ocr_autoretry, "EVERY_MIN", 0), mock.patch("threading.Thread") as thread:
            ocr_autoretry.start_scheduler()
        thread.assert_not_called()

    def test_starts_a_daemon_thread_when_enabled(self):
        with mock.patch.object(ocr_autoretry, "EVERY_MIN", 5), mock.patch("threading.Thread") as thread:
            ocr_autoretry.start_scheduler()
        thread.assert_called_once()
        self.assertTrue(thread.call_args.kwargs["daemon"])


if __name__ == "__main__":
    unittest.main()
