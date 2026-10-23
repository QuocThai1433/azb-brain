"""Biên chế: định biên trên sơ đồ, số đã gán, còn trống, nhân sự HCNS đang làm, chênh lệch."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import analytics, db


class StaffingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        with db.connect() as c:
            c.execute("INSERT INTO units (id, code, name, unit_type, sort_order) VALUES (1, 'P-A', 'Phòng A', 'department', 1)")
            c.execute("INSERT INTO units (id, code, name, unit_type, sort_order) VALUES (2, 'P-B', 'Phòng B', 'department', 2)")
            c.execute("INSERT INTO units (id, code, name, unit_type, sort_order) VALUES (3, 'T-X', 'Tổ X', 'team', 3)")
            c.execute("INSERT INTO employees (id, full_name, unit_id, status) VALUES (1, 'A', 1, 'active')")
            c.execute("INSERT INTO employees (id, full_name, unit_id, status) VALUES (2, 'B', 1, 'active')")
            c.execute("INSERT INTO employees (id, full_name, unit_id, status) VALUES (3, 'C', 1, 'inactive')")
            c.execute("INSERT INTO positions (unit_id, title, employee_id, headcount) VALUES (1, 'Trưởng', 1, 1)")
            c.execute("INSERT INTO positions (unit_id, title, employee_id, headcount) VALUES (1, 'Nhân viên', NULL, 3)")
            c.execute("INSERT INTO positions (unit_id, title, employee_id, headcount) VALUES (2, 'Trưởng', NULL, 1)")

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def by_unit(self):
        with db.connect() as c:
            return {s["unit_id"]: s for s in analytics.insights(c)["staffing"]}

    def test_planned_seated_open_and_hcns(self):
        s = self.by_unit()[1]
        self.assertEqual((s["planned"], s["seated"], s["hcns_active"]), (4, 1, 2))  # inactive không tính
        self.assertEqual(s["open_on_chart"], 3)

    def test_gap_is_hcns_minus_planned(self):
        s = self.by_unit()[1]
        self.assertEqual(s["gap"], -2)  # thiếu 2 người so với định biên 4

    def test_unit_without_staff_shows_negative_gap(self):
        s = self.by_unit()[2]
        self.assertEqual((s["planned"], s["hcns_active"], s["gap"]), (1, 0, -1))

    def test_only_departments_divisions_committees(self):
        self.assertNotIn(3, self.by_unit())  # "team" không nằm trong bảng biên chế


if __name__ == "__main__":
    unittest.main()
