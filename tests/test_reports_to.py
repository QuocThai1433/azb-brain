"""Phân tích cơ cấu ghi rõ cấp quản lý trực tiếp của từng đơn vị (kể cả khi vị trí đứng đầu còn trống).

Chạy từ thư mục gốc dự án: python -m unittest tests.test_reports_to
"""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import analytics, db, seed


class ReportsToTest(unittest.TestCase):
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

    def test_qaqc_and_hsse_report_to_ptgd_thuong_truc(self):
        with db.connect() as conn:
            ins = analytics.insights(conn)
            by_name = {d["unit_name"]: d for d in ins["deputy_led_departments"]}
            self.assertIn("Nguyễn Đức Tịnh", by_name["P. QA/QC"]["reports_to"])
            self.assertIn("Nguyễn Đức Tịnh", analytics.unit_detail(conn, self._unit(conn, "P. HSSE"))["reports_to"])

    def test_vacant_division_head_reports_to_tgd(self):
        with db.connect() as conn:
            ins = analytics.insights(conn)
            vh = next(v for v in ins["vacancies"] if v["unit_name"] == "Khối Vận hành")
            self.assertIn("Trần Minh Nhơn", vh["reports_to"])
            mkt = next(d for d in ins["deputy_led_departments"] if d["unit_name"] == "P. MKT")
            self.assertIn("Trần Minh Nhơn", mkt["reports_to"])

    def test_span_of_control_names_head(self):
        with db.connect() as conn:
            span = {x["unit_name"]: x for x in analytics.insights(conn)["span_of_control"]}
            self.assertIn("Trần Minh Nhơn", span["Ban Tổng Giám đốc"]["head"])
            self.assertIn("(trống)", analytics.head_label(conn, self._unit(conn, "Khối Vận hành")))

    def test_concurrent_person_lists_units_they_manage(self):
        with db.connect() as conn:  # như dữ liệu thật: anh Tịnh cũng là Giám đốc Khối Kinh tế Kỹ thuật
            tinh = conn.execute("SELECT id FROM employees WHERE full_name = 'Nguyễn Đức Tịnh'").fetchone()[0]
            conn.execute("UPDATE positions SET employee_id = ? WHERE unit_id = ? AND is_head = 1",
                         (tinh, self._unit(conn, "Khối Kinh tế Kỹ thuật")))
            conc = {c["name"]: c for c in analytics.insights(conn)["concurrent_roles"]}
            groups = {m["via"]: m["units"] for m in conc["Nguyễn Đức Tịnh"]["manages"]}
            self.assertTrue({"P. QA/QC", "P. HSSE"} <= set(groups["PTGĐ Thường trực"]))
            self.assertIn("P. Đấu thầu", groups["Khối Kinh tế Kỹ thuật"])


if __name__ == "__main__":
    unittest.main()

