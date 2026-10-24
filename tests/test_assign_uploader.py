"""Script gán người đăng cho tài liệu không rõ người đăng: chỉ đếm khi thiếu --apply, và chỉ đụng tài liệu uploaded_by IS NULL.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_assign_uploader
"""
import unittest

from backend import assign_uploader, db
from tests.test_security import DbCase


def _uploaders() -> dict[int, object]:
    with db.connect() as c:
        return {r[0]: r[1] for r in c.execute("SELECT id, uploaded_by FROM documents")}


class AssignUploaderTest(DbCase):
    def setUp(self):
        super().setUp()
        with db.connect() as c:  # doc 1 đã có người đăng, các doc còn lại không rõ
            c.execute("UPDATE documents SET uploaded_by = 3 WHERE id = 1")
            c.commit()

    def test_dry_run_changes_nothing(self):
        self.assertEqual(assign_uploader.main(["mgrA"]), 0)
        self.assertEqual(_uploaders()[2], None)

    def test_apply_fills_only_unknown_uploaders(self):
        self.assertEqual(assign_uploader.main(["mgrA", "--apply"]), 0)
        uploaders = _uploaders()
        self.assertEqual(uploaders[1], 3)  # người đăng đã biết giữ nguyên
        self.assertTrue(all(uploaders[i] == 2 for i in (2, 3, 4, 5)))

    def test_unknown_username_writes_nothing(self):
        self.assertEqual(assign_uploader.main(["khong_co", "--apply"]), 1)
        self.assertEqual(_uploaders()[2], None)


if __name__ == "__main__":
    unittest.main()
