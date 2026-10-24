"""Xoá hẳn tài khoản: admin và Ban TGĐ (ceo) xoá được tài khoản khác, không xoá chính mình hay admin đang hoạt động cuối cùng.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_delete_user
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
        self.clients = {}
        with db.connect() as c:
            for uid, name, role in ((1, "admin", "admin"), (2, "ceo", "ceo"), (3, "nvA", "manager"), (4, "nvB", "manager")):
                c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (?,?,?,'x')", (uid, name, role))
                cl = TestClient(app_module.app)
                cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
                self.clients[name] = cl

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def one(self, sql, *args):
        with db.connect() as c:
            return c.execute(sql, args).fetchone()[0]

    def add_user(self, uid, name, role, active=1):
        with db.connect() as c:
            c.execute("INSERT INTO users (id, username, role, password_hash, active) VALUES (?,?,?,'x',?)", (uid, name, role, active))

    def delete(self, who, target, confirm):
        return self.clients[who].request("DELETE", f"/api/users/{target}", json={"confirm": confirm})


class DeleteUserTest(Case):
    def test_admin_deletes_active_account(self):
        r = self.delete("admin", 4, "nvB")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.one("SELECT COUNT(*) FROM users WHERE id = 4"), 0)

    def test_deleting_active_account_also_ends_its_sessions(self):
        self.delete("admin", 4, "nvB")
        self.assertEqual(self.one("SELECT COUNT(*) FROM sessions WHERE user_id = 4"), 0)

    def test_ceo_can_delete_admin_account(self):
        self.add_user(5, "admin2", "admin")
        r = self.delete("ceo", 5, "admin2")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.one("SELECT COUNT(*) FROM users WHERE id = 5"), 0)

    def test_admin_can_delete_ceo_account(self):
        self.add_user(6, "ceo2", "ceo")
        r = self.delete("admin", 6, "ceo2")
        self.assertEqual(r.status_code, 200, r.text)

    def test_wrong_confirmation_is_refused(self):
        r = self.delete("admin", 4, "nvX")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.one("SELECT COUNT(*) FROM users WHERE id = 4"), 1)

    def test_cannot_delete_self(self):
        r = self.delete("admin", 1, "admin")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.one("SELECT COUNT(*) FROM users WHERE id = 1"), 1)

    def test_cannot_delete_last_active_admin(self):
        # ceo xoá admin đang hoạt động cuối cùng thì bị chặn
        r = self.delete("ceo", 1, "admin")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.one("SELECT COUNT(*) FROM users WHERE id = 1"), 1)

    def test_locked_admin_does_not_count_as_active_admin(self):
        # admin khác đã khoá không đủ điều kiện: admin đang hoạt động vẫn là cuối cùng
        self.add_user(5, "admin2", "admin", active=0)
        r = self.delete("ceo", 1, "admin")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.one("SELECT COUNT(*) FROM users WHERE id = 1"), 1)

    def test_manager_cannot_delete(self):
        r = self.delete("nvA", 4, "nvB")
        self.assertIn(r.status_code, (401, 403))
        self.assertEqual(self.one("SELECT COUNT(*) FROM users WHERE id = 4"), 1)

    def test_private_files_removed_shared_docs_kept(self):
        with db.connect() as c:
            c.execute("INSERT INTO documents (id, title, filename, stored_path, access_level, owner_id, uploaded_by) "
                      "VALUES (10, 'rieng', 'a.txt', 'nope/a.txt', 'private', 4, 4)")
            c.execute("INSERT INTO documents (id, title, filename, stored_path, access_level, owner_id, uploaded_by) "
                      "VALUES (11, 'chung', 'b.txt', 'nope/b.txt', 'internal', 4, 4)")
        r = self.delete("admin", 4, "nvB")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE id = 10"), 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE id = 11"), 1)
        self.assertIsNone(self.one("SELECT owner_id FROM documents WHERE id = 11"))

    def test_deletion_is_logged(self):
        self.delete("admin", 4, "nvB")
        self.assertEqual(self.one("SELECT COUNT(*) FROM audit_log WHERE action = 'delete_user' AND entity_id = 4"), 1)


if __name__ == "__main__":
    unittest.main()
