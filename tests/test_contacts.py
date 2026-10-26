"""Kiểm tra luồng liên hệ nhân sự: SĐT/email không lộ cho AI, và được điền đúng người khi hiển thị.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_contacts
"""
import sqlite3
import unittest

from backend import analytics, contacts

PEOPLE = {
    1: {"id": 1, "full_name": "Nguyễn Văn An", "display_name": None, "job_title": "Trưởng phòng",
        "unit_name": "Phòng Công nghệ thông tin", "phone": "0912345678", "email": "an.nv@azb.com.vn"},
    # trùng họ tên với id 1 nhưng khác người: phải phân biệt theo id, không theo tên
    2: {"id": 2, "full_name": "Nguyễn Văn An", "display_name": None, "job_title": "Nhân viên",
        "unit_name": "Phòng Kế toán", "phone": "0988000111", "email": None},
    3: {"id": 3, "full_name": "Trần Thị Bình", "display_name": "T. Bình", "job_title": None,
        "unit_name": None, "phone": None, "email": None},
}


class ScrubTest(unittest.TestCase):
    def test_hides_phone_and_email_keeps_markers_and_figures(self):
        text = "Số của anh là 0912 345 678, email an.nv@azb.com.vn. Doanh thu 1.250 tỷ năm 2026 [[LH:1]]"
        out = contacts.scrub(text)
        self.assertNotIn("0912", out)
        self.assertNotIn("azb.com.vn", out)
        self.assertIn("1.250 tỷ", out)
        self.assertIn("2026", out)
        self.assertIn("[[LH:1]]", out)

    def test_plus84_is_hidden(self):
        self.assertNotIn("84912345678", contacts.scrub("Gọi +84912345678 nhé"))


class RenderTest(unittest.TestCase):
    def test_marker_after_full_name_shows_that_persons_contact(self):
        out = contacts.render("Liên hệ Nguyễn Văn An [[LH:1]].", PEOPLE, can_see=True)
        self.assertIn("0912345678", out)
        self.assertIn("an.nv@azb.com.vn", out)
        self.assertIn("Phòng Công nghệ thông tin", out)
        self.assertNotIn("0988000111", out)

    def test_same_name_different_ids_gets_own_phone(self):
        out = contacts.render("Nguyễn Văn An [[LH:2]]", PEOPLE, can_see=True)
        self.assertIn("0988000111", out)
        self.assertNotIn("0912345678", out)
        self.assertIn("Phòng Kế toán", out)

    def test_name_match_ignores_diacritics(self):
        out = contacts.render("Nguyen Van An [[LH:1]]", PEOPLE, can_see=True)
        self.assertIn("0912345678", out)

    def test_wrong_name_fails_closed_without_contact(self):
        out = contacts.render("Trần Thị Bình [[LH:1]]", PEOPLE, can_see=True)
        self.assertNotIn("0912345678", out)
        self.assertIn("chưa xác minh", out)

    def test_name_too_far_from_marker_fails_closed(self):
        far = "Nguyễn Văn An đã họp. " + "x" * (contacts.NAME_WINDOW + 10) + " [[LH:1]]"
        out = contacts.render(far, PEOPLE, can_see=True)
        self.assertNotIn("0912345678", out)

    def test_unknown_id_says_not_found(self):
        out = contacts.render("Ai đó [[LH:999]]", PEOPLE, can_see=True)
        self.assertIn("không tìm thấy", out)
        self.assertNotIn("[[LH", out)

    def test_viewer_without_permission_gets_name_only(self):
        out = contacts.render("Nguyễn Văn An [[LH:1]]", PEOPLE, can_see=False)
        self.assertNotIn("0912345678", out)
        self.assertNotIn("an.nv@azb.com.vn", out)
        self.assertIn("Nguyễn Văn An", out)

    def test_person_without_contact_says_so(self):
        out = contacts.render("Trần Thị Bình [[LH:3]]", PEOPLE, can_see=True)
        self.assertIn("chưa có SĐT/email", out)

    def test_display_name_also_matches(self):
        out = contacts.render("T. Bình [[LH:3]]", PEOPLE, can_see=True)
        self.assertIn("Trần Thị Bình", out)


class DataPathTest(unittest.TestCase):
    """Đường dữ liệu AI dùng (employee_roles không truyền quyền): không có SĐT/email trong kết quả công cụ."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE units (id INTEGER PRIMARY KEY, name TEXT, sort_order INTEGER DEFAULT 0);
            CREATE TABLE employees (id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, phone TEXT,
                                    unit_id INTEGER, sort_order INTEGER DEFAULT 0, status TEXT DEFAULT 'active');
            CREATE TABLE positions (id INTEGER PRIMARY KEY, unit_id INTEGER, title TEXT, title_code TEXT,
                                    employee_id INTEGER, is_head INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0,
                                    reports_to_employee_id INTEGER);
            INSERT INTO units (id, name) VALUES (1, 'Phòng Công nghệ thông tin');
            INSERT INTO employees (id, full_name, email, phone, unit_id)
                VALUES (1, 'Nguyễn Văn An', 'an.nv@azb.com.vn', '0912345678', 1);
            INSERT INTO positions (unit_id, title, title_code, employee_id, is_head)
                VALUES (1, 'Trưởng phòng', 'TP', 1, 1);
        """)

    def tearDown(self):
        self.conn.close()

    def test_ai_employee_list_has_no_contacts_but_keeps_id(self):
        emps = analytics.employee_roles(self.conn)
        self.assertEqual(emps[0]["id"], 1)
        self.assertNotIn("phone", emps[0])
        self.assertNotIn("email", emps[0])
        self.assertNotIn("0912345678", repr(emps))


if __name__ == "__main__":
    unittest.main()
