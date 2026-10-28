"""Đề xuất cải tiến (API): người tạo chỉ thấy đề xuất của mình; Ban TGĐ/quản trị xem tất cả và đổi tiến trình; ai đăng nhập cũng tạo được.
Quy tắc vòng đời, file đính kèm: xem tests/test_proposal_workflow.py."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db


class ProposalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        self.clients = {}
        with db.connect() as c:
            for uid, name, role in ((1, "ceo", "ceo"), (2, "manager", "manager"), (3, "manager2", "manager"), (4, "viewer", "viewer")):
                c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (?,?,?,'x')", (uid, name, role))
                cl = TestClient(app_module.app)
                cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
                self.clients[name] = cl

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_create_starts_as_new(self):
        r = self.clients["manager"].post("/api/proposals", json={"title": "Gộp hai kho hồ sơ", "body": "Chi tiết"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["status"], r.json()["title"]), ("new", "Gộp hai kho hồ sơ"))

    def test_manager_sees_only_own(self):
        self.clients["manager"].post("/api/proposals", json={"title": "Của A"})
        self.clients["manager2"].post("/api/proposals", json={"title": "Của B"})
        mine = self.clients["manager"].get("/api/proposals").json()
        self.assertEqual([p["title"] for p in mine], ["Của A"])
        self.assertEqual(len(self.clients["ceo"].get("/api/proposals").json()), 2)

    def test_viewer_creates_own_but_sees_only_own(self):
        self.clients["manager"].post("/api/proposals", json={"title": "Của A"})
        self.assertEqual(self.clients["viewer"].get("/api/proposals").json(), [])  # chỉ thấy đề xuất của mình / được giao
        r = self.clients["viewer"].post("/api/proposals", json={"title": "Của viewer"})  # không cần quyền AI để tự nhập đề xuất
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([p["title"] for p in self.clients["viewer"].get("/api/proposals").json()], ["Của viewer"])
        self.assertEqual(self.clients["manager"].get(f"/api/proposals/{r.json()['id']}").status_code, 404)

    def test_archive_endpoint_only_for_boss(self):
        pid = self.clients["viewer"].post("/api/proposals", json={"title": "x"}).json()["id"]
        self.assertEqual(self.clients["viewer"].post(f"/api/proposals/{pid}/archive", json={}).status_code, 403)

    def test_only_ceo_changes_status_and_owner(self):
        pid = self.clients["manager"].post("/api/proposals", json={"title": "x"}).json()["id"]
        self.assertEqual(self.clients["manager"].put(f"/api/proposals/{pid}", json={"status": "in_progress"}).status_code, 403)
        self.assertEqual(self.clients["manager"].put(f"/api/proposals/{pid}", json={"owner_user_id": 3}).status_code, 403)
        r = self.clients["ceo"].put(f"/api/proposals/{pid}", json={"owner_user_id": 3, "note": "Giao HCNS làm", "status": "in_progress"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["status"], r.json()["owner_user_id"], r.json()["note"]), ("in_progress", 3, "Giao HCNS làm"))

    def test_invalid_status_and_empty_title_are_refused(self):
        pid = self.clients["manager"].post("/api/proposals", json={"title": "x"}).json()["id"]
        self.assertEqual(self.clients["ceo"].put(f"/api/proposals/{pid}", json={"status": "xoa_het"}).status_code, 400)
        self.assertEqual(self.clients["manager"].post("/api/proposals", json={"title": "   "}).status_code, 400)

    def test_filter_by_status(self):
        ceo, m = self.clients["ceo"], self.clients["manager"]
        pid = m.post("/api/proposals", json={"title": "a"}).json()["id"]
        m.post("/api/proposals", json={"title": "b"})
        ceo.put(f"/api/proposals/{pid}", json={"status": "dropped", "status_note": "Chưa cần"})
        done = ceo.get("/api/proposals?status=dropped").json()
        self.assertEqual([p["title"] for p in done], ["a"])

    def test_missing_proposal_is_404(self):
        self.assertEqual(self.clients["ceo"].put("/api/proposals/999", json={"status": "dropped", "status_note": "x"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
