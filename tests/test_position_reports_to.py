"""Chức danh có người báo cáo riêng: chị Duy phụ trách điều hành Ban Tài chính / Ban QLCN, báo cáo anh Nam (Trưởng ban).

Chạy từ thư mục gốc dự án: python -m unittest tests.test_position_reports_to
"""
import gc
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import analytics, db, seed


class PositionReportsToTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(db, "DB_PATH", Path(tmp.name) / "t.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        seed.seed()
        gc.collect()

    def _unit(self, conn, name):
        return conn.execute("SELECT id FROM units WHERE name = ?", (name,)).fetchone()[0]

    def test_duy_runs_both_boards_and_reports_to_nam(self):
        with db.connect() as conn:
            for name in ("Ban Tài chính", "Ban QLCN"):
                pos = analytics.unit_detail(conn, self._unit(conn, name))["positions"]
                head = next(p for p in pos if p["is_head"])
                self.assertEqual(head["employee_name"], "Võ Thành Nam")
                ops = next(p for p in pos if p["title_code"] == "PT")
                self.assertEqual(ops["employee_name"], "Trần Thị Thùy Duy")
                self.assertEqual(ops["reports_to_name"], "Võ Thành Nam")
                self.assertFalse(ops["is_head"])

    def test_duy_roles_show_who_she_reports_to(self):
        with db.connect() as conn:
            duy = next(e for e in analytics.employee_roles(conn) if e["full_name"] == "Trần Thị Thùy Duy")
            by_unit = {r["unit_name"]: r for r in duy["roles"]}
            self.assertEqual(by_unit["Ban Tài chính"]["reports_to_name"], "Võ Thành Nam")
            self.assertIsNone(by_unit["Ban Trợ lý"]["reports_to_name"])
            conc = {c["name"]: c for c in analytics.insights(conn)["concurrent_roles"]}
            self.assertIn("Phụ trách điều hành – Ban QLCN (báo cáo Võ Thành Nam)", conc["Trần Thị Thùy Duy"]["roles"])

    def test_migration_adds_column_to_old_database(self):
        with db.connect() as conn:
            conn.execute("ALTER TABLE positions DROP COLUMN reports_to_employee_id")
        db.init_db()
        with db.connect() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(positions)")}
            self.assertIn("reports_to_employee_id", cols)

    def test_deleting_manager_clears_link(self):
        with db.connect() as conn:
            try:
                nam = conn.execute("SELECT id FROM employees WHERE full_name = 'Võ Thành Nam'").fetchone()[0]
                conn.execute("DELETE FROM positions WHERE employee_id = ?", (nam,))
                conn.execute("DELETE FROM employees WHERE id = ?", (nam,))
            except sqlite3.Error as e:  # pragma: no cover
                self.fail(str(e))
            left = conn.execute("SELECT COUNT(*) FROM positions WHERE reports_to_employee_id IS NOT NULL").fetchone()[0]
            self.assertEqual(left, 0)


if __name__ == "__main__":
    unittest.main()
