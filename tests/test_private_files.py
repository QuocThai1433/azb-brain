"""Kho riêng theo tài khoản: file đính kèm chat chỉ thuộc về chủ, có hạn mức dung lượng và trần lượt đọc AI.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_private_files
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import access, app as app_module, auth, db, documents, privatefiles
from tests.test_security import DbCase

MB = 1024 * 1024


class PrivateFilesCase(DbCase):
    """Thêm: user 4 (manager khác); doc 6 = file riêng của mgrA (id 2), doc 7 = file riêng của ceo (id 1)."""

    def setUp(self):
        super().setUp()
        with db.connect() as c:
            c.execute("INSERT INTO users (id, username, role, unit_id, password_hash) VALUES (4,'mgrB','manager',3,'x')")
            for did, owner, title, text in ((6, 2, "Ảnh riêng của A", "zulu bimatA"), (7, 1, "Ghi chú riêng ceo", "yankee bimatceo")):
                c.execute("INSERT INTO documents (id, unit_id, title, doc_type, filename, stored_path, access_level, owner_id,"
                          " extract_status, content, char_count, size_bytes) VALUES (?,NULL,?,'khac','f.png','','private',?,'ok',?,?,?)",
                          (did, title, owner, text, len(text), 10 * MB))
                c.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) VALUES (?,?,0,1)", (text, did))
            documents.sync_ai_index(c)
        self.mgr2 = {"id": 4, "username": "mgrB", "full_name": None, "role": "manager", "unit_id": 3}

    def visible(self, user, **kw):
        with db.connect() as c:
            return access.visible_doc_ids(c, user, **kw)


class IsolationTest(PrivateFilesCase):
    def test_private_file_visible_only_to_owner(self):
        self.assertIn(6, self.visible(self.mgr))
        for other in (self.mgr2, self.view, self.ceo):
            self.assertNotIn(6, self.visible(other))
        self.assertNotIn(7, self.visible(self.mgr))
        self.assertIn(7, self.visible(self.ceo))

    def test_library_view_excludes_private_even_for_owner(self):
        self.assertNotIn(6, self.visible(self.mgr, include_private=False))

    def test_other_users_cannot_open_by_id(self):
        with db.connect() as c:
            for other in (self.mgr2, self.view, self.ceo):
                self.assertFalse(access.can_view_doc(c, other, 6))
            self.assertTrue(access.can_view_doc(c, self.mgr, 6))

    def test_admin_management_view_is_explicit(self):
        with db.connect() as c:
            self.assertTrue(access.can_view_doc(c, self.ceo, 6, as_admin=True))
            self.assertFalse(access.can_view_doc(c, self.mgr2, 6, as_admin=True))

    def test_get_file_allows_owner_and_exec_only(self):
        with db.connect() as c:
            self.assertEqual(privatefiles.get_file(c, self.mgr, 6)["id"], 6)
            self.assertEqual(privatefiles.get_file(c, self.ceo, 6)["id"], 6)
            for other in (self.mgr2, self.view):
                with self.assertRaises(HTTPException):
                    privatefiles.get_file(c, other, 6)
            with self.assertRaises(HTTPException):  # tài liệu thư viện không phải file riêng
                privatefiles.get_file(c, self.ceo, 1)

    def test_library_write_endpoints_reject_private(self):
        with db.connect() as c:
            for u in (self.mgr, self.ceo):
                with self.assertRaises(HTTPException):
                    access.check_doc_write(c, u, 6)

    def test_ai_search_and_read_respect_owner(self):
        mine = self.tool("search_documents", {"query": "zulu bimatA", "unit_id": 0}, self.mgr)
        self.assertIn("Ảnh riêng của A", json.dumps(mine, ensure_ascii=False))
        for other in (self.mgr2, self.ceo):
            res = self.tool("search_documents", {"query": "zulu bimatA", "unit_id": 0}, other)
            self.assertNotIn("Ảnh riêng của A", json.dumps(res, ensure_ascii=False))
            self.assertIn("error", self.tool("read_document", {"doc_id": 6, "from_chunk": 0}, other))
        self.assertNotIn("error", self.tool("read_document", {"doc_id": 6, "from_chunk": 0}, self.mgr))

    def test_ai_listing_does_not_leak_titles(self):
        listed = self.tool("list_documents", {"unit_id": 0, "kind": "noi_bo"}, self.ceo)
        self.assertNotIn("Ảnh riêng của A", json.dumps(listed, ensure_ascii=False))
        self.assertIn("Ghi chú riêng ceo", json.dumps(listed, ensure_ascii=False))


class QuotaTest(PrivateFilesCase):
    def test_default_quota_and_usage(self):
        with db.connect() as c:
            u = privatefiles.usage(c, self.mgr)
            self.assertEqual((u["quota_mb"], u["used_mb"], u["remaining_mb"]), (300, 10.0, 290.0))

    def test_upload_over_quota_rejected(self):
        with db.connect() as c:
            privatefiles.check_quota(c, self.mgr, 289 * MB)
            with self.assertRaises(HTTPException):
                privatefiles.check_quota(c, self.mgr, 291 * MB)

    def test_admin_can_raise_quota_and_exec_is_unlimited(self):
        with db.connect() as c:
            c.execute("UPDATE users SET quota_mb = 1000 WHERE id = 2")
            privatefiles.check_quota(c, self.mgr, 900 * MB)
            self.assertIsNone(privatefiles.usage(c, self.ceo)["quota_mb"])
            privatefiles.check_quota(c, self.ceo, 10_000 * MB)

    def test_deleting_frees_quota(self):
        with db.connect() as c:
            c.execute("DELETE FROM documents WHERE id = 6")
            self.assertEqual(privatefiles.usage(c, self.mgr)["used_mb"], 0)

    def test_daily_ocr_cap_is_per_user(self):
        with db.connect() as c:
            self.assertTrue(all(privatefiles.ocr_take(c, 2) for _ in range(privatefiles.OCR_DAILY_LIMIT)))
            self.assertFalse(privatefiles.ocr_take(c, 2))
            self.assertTrue(privatefiles.ocr_take(c, 4))


class MigrationTest(PrivateFilesCase):
    def test_old_pasted_images_move_to_uploader_private_store(self):
        with db.connect() as c:
            c.execute("INSERT INTO documents (id, unit_id, title, doc_type, filename, stored_path, access_level, uploaded_by)"
                      " VALUES (20, NULL, 'a', 'khac', 'anh-dan-081632.png', '', 'internal', 2)")
            c.execute("INSERT INTO documents (id, unit_id, title, doc_type, filename, stored_path, access_level, uploaded_by)"
                      " VALUES (21, NULL, 'b', 'khac', 'anh-dan-081443.png', '', 'internal', NULL)")
        db.init_db()
        with db.connect() as c:
            self.assertEqual(tuple(c.execute("SELECT access_level, owner_id FROM documents WHERE id = 20").fetchone()), ("private", 2))
            self.assertEqual(tuple(c.execute("SELECT access_level, owner_id FROM documents WHERE id = 21").fetchone()), ("private", None))
        self.assertNotIn(20, self.visible(self.mgr2))
        self.assertNotIn(21, self.visible(self.ceo))  # chưa rõ chủ: chỉ hiện ở màn "chờ xử lý" của admin


class ApiTest(unittest.TestCase):
    """Gọi API thật (TestClient, database và thư mục upload tạm): tải lên → hạn mức → cô lập → đọc ảnh khi gửi."""

    PNG = b"\x89PNG fake"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(db, "DB_PATH", root / "azb.db"), mock.patch.object(documents, "UPLOAD_DIR", root / "uploads")]
        for p in self.patches:
            p.start()
        (root / "uploads").mkdir()
        db.init_db()
        self.clients = {}
        with db.connect() as c:
            for uid, name, role in ((1, "ceo", "ceo"), (2, "mgrA", "manager"), (3, "mgrB", "manager"), (4, "view", "viewer")):
                c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (?,?,?,'x')", (uid, name, role))
                cl = TestClient(app_module.app)
                cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
                self.clients[name] = cl

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def upload(self, who, name="ghi-chu.txt", data=b"noi dung rieng alpha", ctype="text/plain"):
        return self.clients[who].post("/api/my-files", files={"file": (name, data, ctype)})

    def status(self, fid):
        with db.connect() as c:
            return c.execute("SELECT extract_status FROM documents WHERE id = ?", (fid,)).fetchone()[0]

    def test_upload_list_and_isolation(self):
        r = self.upload("mgrA")
        self.assertEqual(r.status_code, 200, r.text)
        fid = r.json()["id"]
        mine = self.clients["mgrA"].get("/api/my-files").json()
        self.assertEqual([f["id"] for f in mine["files"]], [fid])
        self.assertEqual(mine["files"][0]["extract_status"], "ok")
        self.assertEqual(self.clients["mgrB"].get("/api/my-files").json()["files"], [])
        for method, url in (("get", f"/api/my-files/{fid}"), ("get", f"/api/my-files/{fid}/file"), ("delete", f"/api/my-files/{fid}"),
                            ("post", f"/api/my-files/{fid}/read")):
            self.assertIn(getattr(self.clients["mgrB"], method)(url).status_code, (403, 404), url)
        self.assertEqual(self.clients["view"].get(f"/api/my-files/{fid}").status_code, 404)
        self.assertEqual(self.clients["mgrA"].get(f"/api/my-files/{fid}/file").content, b"noi dung rieng alpha")

    def test_private_files_stay_out_of_library(self):
        fid = self.upload("mgrA").json()["id"]
        listed = self.clients["ceo"].get("/api/documents").json()
        self.assertNotIn(fid, [d["id"] for d in listed])
        self.assertEqual(self.clients["ceo"].get("/api/documents/search", params={"q": "alpha"}).json(), [])

    def test_ceo_can_view_and_it_is_logged_silently(self):
        fid = self.upload("mgrA").json()["id"]
        self.assertEqual(self.clients["ceo"].get(f"/api/my-files/{fid}").status_code, 200)
        with db.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'view_private' AND user_id = 1").fetchone()[0], 1)
        overview = self.clients["ceo"].get("/api/admin/private-files").json()
        self.assertEqual({o["user_id"]: o["files"] for o in overview}[2], 1)
        self.assertEqual(self.clients["mgrA"].get("/api/admin/private-files").status_code, 403)

    def test_quota_blocks_upload_and_admin_can_raise_it(self):
        with db.connect() as c:
            c.execute("UPDATE users SET quota_mb = 1 WHERE id = 2")
        big = b"x" * (2 * MB)
        r = self.upload("mgrA", "to.txt", big)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Không đủ dung lượng", r.json()["detail"])
        with db.connect() as c:
            c.execute("UPDATE users SET quota_mb = 5 WHERE id = 2")
        self.assertEqual(self.upload("mgrA", "to.txt", big).status_code, 200)
        usage = self.clients["mgrA"].get("/api/my-files/meta").json()["usage"]
        self.assertEqual((usage["quota_mb"], usage["used_mb"]), (5, 2.0))
        self.assertIsNone(self.clients["ceo"].get("/api/my-files/meta").json()["usage"]["quota_mb"])

    def test_viewer_cannot_use_private_store(self):
        self.assertEqual(self.upload("view").status_code, 403)

    def test_publish_needs_docs_edit_and_keeps_original(self):
        fid = self.upload("ceo").json()["id"]
        r = self.clients["ceo"].post(f"/api/my-files/{fid}/publish", json={"title": "Bản chung", "access_level": "internal"})
        self.assertEqual(r.status_code, 200, r.text)
        titles = [d["title"] for d in self.clients["ceo"].get("/api/documents").json()]
        self.assertIn("Bản chung", titles)
        self.assertEqual(len(self.clients["ceo"].get("/api/my-files").json()["files"]), 1)
        other = self.upload("mgrA").json()["id"]
        self.assertEqual(self.clients["mgrA"].post(f"/api/my-files/{other}/publish", json={}).status_code, 403)  # chưa được cấp docs_edit

    def test_delete_frees_space(self):
        fid = self.upload("mgrA", "a.txt", b"x" * MB).json()["id"]
        self.assertEqual(self.clients["mgrA"].delete(f"/api/my-files/{fid}").status_code, 200)
        self.assertEqual(self.clients["mgrA"].get("/api/my-files").json()["usage"]["used_mb"], 0)

    def test_images_are_read_only_when_question_is_sent(self):
        fid = self.upload("mgrA", "anh-dan-1.png", self.PNG, "image/png").json()["id"]
        self.assertEqual(self.status(fid), "needs_ocr")
        question = f'[Đính kèm: "anh-dan-1.png" (id tài liệu {fid})]\nTóm tắt ảnh'
        with mock.patch.object(documents, "_read_image", return_value="chữ trong ảnh mẫu") as ocr:
            self.assertEqual(privatefiles.prepare_attachments({"id": 3}, question), [])  # người khác gửi id này: không đọc
            ocr.assert_not_called()
            self.assertEqual(privatefiles.prepare_attachments({"id": 2}, question), [])
            ocr.assert_called_once()
        self.assertEqual(self.status(fid), "ok")

    def test_gemini_quota_error_is_reported_not_raised(self):
        fid = self.upload("mgrA", "anh-dan-2.png", self.PNG, "image/png").json()["id"]

        class Quota(Exception):
            code = 429
        with mock.patch.object(documents, "_read_image", side_effect=Quota("RESOURCE_EXHAUSTED")):
            notes = privatefiles.prepare_attachments({"id": 2}, f"[Đính kèm: x (id tài liệu {fid})]")
        self.assertEqual(len(notes), 1)
        self.assertIn("429", notes[0])
        self.assertNotIn("RESOURCE_EXHAUSTED", notes[0])

    def test_daily_cap_stops_reading(self):
        fid = self.upload("mgrA", "anh-dan-3.png", self.PNG, "image/png").json()["id"]
        with db.connect() as c:
            c.execute("INSERT INTO ocr_usage (user_id, day, n) VALUES (2, date('now','localtime'), ?)", (privatefiles.OCR_DAILY_LIMIT,))
        with mock.patch.object(documents, "_read_image", return_value="x") as ocr:
            notes = privatefiles.prepare_attachments({"id": 2}, f"[Đính kèm: x (id tài liệu {fid})]")
        ocr.assert_not_called()
        self.assertIn("hết", notes[0])
        self.assertEqual(self.clients["mgrA"].post(f"/api/my-files/{fid}/read").status_code, 429)


if __name__ == "__main__":
    unittest.main()
