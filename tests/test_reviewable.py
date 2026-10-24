"""Chỉ mời đối chiếu những PDF đọc bằng AI mà API đối chiếu mở được (còn file gốc, văn bản có đánh dấu trang).

Chạy từ thư mục gốc dự án: python -m unittest tests.test_reviewable
"""
import tempfile
import unittest
from pathlib import Path

from backend import db, documents
from tests.test_security import DbCase

AI_NOTE = "Đọc bằng AI từ bản scan – nên đối chiếu bản gốc."
PAGED = "--- Trang 1 ---\nNội dung một\n\n--- Trang 2 ---\nNội dung hai"


class ReviewableIdsTest(DbCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: self.tmp.cleanup())

    def _set(self, doc_id, *, content=PAGED, note=AI_NOTE, name="a.pdf", create=True, pages=2):
        path = Path(self.tmp.name) / f"{doc_id}_{name}"
        if create:
            path.write_bytes(b"%PDF-1.4")
        with db.connect() as c:
            c.execute("UPDATE documents SET extract_status = 'ok', extract_note = ?, content = ?, stored_path = ?, page_count = ?"
                      " WHERE id = ?", (note, content, str(path), pages, doc_id))

    def ids(self):
        with db.connect() as c:
            return documents.reviewable_ids(c)

    def test_ai_pdf_with_page_marks_is_reviewable(self):
        self._set(1)
        self.assertIn(1, self.ids())

    def test_text_without_page_marks_is_reviewable_as_whole_file(self):
        self._set(1, content="Không có đánh dấu trang", pages=2)
        self.assertIn(1, self.ids())

    def test_website_document_is_never_reviewable(self):
        self._set(1)
        with db.connect() as c:
            c.execute("UPDATE documents SET doc_type = 'website' WHERE id = 1")
        self.assertNotIn(1, self.ids())

    def test_whole_review_marks_every_page_and_reindexes_on_edit(self):
        self._set(1, content="Chữ cũ", pages=3)
        with db.connect() as c:
            self.assertEqual(documents.save_whole_review(c, 1, 1, None), "verified")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM doc_page_review WHERE doc_id = 1").fetchone()[0], 3)
            self.assertEqual(documents.save_whole_review(c, 1, 1, "Chữ mới"), "edited")
            self.assertEqual(c.execute("SELECT content FROM documents WHERE id = 1").fetchone()[0], "Chữ mới")
            self.assertEqual(c.execute("SELECT text FROM doc_chunks WHERE doc_id = 1").fetchone()[0], "Chữ mới")

    def test_missing_original_file_is_not(self):
        self._set(1, create=False)
        self.assertNotIn(1, self.ids())

    def test_note_wording_does_not_matter(self):
        # Ghi chú cũ có thể không có chữ "AI" (ví dụ "bản đọc tự động (Gemini)") nhưng vẫn là PDF do AI đọc
        self._set(1, note="CHƯA ĐỐI CHIẾU HẾT: chỉ các trang 1, 2 đã đối chiếu. Các trang còn lại là bản đọc tự động (Gemini).")
        self.assertIn(1, self.ids())

    def test_not_ai_read_or_not_pdf_is_not(self):
        self._set(1, note=None)
        self._set(2, name="b.docx")
        self.assertFalse({1, 2} & self.ids())


if __name__ == "__main__":
    unittest.main()
