"""Vòng đời quy trình/tài liệu: quá 12 tháng chưa rà soát, chưa có ngày hiệu lực, bản nháp; website không tính."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import analytics, db


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        with db.connect() as c:
            c.execute("INSERT INTO units (id, code, name, unit_type) VALUES (1, 'P-A', 'Phòng A', 'department')")
            c.executemany(
                "INSERT INTO processes (id, unit_id, code, name, effective_date, status) VALUES (?,?,?,?,?,?)",
                [
                    (1, 1, "QT-01", "Cũ", "2020-01-01", "active"),           # quá hạn
                    (2, 1, "QT-02", "Mới", "2099-01-01", "active"),          # còn hạn (ngày tương lai)
                    (3, 1, "QT-03", "Không ngày", None, "active"),           # chưa có ngày
                    (4, 1, "QT-04", "Ngày sai", "01/08/2026", "active"),     # không đọc được ngày
                    (5, 1, "QT-05", "Đã thay thế", "2010-01-01", "retired"), # đã bỏ -> không tính
                    (6, 1, "QT-06", "Nháp", "2099-01-01", "draft"),          # nháp
                ],
            )
            c.executemany(
                "INSERT INTO documents (id, title, code, doc_type, filename, stored_path, uploaded_at) VALUES (?,?,?,?,?,?,?)",
                [
                    (1, "Quy trình cũ", "QT-OLD", "quy_trinh", "a", "a", "2020-01-01 10:00:00"),
                    (2, "Quy trình mới", "QT-NEW", "quy_trinh", "b", "b", "2099-01-01 10:00:00"),
                    (3, "Trang web", "WEB", "website", "c", "c", "2020-01-01 10:00:00"),  # website không tính
                ],
            )

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def insights(self):
        with db.connect() as c:
            return analytics.insights(c)

    def test_stale_processes(self):
        ids = {p["id"] for p in self.insights()["stale_processes"]}
        self.assertEqual(ids, {1, 3, 4})  # cũ, không ngày, ngày không đọc được; không gồm còn hạn, đã bỏ

    def test_stale_documents_skip_website_and_recent(self):
        ids = {d["id"] for d in self.insights()["stale_documents"]}
        self.assertEqual(ids, {1})

    def test_drafts(self):
        self.assertEqual([p["id"] for p in self.insights()["draft_processes"]], [6])


if __name__ == "__main__":
    unittest.main()
