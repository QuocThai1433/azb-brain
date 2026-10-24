"""Nhập SĐT/ngày vào từ danh sách HCNS: người trùng tên trong DB chỉ được ghi khi phòng ban và chức danh chỉ ra đúng một người.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_hr_contacts
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import openpyxl

from backend import db, hr_contacts


def _workbook(path: Path, people: list[tuple]) -> str:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = hr_contacts.PRIMARY_SHEET
    for i, (name, title, dept, phone, start) in enumerate(people, start=1):
        ws.append([i, 1, name, title, dept, None, phone, start, "Hợp đồng không XĐTH"])
    for sheet in hr_contacts.CROSS_SHEETS:
        wb.create_sheet(sheet)
    wb.save(path)
    return str(path)


class HrContactsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        with db.connect() as c:
            for code, name, title, dept in (
                    ("NV1", "Nguyễn Minh Vương", "Trưởng BP. M&E", "Phòng Thiết kế - Kỹ thuật"),
                    ("NV2", "Nguyễn Minh Vương", "Trưởng BP. Khối lượng M&E", "Phòng Đấu thầu"),
                    ("NV3", "Trần Quang Hiển", "Chỉ Huy trưởng", "CT. Châu Giang"),
                    ("NV4", "Trần Quang Hiển", "Trưởng nhóm Giám sát QS", "CT. Motul"),
                    ("NV5", "Lê Văn Một", "Kế toán", "Phòng Tài chính")):
                c.execute("INSERT INTO employees (employee_code, full_name, job_title, hr_department) VALUES (?,?,?,?)",
                          (code, name, title, dept))
            c.commit()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def _plan(self, people):
        return hr_contacts.plan(_workbook(self.dir / "hcns.xlsx", people))

    def test_duplicate_name_resolved_by_department_and_title(self):
        res = self._plan([("Nguyễn Minh Vương", "NV Khối lượng M&E", "Đấu thầu", "0906.988.508", "15/06/2015")])
        self.assertEqual(res["resolved_by_dept"], ["Nguyễn Minh Vương"])
        self.assertEqual(res["ambiguous_db"], [])
        with db.connect() as c:
            code = c.execute("SELECT employee_code FROM employees WHERE id = ?", (res["updates"][0]["employee_id"],)).fetchone()[0]
        self.assertEqual(code, "NV2")
        self.assertEqual(res["updates"][0]["joined_date"], "2015-06-15")

    def test_duplicate_name_without_matching_department_is_skipped(self):
        res = self._plan([("Trần Quang Hiển", "Kỹ sư Hiện trường", "Yongjin", "0902.751.925", "26/10/2020")])
        self.assertEqual(res["ambiguous_db"], ["Trần Quang Hiển"])
        self.assertEqual(res["updates"], [])

    def test_matching_department_but_other_title_is_skipped(self):
        res = self._plan([("Nguyễn Minh Vương", "Kế toán", "Đấu thầu", "0906.988.508", "15/06/2015")])
        self.assertEqual(res["ambiguous_db"], ["Nguyễn Minh Vương"])
        self.assertEqual(res["updates"], [])

    def test_unique_name_still_matches_without_department(self):
        res = self._plan([("Lê Văn Một", "Khác hoàn toàn", "Khác", "0911.222.333", "01/02/2018")])
        self.assertEqual(res["resolved_by_dept"], [])
        self.assertEqual(len(res["updates"]), 1)


if __name__ == "__main__":
    unittest.main()
