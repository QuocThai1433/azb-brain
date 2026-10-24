"""Đăng ký tự do: tài khoản mới chờ admin duyệt, luôn là viewer, không đăng nhập được trước khi được duyệt.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_register
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db, documents


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.patches = [mock.patch.object(db, "DB_PATH", self.root / "azb.db"),
                        mock.patch.object(documents, "UPLOAD_DIR", self.root / "uploads")]
        for p in self.patches:
            p.start()
        (self.root / "uploads").mkdir()
        db.init_db()
        app_module._register_log.clear()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def add_admin(self):
        with db.connect() as c:
            c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (1,'admin','admin','x')")
            cl = TestClient(app_module.app)
            cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, 1))
        return cl

    def user(self, username):
        with db.connect() as c:
            return c.execute("SELECT role, active, password_hash FROM users WHERE username = ?", (username,)).fetchone()

    def test_register_blocked_before_first_admin(self):
        r = TestClient(app_module.app).post("/api/auth/register", json={"username": "nva", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        self.assertEqual(r.status_code, 403)
        self.assertIsNone(self.user("nva"))

    def test_register_creates_pending_viewer_and_cannot_login(self):
        self.add_admin()
        anon = TestClient(app_module.app)
        r = anon.post("/api/auth/register", json={"username": " NguyenVanA ", "password": "matkhau123", "full_name": "Nguyễn Văn A", "unit": "P. Kế toán", "phone": "456"})
        self.assertEqual(r.status_code, 200)
        u = self.user("nguyenvana")
        self.assertEqual((u["role"], u["active"]), ("viewer", 0))
        self.assertNotEqual(u["password_hash"], "matkhau123")

        r = anon.post("/api/auth/login", json={"username": "nguyenvana", "password": "matkhau123"})
        self.assertEqual(r.status_code, 403)
        r = anon.post("/api/auth/login", json={"username": "nguyenvana", "password": "sai-mat-khau"})
        self.assertEqual(r.status_code, 401)

    def test_admin_approval_enables_login(self):
        admin = self.add_admin()
        anon = TestClient(app_module.app)
        anon.post("/api/auth/register", json={"username": "nvb", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        uid = self.user_id("nvb")
        self.assertEqual(admin.put(f"/api/users/{uid}", json={"active": 1}).status_code, 200)
        r = anon.post("/api/auth/login", json={"username": "nvb", "password": "matkhau123"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["role"], "viewer")

    def test_role_in_payload_is_ignored(self):
        self.add_admin()
        TestClient(app_module.app).post("/api/auth/register",
                                        json={"username": "hacker", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT",
                                              "role": "admin", "active": 1})
        u = self.user("hacker")
        self.assertEqual((u["role"], u["active"]), ("viewer", 0))

    def test_full_name_required_and_note_stored(self):
        admin = self.add_admin()
        anon = TestClient(app_module.app)
        for name in (None, "", "   "):
            body = {"username": "nvk", "password": "matkhau123"}
            if name is not None:
                body["full_name"] = name
            self.assertEqual(anon.post("/api/auth/register", json=body).status_code, 400)
        self.assertIsNone(self.user("nvk"))
        self.assertEqual(anon.post("/api/auth/register", json={"username": "nvk", "password": "matkhau123", "full_name": "x" * 101}).status_code, 400)
        self.assertEqual(anon.post("/api/auth/register", json={"username": "nvk", "password": "matkhau123", "full_name": "Lê Văn K",
                                                               "unit": "u" * 101}).status_code, 400)
        anon.post("/api/auth/register", json={"username": "nvk", "password": "matkhau123", "full_name": " Lê Văn K ",
                                              "unit": " P. HCNS ", "phone": " 123 "})
        listed = {u["username"]: u for u in admin.get("/api/users").json()}
        self.assertEqual(listed["nvk"]["full_name"], "Lê Văn K")
        self.assertEqual(listed["nvk"]["register_unit"], "P. HCNS")
        self.assertEqual(listed["nvk"]["register_phone"], "123")
        self.assertEqual(listed["nvk"]["pending_approval"], 1)

    def test_unit_required_and_phone_optional(self):
        self.add_admin()
        anon = TestClient(app_module.app)
        base = {"username": "nvm", "password": "matkhau123", "full_name": "Nguyễn Test"}
        self.assertEqual(anon.post("/api/auth/register", json={**base, "unit": "  "}).status_code, 400)
        self.assertEqual(anon.post("/api/auth/register", json={**base}).status_code, 400)
        self.assertEqual(anon.post("/api/auth/register", json={**base, "unit": "x" * 101}).status_code, 400)
        self.assertEqual(anon.post("/api/auth/register", json={**base, "unit": "P. IT", "phone": "abc"}).status_code, 400)
        self.assertEqual(anon.post("/api/auth/register", json={**base, "unit": "P. IT", "phone": "1"}).status_code, 400)
        self.assertIsNone(self.user("nvm"))
        self.assertEqual(anon.post("/api/auth/register", json={**base, "unit": "Công trình Hà Nội"}).status_code, 200)
        self.assertIsNotNone(self.user("nvm"))

    def test_units_endpoint_is_public_and_names_only(self):
        with db.connect() as c:
            c.execute("INSERT INTO units (id, code, name, unit_type, sort_order) VALUES (1,'HQ','Công ty','board',0)")
            c.execute("INSERT INTO units (id, code, name, unit_type, sort_order) VALUES (4,'K','Khối Vận hành','division',0)")
            c.execute("INSERT INTO units (id, code, name, unit_type, sort_order) VALUES (5,'TGD','Ban Tổng Giám đốc','executive',0)")
            c.execute("INSERT INTO units (id, code, name, full_name, unit_type, sort_order, notes) VALUES (2,'KT','P. Kế toán','Phòng Kế toán','department',2,'ghi chú nội bộ')")
            c.execute("INSERT INTO units (id, code, name, unit_type, sort_order) VALUES (3,'IT','P. IT','department',1)")
        r = TestClient(app_module.app).get("/api/auth/units")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [{"name": "P. IT", "full_name": None, "keywords": "IT"},
                                    {"name": "P. Kế toán", "full_name": "Phòng Kế toán", "keywords": "KT"}])

    def test_units_keywords_include_everyday_names(self):
        with db.connect() as c:
            c.execute("INSERT INTO units (id, code, name, unit_type) VALUES (1,'P-HCNS','P. Hành chính Nhân sự','department')")
        got = TestClient(app_module.app).get("/api/auth/units").json()
        self.assertIn("hcns", got[0]["keywords"].split())

    def test_duplicate_and_weak_input_rejected(self):
        self.add_admin()
        anon = TestClient(app_module.app)
        self.assertEqual(anon.post("/api/auth/register", json={"username": "admin", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"}).status_code, 400)
        self.assertEqual(anon.post("/api/auth/register", json={"username": "nvc", "password": "ngan", "full_name": "Nguyễn Test", "unit": "P. IT"}).status_code, 400)
        self.assertEqual(anon.post("/api/auth/register", json={"username": "   ", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"}).status_code, 400)

    def test_username_format_enforced(self):
        self.add_admin()
        anon = TestClient(app_module.app)
        for bad in ("ab", "nguyễnvăn", "has space", "a" * 33, "x@y.com;"):
            r = anon.post("/api/auth/register", json={"username": bad, "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
            self.assertEqual(r.status_code, 400, bad)
        r = anon.post("/api/auth/register", json={"username": "Nguyen.Van_A-1", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.user("nguyen.van_a-1"))

    def test_register_rate_limited_per_ip(self):
        self.add_admin()
        anon = TestClient(app_module.app)
        for i in range(app_module.REGISTER_MAX_PER_IP):
            r = anon.post("/api/auth/register", json={"username": f"user{i}", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
            self.assertEqual(r.status_code, 200)
        r = anon.post("/api/auth/register", json={"username": "user-extra", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        self.assertEqual(r.status_code, 429)
        self.assertIsNone(self.user("user-extra"))
        other = anon.post("/api/auth/register", headers={"x-forwarded-for": "10.0.0.9"},
                          json={"username": "other-ip", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        self.assertEqual(other.status_code, 200)

    def test_register_blocked_when_too_many_pending(self):
        self.add_admin()
        anon = TestClient(app_module.app)
        with mock.patch.object(app_module, "REGISTER_MAX_PENDING", 2):
            for i in range(2):
                anon.post("/api/auth/register", headers={"x-forwarded-for": f"10.0.1.{i}"},
                          json={"username": f"pend{i}", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
            r = anon.post("/api/auth/register", headers={"x-forwarded-for": "10.0.1.99"},
                          json={"username": "pend-x", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        self.assertEqual(r.status_code, 429)

    def test_approve_assigns_role_unit_and_permissions(self):
        admin = self.add_admin()
        with db.connect() as c:
            c.execute("INSERT INTO units (id, code, name, unit_type) VALUES (1,'HQ','Công ty','board')")
        anon = TestClient(app_module.app)
        anon.post("/api/auth/register", json={"username": "nvd", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        uid = self.user_id("nvd")
        r = admin.post(f"/api/users/{uid}/approve", json={"role": "manager", "unit_id": 1, "features": ["docs_view", "insights"]})
        self.assertEqual(r.status_code, 200)
        u = self.user("nvd")
        self.assertEqual((u["role"], u["active"]), ("manager", 1))
        with db.connect() as c:
            self.assertEqual(c.execute("SELECT pending_approval FROM users WHERE id = ?", (uid,)).fetchone()[0], 0)
            feats = {r[0] for r in c.execute("SELECT feature FROM user_permissions WHERE user_id = ?", (uid,))}
            unit = c.execute("SELECT unit_id FROM users WHERE id = ?", (uid,)).fetchone()[0]
        self.assertEqual(feats, {"docs_view", "insights"})
        self.assertEqual(unit, 1)
        self.assertEqual(anon.post("/api/auth/login", json={"username": "nvd", "password": "matkhau123"}).status_code, 200)

    def test_approve_rejects_invalid_input_and_non_pending(self):
        admin = self.add_admin()
        anon = TestClient(app_module.app)
        anon.post("/api/auth/register", json={"username": "nve", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        uid = self.user_id("nve")
        self.assertEqual(admin.post(f"/api/users/{uid}/approve", json={"role": "superuser"}).status_code, 400)
        self.assertEqual(admin.post(f"/api/users/{uid}/approve", json={"role": "viewer", "features": ["hack"]}).status_code, 400)
        self.assertEqual(admin.post("/api/users/1/approve", json={"role": "viewer"}).status_code, 400)  # admin không chờ duyệt
        self.assertEqual(anon.post(f"/api/users/{uid}/approve", json={"role": "viewer"}).status_code, 401)

    def test_reject_removes_pending_account(self):
        admin = self.add_admin()
        TestClient(app_module.app).post("/api/auth/register", json={"username": "nvf", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        uid = self.user_id("nvf")
        r = admin.request("DELETE", f"/api/users/{uid}", json={"confirm": "nvf"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(self.user("nvf"))

    def test_admin_state_counts_pending_accounts(self):
        admin = self.add_admin()
        anon = TestClient(app_module.app)
        anon.post("/api/auth/register", json={"username": "nvg", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        anon.post("/api/auth/register", json={"username": "nvh", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        self.assertEqual(admin.get("/api/auth/state").json()["user"]["pending_accounts"], 2)

    def test_disabled_account_gets_its_own_message(self):
        admin = self.add_admin()
        anon = TestClient(app_module.app)
        anon.post("/api/auth/register", json={"username": "nvi", "password": "matkhau123", "full_name": "Nguyễn Test", "unit": "P. IT"})
        uid = self.user_id("nvi")
        admin.put(f"/api/users/{uid}", json={"active": 1})
        admin.put(f"/api/users/{uid}", json={"active": 0})
        r = anon.post("/api/auth/login", json={"username": "nvi", "password": "matkhau123"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("đã bị khoá", r.json()["detail"])

    def user_id(self, username):
        with db.connect() as c:
            return c.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()[0]


if __name__ == "__main__":
    unittest.main()
