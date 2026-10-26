"""Phân tích: tổng và danh sách trưởng/phó phòng, và id đơn vị để bấm từ mục kiêm nhiệm.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_leadership
"""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import analytics, db, seed


class LeadershipTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(db, "DB_PATH", Path(tmp.name) / "t.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        seed.seed()
        gc.collect()

    def test_counts_match_filled_positions_by_title_code(self):
        with db.connect() as conn:
            lead = analytics.insights(conn)["leadership"]
            for key, codes in (("heads", ("TP", "TB", "TBP")), ("deputies", ("PP", "PB"))):
                want = conn.execute(
                    f"SELECT COUNT(*) FROM positions WHERE employee_id IS NOT NULL AND title_code IN ({','.join('?' * len(codes))})",
                    codes).fetchone()[0]
                self.assertEqual(lead[key]["count"], want)
                self.assertEqual(len(lead[key]["people"]), want)
            self.assertTrue(lead["deputies"]["count"] > 0)
            self.assertTrue(all(p["unit_id"] and p["name"] for p in lead["deputies"]["people"]))

    def test_manages_has_unit_ids_parallel_to_names(self):
        with db.connect() as conn:
            tinh = conn.execute("SELECT id FROM employees WHERE full_name = 'Nguyễn Đức Tịnh'").fetchone()[0]
            for m in analytics.direct_reports_of(conn, tinh):
                self.assertEqual(len(m["units"]), len(m["unit_ids"]))
                for uid, name in zip(m["unit_ids"], m["units"]):
                    self.assertEqual(conn.execute("SELECT name FROM units WHERE id = ?", (uid,)).fetchone()[0], name)

    def test_concurrent_roles_expose_unit_ids(self):
        with db.connect() as conn:
            for c in analytics.insights(conn)["concurrent_roles"]:
                self.assertEqual(len(c["role_items"]), len(c["roles"]))
                self.assertTrue(all(r["unit_id"] for r in c["role_items"]))


if __name__ == "__main__":
    unittest.main()
