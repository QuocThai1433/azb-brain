"""Liên kết tài khoản ↔ hồ sơ nhân sự: admin gán khi tạo tài khoản (tuỳ chọn) hoặc người dùng tự xin và admin duyệt."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        self.clients = {}
        with db.connect() as c:
            for eid, name in ((1, "Nguyễn Văn An"), (2, "Trần Thị Bình")):
                c.execute("INSERT INTO employees (id, employee_code, full_name, phone) VALUES (?,?,?,?)",
                          (eid, f"NV{eid:03d}", name, "0912345678"))
            for uid, name, role in ((1, "admin", "admin"), (2, "an", "viewer"), (3, "binh", "viewer")):
                c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (?,?,?,'x')", (uid, name, role))
                cl = TestClient(app_module.app)
                cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
                self.clients[name] = cl

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def emp_of(self, uid):
        with db.connect() as c:
            return c.execute("SELECT employee_id FROM users WHERE id = ?", (uid,)).fetchone()[0]


class LinkRequestTest(Base):
    def test_create_with_employee_and_without(self):
        a = self.clients["admin"]
        r = a.post("/api/users", json={"username": "moi", "role": "viewer", "password": "matkhau123", "employee_id": 1})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.emp_of(r.json()["id"]), 1)
        dup = a.post("/api/users", json={"username": "moi2", "role": "viewer", "password": "matkhau123", "employee_id": 1})
        self.assertEqual(dup.status_code, 400)
        r = a.post("/api/users", json={"username": "moi3", "role": "viewer", "password": "matkhau123"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(self.emp_of(r.json()["id"]))

    def test_user_requests_admin_approves(self):
        u, a = self.clients["an"], self.clients["admin"]
        self.assertEqual({e["id"] for e in u.get("/api/me/link-options").json()}, {1, 2})
        self.assertNotIn("phone", u.get("/api/me/link-options").json()[0])
        self.assertEqual(u.post("/api/me/link-request", json={"employee_id": 1}).status_code, 200)
        self.assertIsNone(self.emp_of(2))  # chưa duyệt thì chưa liên kết
        self.assertEqual(u.get("/api/me/profile").json()["link_request"]["status"], "pending")
        pend = a.get("/api/link-requests").json()
        self.assertEqual(len(pend), 1)
        self.assertEqual(u.get("/api/link-requests").status_code, 403)  # user thường không duyệt được
        self.assertEqual(a.post(f"/api/link-requests/{pend[0]['id']}/decide", json={"approve": True}).status_code, 200)
        self.assertEqual(self.emp_of(2), 1)
        me = u.get("/api/me/profile").json()
        self.assertTrue(me["linked"])
        self.assertIsNone(me["link_request"])
        self.assertEqual(u.post("/api/me/link-request", json={"employee_id": 2}).status_code, 400)  # đã liên kết rồi

    def test_taken_profile_reject_and_resubmit(self):
        u, b, a = self.clients["an"], self.clients["binh"], self.clients["admin"]
        u.post("/api/me/link-request", json={"employee_id": 1})
        b.post("/api/me/link-request", json={"employee_id": 1})  # hai người cùng xin một hồ sơ
        first, second = [r["id"] for r in a.get("/api/link-requests").json()]
        self.assertEqual(a.post(f"/api/link-requests/{first}/decide", json={"approve": True}).status_code, 200)
        self.assertEqual(a.post(f"/api/link-requests/{second}/decide", json={"approve": True}).status_code, 400)
        self.assertIsNone(self.emp_of(3))
        self.assertEqual(b.post("/api/me/link-request", json={"employee_id": 1}).status_code, 400)  # hồ sơ đã có chủ
        self.assertEqual(b.post("/api/me/link-request", json={"employee_id": 2}).status_code, 200)
        pend = a.get("/api/link-requests").json()
        self.assertEqual(len(pend), 1)  # gửi lại thì thay đơn cũ đang chờ
        a.post(f"/api/link-requests/{pend[0]['id']}/decide", json={"approve": False, "note": "sai người"})
        lr = b.get("/api/me/profile").json()["link_request"]
        self.assertEqual((lr["status"], lr["admin_note"]), ("rejected", "sai người"))


if __name__ == "__main__":
    unittest.main()


class LinkNoticeTest(Base):
    """Sau khi admin xử lý, người dùng thấy huy hiệu + thông báo một lần; admin thấy số đơn chờ."""

    def test_notice_after_decision(self):
        u, a = self.clients["an"], self.clients["admin"]
        self.assertEqual(u.get("/api/auth/state").json()["user"]["profile_notices"], 0)
        u.post("/api/me/link-request", json={"employee_id": 1})
        self.assertEqual(a.get("/api/auth/state").json()["user"]["pending_links"], 1)
        rid = a.get("/api/link-requests").json()[0]["id"]
        a.post(f"/api/link-requests/{rid}/decide", json={"approve": True})
        self.assertEqual(a.get("/api/auth/state").json()["user"]["pending_links"], 0)
        self.assertEqual(u.get("/api/auth/state").json()["user"]["profile_notices"], 1)
        notice = u.get("/api/me/profile").json()["link_notice"]
        self.assertEqual((notice["status"], notice["employee_name"]), ("approved", "Nguyễn Văn An"))
        u.post("/api/me/profile/seen")
        self.assertEqual(u.get("/api/auth/state").json()["user"]["profile_notices"], 0)
        self.assertIsNone(u.get("/api/me/profile").json()["link_notice"])

    def test_rejection_notice_carries_reason(self):
        u, a = self.clients["binh"], self.clients["admin"]
        u.post("/api/me/link-request", json={"employee_id": 2})
        rid = a.get("/api/link-requests").json()[0]["id"]
        a.post(f"/api/link-requests/{rid}/decide", json={"approve": False, "note": "sai người"})
        n = u.get("/api/me/profile").json()["link_notice"]
        self.assertEqual((n["status"], n["admin_note"]), ("rejected", "sai người"))


class ProfileUpdateTest(Base):
    """Cập nhật nhiều thông tin một lần: chỉ gửi trường thực sự đổi, kiểm tra hết trước khi ghi."""

    def setUp(self):
        super().setUp()
        with db.connect() as c:
            c.execute("UPDATE users SET employee_id = 1 WHERE id = 2")
        self.u = self.clients["an"]

    def test_direct_fields_apply_and_others_wait(self):
        r = self.u.post("/api/me/profile/update", json={"values": {
            "full_name": "Nguyễn Văn An", "phone": "0987654321",  # họ tên không đổi
            "email": "An@Azb.com.vn", "job_title": "Giám đốc", "contract_term": ""}})  # contract_term trống = bỏ qua
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((sorted(r.json()["applied"]), r.json()["pending"]), (["email", "phone"], ["job_title"]))
        with db.connect() as c:
            emp = c.execute("SELECT phone, email, job_title FROM employees WHERE id = 1").fetchone()
            self.assertEqual(tuple(emp), ("0987654321", "an@azb.com.vn", None))  # chức danh chưa đổi
            self.assertEqual(c.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'profile_self_edit'").fetchone()[0], 2)
        reqs = self.u.get("/api/me/profile").json()["requests"]
        self.assertEqual([(x["field"], x["new_value"]) for x in reqs], [("job_title", "Giám đốc")])

    def test_invalid_value_rejects_whole_batch(self):
        r = self.u.post("/api/me/profile/update", json={"values": {"email": "ok@azb.com.vn", "phone": "abc"}})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Số điện thoại", r.json()["detail"])
        self.assertEqual(self.u.get("/api/me/profile").json()["requests"], [])
        self.assertEqual(self.u.post("/api/me/profile/update", json={"values": {}}).status_code, 400)

    def test_unlinked_user_cannot_update(self):
        r = self.clients["binh"].post("/api/me/profile/update", json={"values": {"email": "b@azb.com.vn"}})
        self.assertEqual(r.status_code, 400)
