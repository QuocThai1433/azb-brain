"""Đọc lại hàng loạt các tài liệu chưa đọc được: chỉ file user có quyền ghi, mặc định chỉ file lỗi, dừng khi hết hạn mức AI.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_reprocess_unread
"""
import unittest
from unittest import mock

from backend import db, documents
from tests.test_security import DbCase


def _set_status(statuses: dict[int, str]) -> None:
    with db.connect() as c:
        for doc_id, status in statuses.items():
            c.execute("UPDATE documents SET extract_status = ? WHERE id = ?", (status, doc_id))


def _status(doc_id: int) -> str:
    with db.connect() as c:
        return c.execute("SELECT extract_status FROM documents WHERE id = ?", (doc_id,)).fetchone()[0]


class CandidatesTest(DbCase):
    def setUp(self):
        super().setUp()
        # 1: internal phòng A, 2: restricted phòng A (chưa đọc được bằng OCR), 3: restricted phòng B,
        # 4: mật phòng B, 5: chung công ty
        _set_status({1: "failed", 2: "needs_ocr", 3: "failed", 4: "failed", 5: "failed"})

    def ids(self, user, include_ocr=False):
        with db.connect() as c:
            return [doc_id for doc_id, _ in documents.reprocess_candidates(c, user, include_ocr)]

    def test_manager_gets_only_failed_docs_in_own_unit(self):
        self.assertEqual(self.ids(self.mgr), [1])

    def test_include_ocr_adds_unread_scans(self):
        self.assertEqual(self.ids(self.mgr, include_ocr=True), [1, 2])

    def test_executive_gets_all_failed_docs(self):
        self.assertEqual(self.ids(self.ceo), [1, 3, 4, 5])

    def test_private_files_never_included(self):
        with db.connect() as c:
            c.execute("UPDATE documents SET access_level = 'private', owner_id = 2 WHERE id = 1")
        self.assertEqual(self.ids(self.mgr), [])


class ReprocessManyTest(DbCase):
    def test_processes_every_queued_doc(self):
        queue = [(1, "failed"), (3, "failed")]
        _set_status({1: "pending", 3: "pending"})

        def fake(doc_id, use_ocr=True):
            _set_status({doc_id: "ok"})

        with mock.patch.object(documents, "process_document", side_effect=fake) as proc:
            documents.reprocess_many(queue)
        self.assertEqual([c.args[0] for c in proc.call_args_list], [1, 3])
        self.assertEqual((_status(1), _status(3)), ("ok", "ok"))

    def test_quota_error_stops_and_restores_remaining_status(self):
        queue = [(1, "failed"), (2, "needs_ocr"), (3, "failed")]
        _set_status({1: "pending", 2: "pending", 3: "pending"})

        def fake(doc_id, use_ocr=True):
            with db.connect() as c:
                c.execute("UPDATE documents SET extract_status = 'failed', extract_note = ? WHERE id = ?",
                          ("Gemini đang hết hạn mức đọc ảnh/scan (429).", doc_id))

        with mock.patch.object(documents, "process_document", side_effect=fake) as proc:
            documents.reprocess_many(queue)
        self.assertEqual(proc.call_count, 1)  # dừng ngay sau lỗi hạn mức
        self.assertEqual(_status(1), "failed")
        self.assertEqual(_status(2), "needs_ocr")  # trả về trạng thái cũ
        self.assertEqual(_status(3), "failed")


if __name__ == "__main__":
    unittest.main()
