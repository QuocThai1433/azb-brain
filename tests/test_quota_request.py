"""Xin thêm dung lượng kho riêng qua luồng xin cấp quyền: gửi đơn → admin chỉnh số MB và duyệt → hạn mức tăng."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db, privatefiles


class QuotaRequestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        self.clients = {}
        with db.connect() as c:
            for uid, name, role in ((1, "admin", "admin"), (2, "viewer", "viewer")):
                c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (?,?,?,'x')", (uid, name, role))
                cl = TestClient(app_module.app)
                cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
                self.clients[name] = cl

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def quota(self):
        with db.connect() as c:
            return privatefiles.quota_mb(c, {"id": 2, "role": "viewer"})

    def test_request_needs_something_and_a_reason(self):
        u = self.clients["viewer"]
        self.assertEqual(u.post("/api/access-requests", json={"features": [], "reason": "x"}).status_code, 400)
        self.assertEqual(u.post("/api/access-requests", json={"extra_mb": 500, "reason": " "}).status_code, 400)
        self.assertEqual(u.post("/api/access-requests", json={"extra_mb": -5, "reason": "x"}).status_code, 400)
        self.assertEqual(u.post("/api/access-requests", json={"extra_mb": "abc", "reason": "x"}).status_code, 400)

    def test_approve_adds_to_quota_with_admin_override(self):
        u, a = self.clients["viewer"], self.clients["admin"]
        rid = u.post("/api/access-requests", json={"extra_mb": 500, "reason": "nhiều file scan"}).json()["id"]
        self.assertEqual(self.quota(), privatefiles.DEFAULT_QUOTA_MB)  # chưa duyệt thì chưa đổi
        r = a.post(f"/api/access-requests/{rid}/decide", json={"approve": True, "grant_mb": 200})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.quota(), privatefiles.DEFAULT_QUOTA_MB + 200)
        mine = u.get("/api/access-requests").json()[0]
        self.assertEqual((mine["extra_mb"], mine["granted_mb"], mine["status"]), (500, 200, "approved"))

    def test_approve_defaults_to_requested_and_reject_changes_nothing(self):
        u, a = self.clients["viewer"], self.clients["admin"]
        rid = u.post("/api/access-requests", json={"extra_mb": 100, "reason": "x"}).json()["id"]
        a.post(f"/api/access-requests/{rid}/decide", json={"approve": False, "note": "chưa cần"})
        self.assertEqual(self.quota(), privatefiles.DEFAULT_QUOTA_MB)
        rid = u.post("/api/access-requests", json={"extra_mb": 100, "reason": "x"}).json()["id"]
        a.post(f"/api/access-requests/{rid}/decide", json={"approve": True})
        self.assertEqual(self.quota(), privatefiles.DEFAULT_QUOTA_MB + 100)

    def test_edit_pending_request_can_change_amount(self):
        u = self.clients["viewer"]
        rid = u.post("/api/access-requests", json={"extra_mb": 100, "reason": "x"}).json()["id"]
        self.assertEqual(u.put(f"/api/access-requests/{rid}", json={"extra_mb": 300, "reason": "y"}).status_code, 200)
        self.assertEqual(u.get("/api/access-requests").json()[0]["extra_mb"], 300)


if __name__ == "__main__":
    unittest.main()
