"""Data chép từ máy khác có đường dẫn file tuyệt đối sai: khi khởi động phải trỏ lại về data/uploads.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_relink_uploads
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import db, documents
from tests.test_security import DbCase


class RelinkUploadsTest(DbCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(lambda: self.tmp.cleanup())
        self.up = Path(self.tmp.name)
        p = mock.patch.object(documents, "UPLOAD_DIR", self.up)
        p.start()
        self.addCleanup(p.stop)

    def _path(self, doc_id):
        with db.connect() as c:
            return db.row(c, "SELECT stored_path FROM documents WHERE id = ?", (doc_id,))["stored_path"]

    def _run(self):
        with db.connect() as c:
            return documents.relink_uploads(c)

    def test_foreign_windows_path_is_relinked(self):
        (self.up / "1_a.pdf").write_bytes(b"%PDF-1.4")
        with db.connect() as c:
            c.execute("UPDATE documents SET stored_path = ? WHERE id = 1", (r"C:\Cty\azb-brain\data\uploads\1_a.pdf",))
        self.assertEqual(self._run(), 1)
        self.assertEqual(Path(self._path(1)), self.up / "1_a.pdf")

    def test_missing_file_is_left_alone(self):
        with db.connect() as c:
            c.execute("UPDATE documents SET stored_path = ? WHERE id = 1", (r"C:\x\9_b.pdf",))
        self.assertEqual(self._run(), 0)
        self.assertEqual(self._path(1), r"C:\x\9_b.pdf")


if __name__ == "__main__":
    unittest.main()
