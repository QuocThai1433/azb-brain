"""Quyền cấp riêng: dùng trợ lý AI, xoá tài liệu, tải file gốc (tách khỏi vai trò / docs_edit / docs_view).

Chạy từ thư mục gốc dự án: python -m unittest tests.test_feature_permissions
"""
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db, documents
from tests.test_security import DbCase


class FeaturePermissionsCase(DbCase):
    def setUp(self):
        super().setUp()
        self.upload_patch = mock.patch.object(documents, "UPLOAD_DIR", documents.UPLOAD_DIR.__class__(self.tmp.name) / "uploads")
        self.upload_patch.start()
        documents.UPLOAD_DIR.mkdir(exist_ok=True)
        self.file = documents.UPLOAD_DIR / "f1.txt"
        self.file.write_text("noi dung", encoding="utf-8")
        with db.connect() as c:
            c.execute("UPDATE documents SET stored_path = ? WHERE id = 1", (str(self.file),))

    def tearDown(self):
        self.upload_patch.stop()
        super().tearDown()

    def grant(self, uid, *features):
        with db.connect() as c:
            c.execute("DELETE FROM user_permissions WHERE user_id = ?", (uid,))
            c.executemany("INSERT INTO user_permissions (user_id, feature) VALUES (?,?)", [(uid, f) for f in features])

    def client(self, uid):
        cl = TestClient(app_module.app)
        with db.connect() as c:
            cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
        return cl


class AiUseTest(FeaturePermissionsCase):
    def test_viewer_needs_ai_use(self):
        cl = self.client(3)
        self.assertEqual(cl.get("/api/conversations").status_code, 403)
        self.grant(3, "ai_use")
        self.assertEqual(cl.get("/api/conversations").status_code, 200)
        self.assertTrue(cl.get("/api/auth/state").json()["user"]["can_use_ai"])

    def test_manager_keeps_ai_without_grant(self):
        self.assertEqual(self.client(2).get("/api/conversations").status_code, 200)

    def test_ai_use_does_not_widen_admin_endpoints(self):
        self.grant(3, "ai_use")
        cl = self.client(3)
        self.assertEqual(cl.get("/api/users").status_code, 403)
        self.assertEqual(cl.get("/api/admin/private-files").status_code, 403)


class DocsDownloadTest(FeaturePermissionsCase):
    def test_download_needs_docs_download_but_inline_view_does_not(self):
        self.grant(2, "docs_view")
        cl = self.client(2)
        self.assertEqual(cl.get("/api/documents/1/file").status_code, 403)
        self.assertEqual(cl.get("/api/documents/1/file", params={"inline": 1}).status_code, 200)
        self.grant(2, "docs_view", "docs_download")
        self.assertEqual(cl.get("/api/documents/1/file").status_code, 200)

    def test_download_still_filtered_by_confidentiality(self):
        self.grant(2, "docs_view", "docs_download")
        self.assertEqual(self.client(2).get("/api/documents/4/file").status_code, 404)  # tài liệu mật của phòng khác


class DocsDeleteTest(FeaturePermissionsCase):
    def test_docs_edit_alone_cannot_delete(self):
        self.grant(2, "docs_edit")
        self.assertEqual(self.client(2).delete("/api/documents/1").status_code, 403)
        self.assertTrue(self.file.exists())

    def test_docs_delete_moves_file_to_trash(self):
        self.grant(2, "docs_view", "docs_delete")
        self.assertEqual(self.client(2).delete("/api/documents/1").status_code, 200)
        self.assertFalse(self.file.exists())
        self.assertTrue((documents.UPLOAD_DIR / "_trash" / "f1.txt").exists())


class ImpliedViewTest(FeaturePermissionsCase):
    def test_edit_delete_download_imply_view(self):
        for feature in ("docs_edit", "docs_delete", "docs_download"):
            with db.connect() as c:
                c.execute("DELETE FROM user_permissions WHERE user_id = 2")
                c.execute("INSERT INTO user_permissions (user_id, feature) VALUES (2, ?)", (feature,))
                perms = auth.effective_permissions(c, self.mgr)
            self.assertIn("docs_view", perms, feature)

    def test_unrelated_features_do_not_imply_view(self):
        self.grant(2, "insights", "ai_use")
        with db.connect() as c:
            self.assertNotIn("docs_view", auth.effective_permissions(c, self.mgr))


class MigrationTest(FeaturePermissionsCase):
    def test_existing_grants_carry_over_once(self):
        self.grant(2, "docs_view", "docs_edit")
        self.grant(3, "insights")
        with db.connect() as c:
            c.execute("PRAGMA user_version = 0")
        db.init_db()
        with db.connect() as c:
            got = lambda uid: {r[0] for r in c.execute("SELECT feature FROM user_permissions WHERE user_id = ?", (uid,))}
            self.assertEqual(got(2), {"docs_view", "docs_edit", "docs_delete", "docs_download"})
            self.assertEqual(got(3), {"insights"})
            c.execute("DELETE FROM user_permissions WHERE user_id = 2 AND feature = 'docs_delete'")
        db.init_db()  # admin đã thu hồi thì khởi động lại không cấp lại
        with db.connect() as c:
            self.assertNotIn("docs_delete", {r[0] for r in c.execute("SELECT feature FROM user_permissions WHERE user_id = 2")})
