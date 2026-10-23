"""Nghỉ việc (giữ dữ liệu 90 ngày rồi admin duyệt xoá) và xoá file đính kèm khi xoá đoạn chat.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_offboarding
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db, documents, memory, offboarding


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

    def upload(self, who, name="a.txt", data=b"noi dung rieng"):
        return self.clients[who].post("/api/my-files", files={"file": (name, data, "text/plain")}).json()["id"]

    def chat(self, user_id, *file_ids):
        with db.connect() as c:
            cid = c.execute("INSERT INTO conversations (user_id, title) VALUES (?, 't')", (user_id,)).lastrowid
            for f in file_ids:
                c.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, 'user', ?)",
                          (cid, f'[Đính kèm: "a.txt" (id tài liệu {f})]\nTóm tắt'))
                c.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, 'assistant', 'ok')", (cid,))
            if not file_ids:
                c.execute("INSERT INTO chat_messages (conversation_id, role, content) VALUES (?, 'user', 'xin chào')", (cid,))
        return cid

    def one(self, sql, *args):
        with db.connect() as c:
            return c.execute(sql, args).fetchone()[0]


class RetentionClockTest(Case):
    def test_clock_starts_on_lock_and_resets_on_unlock(self):
        admin = self.clients["admin"]
        self.assertIsNone(self.one("SELECT deactivated_at FROM users WHERE id = 3"))
        self.assertEqual(admin.put("/api/users/3", json={"active": 0}).status_code, 200)
        first = self.one("SELECT deactivated_at FROM users WHERE id = 3")
        self.assertIsNotNone(first)
        admin.put("/api/users/3", json={"active": 0, "full_name": "A"})  # khoá lại/sửa tiếp không dời mốc
        self.assertEqual(self.one("SELECT deactivated_at FROM users WHERE id = 3"), first)
        admin.put("/api/users/3", json={"active": 1})
        self.assertIsNone(self.one("SELECT deactivated_at FROM users WHERE id = 3"))

    def test_accounts_locked_before_upgrade_get_a_start_date(self):
        with db.connect() as c:
            c.execute("INSERT INTO users (id, username, role, active, password_hash) VALUES (9,'cu','viewer',0,'x')")
        db.init_db()
        self.assertIsNotNone(self.one("SELECT deactivated_at FROM users WHERE id = 9"))


class PurgeTest(Case):
    def setUp(self):
        super().setUp()
        self.fid = self.upload("nvA")
        self.other = self.upload("nvB")
        with db.connect() as c:
            memory.set_enabled(c, 3, True)
            memory.add_note(c, 3, "Phụ trách mảng đấu thầu miền Nam.", "stated")
            c.execute("INSERT INTO documents (id, title, doc_type, filename, stored_path, access_level, uploaded_by)"
                      " VALUES (500, 'Quy trình chung', 'quy_trinh', 'q.pdf', '', 'internal', 3)")
        self.conv = self.chat(3, self.fid)
        self.clients["admin"].put("/api/users/3", json={"active": 0})

    def age(self, days):
        with db.connect() as c:
            c.execute("UPDATE users SET deactivated_at = datetime('now','localtime', ?) WHERE id = 3", (f"-{days} days",))

    def purge(self, confirm="nvA", who="admin"):
        return self.clients[who].post("/api/admin/offboarding/3/purge", json={"confirm": confirm})

    def test_overview_shows_days_left_and_data(self):
        accounts = self.clients["admin"].get("/api/admin/offboarding").json()["accounts"]
        self.assertEqual(len(accounts), 1)
        a = accounts[0]
        self.assertEqual((a["username"], a["files"], a["notes"], a["conversations"], a["due"]), ("nvA", 1, 1, 1, False))
        self.assertIn(a["days_left"], (89, 90))
        self.age(91)
        self.assertTrue(self.clients["admin"].get("/api/admin/offboarding").json()["accounts"][0]["due"])

    def test_cannot_purge_before_retention_ends(self):
        r = self.purge()
        self.assertEqual(r.status_code, 400)
        self.assertIn("Chưa đủ 90 ngày", r.json()["detail"])
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE owner_id = 3"), 1)

    def test_purge_needs_typed_username(self):
        self.age(100)
        self.assertEqual(self.purge("sai-ten").status_code, 400)
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE owner_id = 3"), 1)

    def test_only_admin_can_approve(self):
        self.age(100)
        self.assertEqual(self.purge(who="ceo").status_code, 403)
        self.assertEqual(self.purge(who="nvB").status_code, 403)

    def test_active_account_is_never_purged(self):
        self.age(100)
        self.clients["admin"].put("/api/users/3", json={"active": 1})
        self.age(100)
        self.assertEqual(self.purge().status_code, 400)

    def test_purge_removes_private_data_only(self):
        self.age(100)
        r = self.purge()
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"files": 1, "notes": 1, "conversations": 1})
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE owner_id = 3"), 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM chat_messages WHERE conversation_id = ?", self.conv), 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM user_memories WHERE user_id = 3"), 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE id = 500"), 1)      # thư viện chung giữ nguyên
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE owner_id = 4"), 1)  # người khác không ảnh hưởng
        self.assertEqual(self.one("SELECT COUNT(*) FROM users WHERE id = 3"), 1)
        self.assertEqual(len(list((self.root / "uploads" / "_trash").glob(f"{self.fid}_*"))), 1)  # file gốc vào thùng rác
        self.assertEqual(self.one("SELECT COUNT(*) FROM audit_log WHERE action = 'purge_user_data'"), 1)
        self.assertEqual(self.clients["admin"].get("/api/admin/offboarding").json()["accounts"], [])
        self.assertEqual(self.purge().status_code, 400)  # hết dữ liệu: không xoá lại

    def test_admin_can_still_view_files_during_retention(self):
        self.assertEqual(self.clients["admin"].get(f"/api/my-files/{self.fid}").status_code, 200)


class ConversationFilesTest(Case):
    def test_lists_only_files_used_in_this_chat_only(self):
        shared, solo = self.upload("nvA", "s.txt"), self.upload("nvA", "solo.txt")
        c1, c2 = self.chat(3, shared, solo), self.chat(3, shared)
        r = self.clients["nvA"].get(f"/api/conversations/{c1}/files").json()
        self.assertEqual([f["id"] for f in r["files"]], [solo])
        self.assertEqual(r["kept"], 1)  # file dùng chung với đoạn chat khác luôn giữ lại
        self.assertEqual(self.clients["nvA"].get(f"/api/conversations/{c2}/files").json()["files"], [])

    def test_delete_chat_keeps_files_by_default(self):
        fid = self.upload("nvA")
        cid = self.chat(3, fid)
        r = self.clients["nvA"].delete(f"/api/conversations/{cid}")
        self.assertEqual(r.json(), {"ok": True, "files_removed": 0})
        self.assertEqual(self.one("SELECT COUNT(*) FROM conversations WHERE id = ?", cid), 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE id = ?", fid), 1)

    def test_delete_chat_can_remove_its_files_and_frees_quota(self):
        shared, solo = self.upload("nvA", "s.txt"), self.upload("nvA", "solo.txt", b"x" * 1024)
        c1, _ = self.chat(3, shared, solo), self.chat(3, shared)
        r = self.clients["nvA"].delete(f"/api/conversations/{c1}", params={"delete_files": True})
        self.assertEqual(r.json()["files_removed"], 1)
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE id = ?", solo), 0)
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE id = ?", shared), 1)
        self.assertEqual(self.one("SELECT COUNT(*) FROM audit_log WHERE action = 'delete_private'"), 1)

    def test_cannot_delete_someone_elses_files_by_naming_them(self):
        theirs = self.upload("nvB")
        cid = self.chat(3, theirs)  # nvA nhắc tới id file của nvB trong chat của mình
        self.assertEqual(self.clients["nvA"].get(f"/api/conversations/{cid}/files").json()["files"], [])
        self.clients["nvA"].delete(f"/api/conversations/{cid}", params={"delete_files": True})
        self.assertEqual(self.one("SELECT COUNT(*) FROM documents WHERE id = ?", theirs), 1)

    def test_other_users_cannot_list_or_delete_conversation(self):
        cid = self.chat(3, self.upload("nvA"))
        self.assertEqual(self.clients["nvB"].get(f"/api/conversations/{cid}/files").status_code, 404)
        self.assertEqual(self.clients["nvB"].delete(f"/api/conversations/{cid}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
