"""Kiểm tra liên kết tài khoản ↔ hồ sơ nhân sự, xem hồ sơ của mình và luồng yêu cầu sửa thông tin.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_selfinfo
"""
import sqlite3
import unittest

from backend import contacts, selfinfo
from backend.db import SCHEMA


class SelfInfoTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        for col in ("job_title TEXT", "unit_id INTEGER", "birth_date TEXT", "contract_term TEXT", "hr_department TEXT",
                    "hr_division TEXT", "employee_code TEXT"):
            try:
                self.conn.execute(f"ALTER TABLE employees ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        self.conn.execute("ALTER TABLE users ADD COLUMN employee_id INTEGER")
        self.conn.executescript("""
            INSERT INTO units (id, code, name, unit_type) VALUES (1, 'IT', 'Phòng IT', 'department');
            INSERT INTO employees (id, full_name, phone, email, birth_date, joined_date, contract_term, job_title, unit_id)
                VALUES (1, 'Trần Quốc Thái', '0912345678', 'thai@azb.com.vn', '1990-05-01', '2020-01-02', 'Không thời hạn', 'Chuyên viên', 1),
                       (2, 'Nguyễn Văn An', '0988000111', NULL, '1985-03-04', '2019-01-01', 'Có thời hạn', 'Trưởng phòng', 1),
                       (3, 'Lê Thị Bình', NULL, NULL, NULL, NULL, NULL, NULL, 1),
                       (4, 'Lê Thị Bình', NULL, NULL, NULL, NULL, NULL, NULL, 1);
            INSERT INTO users (id, username, full_name, role, password_hash) VALUES
                (10, 'thai', 'Trần Quốc Thái', 'manager', 'x'),
                (11, 'an', 'Nguyễn Văn An', 'manager', 'x'),
                (12, 'binh', 'Lê Thị Bình', 'manager', 'x'),
                (13, 'admin', 'Quản trị', 'admin', 'x');
        """)
        self.admin = {"id": 13, "role": "admin"}

    def tearDown(self):
        self.conn.close()

    def user(self, uid=10):
        r = self.conn.execute("SELECT id, role, employee_id FROM users WHERE id = ?", (uid,)).fetchone()
        return dict(r)

    # ---- liên kết ----
    def test_suggestion_only_when_name_matches_exactly_one_person(self):
        s = selfinfo.link_options(self.conn)["suggestions"]
        self.assertEqual(s[10], 1)
        self.assertEqual(s[11], 2)
        self.assertNotIn(12, s)  # hai người trùng tên: không tự đoán

    def test_one_profile_links_to_one_account(self):
        selfinfo.link(self.conn, 10, 1)
        with self.assertRaises(ValueError):
            selfinfo.link(self.conn, 11, 1)
        selfinfo.link(self.conn, 10, None)  # gỡ rồi gán lại được
        selfinfo.link(self.conn, 11, 1)

    def test_unknown_employee_rejected(self):
        with self.assertRaises(ValueError):
            selfinfo.link(self.conn, 10, 999)

    # ---- hồ sơ của mình ----
    def test_marker_fills_only_own_profile(self):
        selfinfo.link(self.conn, 10, 1)
        out = selfinfo.apply_marker(self.conn, self.user(10), "Thông tin của bạn:\n[[TT]]")
        self.assertIn("0912345678", out)
        self.assertIn("01/05/1990", out)
        self.assertIn("Không thời hạn", out)
        self.assertNotIn("0988000111", out)

    def test_marker_for_unlinked_account_explains_instead_of_guessing(self):
        out = selfinfo.apply_marker(self.conn, self.user(11), "[[TT]]")
        self.assertIn("chưa được liên kết", out)
        self.assertNotIn("0912345678", out)
        self.assertNotIn("0988000111", out)

    def test_text_without_marker_unchanged(self):
        self.assertEqual(selfinfo.apply_marker(self.conn, self.user(10), "Xin chào"), "Xin chào")

    def test_lh_marker_shows_own_contact_to_non_admin_but_not_others(self):
        people = contacts.load(self.conn, {1, 2})
        mine = contacts.render("Trần Quốc Thái [[LH:1]]", people, can_see=False, self_id=1)
        other = contacts.render("Nguyễn Văn An [[LH:2]]", people, can_see=False, self_id=1)
        self.assertIn("0912345678", mine)
        self.assertNotIn("0988000111", other)

    def test_identity_note_has_no_contact_data(self):
        selfinfo.link(self.conn, 10, 1)
        from backend import db
        original = db.connect
        db.connect = lambda: self.conn
        try:
            note = selfinfo.identity_note(1)
        finally:
            db.connect = original
        self.assertIn("Trần Quốc Thái", note)
        self.assertNotIn("0912345678", note)
        self.assertNotIn("thai@azb.com.vn", note)

    # ---- yêu cầu sửa ----
    def test_cannot_submit_without_link(self):
        with self.assertRaises(ValueError):
            selfinfo.submit(self.conn, self.user(10), "phone", "0909999999")

    def test_request_does_not_change_profile_until_approved(self):
        selfinfo.link(self.conn, 10, 1)
        req = selfinfo.submit(self.conn, self.user(10), "phone", "0909.999.999")
        self.assertEqual(self.conn.execute("SELECT phone FROM employees WHERE id = 1").fetchone()[0], "0912345678")
        selfinfo.decide(self.conn, self.admin, req["id"], True)
        self.assertEqual(self.conn.execute("SELECT phone FROM employees WHERE id = 1").fetchone()[0], "0909999999")
        log = self.conn.execute("SELECT detail FROM audit_log WHERE action = 'profile_change'").fetchone()[0]
        self.assertIn("0912345678", log)  # giữ giá trị cũ để khôi phục
        self.assertIn("0909999999", log)

    def test_rejected_request_leaves_profile_unchanged(self):
        selfinfo.link(self.conn, 10, 1)
        req = selfinfo.submit(self.conn, self.user(10), "email", "moi@azb.com.vn")
        selfinfo.decide(self.conn, self.admin, req["id"], False, "Sai")
        self.assertEqual(self.conn.execute("SELECT email FROM employees WHERE id = 1").fetchone()[0], "thai@azb.com.vn")
        with self.assertRaises(ValueError):  # đã quyết định thì không duyệt lại được
            selfinfo.decide(self.conn, self.admin, req["id"], True)

    def test_user_can_only_target_own_employee_record(self):
        selfinfo.link(self.conn, 10, 1)
        selfinfo.submit(self.conn, self.user(10), "job_title", "Phó phòng")
        row = self.conn.execute("SELECT employee_id FROM employee_change_requests").fetchone()
        self.assertEqual(row[0], 1)

    def test_resubmitting_same_field_replaces_pending_request(self):
        selfinfo.link(self.conn, 10, 1)
        first = selfinfo.submit(self.conn, self.user(10), "phone", "0909999999")
        second = selfinfo.submit(self.conn, self.user(10), "phone", "0908888888")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM employee_change_requests").fetchone()[0], 1)

    def test_invalid_values_rejected(self):
        selfinfo.link(self.conn, 10, 1)
        for field, value in (("phone", "12345"), ("email", "khong-phai-email"), ("birth_date", "31/02/1990"),
                             ("password_hash", "x"), ("full_name", "  ")):
            with self.assertRaises(ValueError, msg=(field, value)):
                selfinfo.submit(self.conn, self.user(10), field, value)

    def test_same_value_rejected(self):
        selfinfo.link(self.conn, 10, 1)
        with self.assertRaises(ValueError):
            selfinfo.submit(self.conn, self.user(10), "phone", "0912345678")

    def test_approval_blocked_if_account_relinked_elsewhere(self):
        selfinfo.link(self.conn, 10, 1)
        req = selfinfo.submit(self.conn, self.user(10), "phone", "0909999999")
        selfinfo.link(self.conn, 10, None)
        with self.assertRaises(ValueError):
            selfinfo.decide(self.conn, self.admin, req["id"], True)
        self.assertEqual(self.conn.execute("SELECT phone FROM employees WHERE id = 1").fetchone()[0], "0912345678")

    def test_withdraw_only_own_pending(self):
        selfinfo.link(self.conn, 10, 1)
        selfinfo.link(self.conn, 11, 2)
        req = selfinfo.submit(self.conn, self.user(10), "phone", "0909999999")
        with self.assertRaises(ValueError):
            selfinfo.withdraw(self.conn, 11, req["id"])
        selfinfo.withdraw(self.conn, 10, req["id"])


if __name__ == "__main__":
    unittest.main()
