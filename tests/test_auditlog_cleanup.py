"""Dọn nhật ký: bỏ ảnh chụp hoàn tác quá hạn, lưu trữ rồi xoá dòng quá cũ; chỉ admin; có kiểm tra giới hạn."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db


class AuditCleanupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        self.clients = {}
        with db.connect() as c:
            c.execute("INSERT INTO units (id, code, name, unit_type) VALUES (1, 'P-A', 'Phòng A', 'department')")
            for uid, name, role in ((1, "admin", "admin"), (2, "ceo", "ceo")):
                c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (?,?,?,'x')", (uid, name, role))
                cl = TestClient(app_module.app)
                cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
                self.clients[name] = cl
            # 1 dòng mới, 1 dòng 200 ngày (có snapshot), 1 dòng 800 ngày (có snapshot)
            for days, label in ((1, "moi"), (200, "cu"), (800, "rat-cu")):
                c.execute("INSERT INTO audit_log (ts, action, entity, entity_id, detail, user_id, label, snapshot)"
                          " VALUES (datetime('now','localtime',?), 'update', 'units', 1, '{}', 1, ?, '{\"name\":\"x\"}')", (f"-{days} days", label))

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def _labels(self):
        with db.connect() as c:
            return {r[0]: r[1] for r in c.execute("SELECT label, snapshot IS NOT NULL FROM audit_log WHERE label IS NOT NULL")}

    def test_preview_counts(self):
        p = self.clients["admin"].get("/api/change-history/cleanup-preview").json()
        self.assertEqual((p["snapshots_to_drop"], p["rows_to_archive"]), (2, 1))

    def test_cleanup_tiers(self):
        r = self.clients["admin"].post("/api/change-history/cleanup", json={})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["snapshots_dropped"], r.json()["rows_archived"]), (1, 1))
        self.assertEqual(self._labels(), {"moi": 1, "cu": 0})  # dòng 800 ngày đã xoá, dòng 200 ngày mất snapshot, dòng mới còn nguyên
        files = list((Path(self.tmp.name) / "archive").glob("*.xlsx"))
        self.assertEqual(len(files), 1)

    def test_only_admin_and_limits(self):
        self.assertEqual(self.clients["ceo"].post("/api/change-history/cleanup", json={}).status_code, 403)
        self.assertEqual(self.clients["ceo"].get("/api/change-history/cleanup-preview").status_code, 403)
        self.assertEqual(self.clients["admin"].post("/api/change-history/cleanup", json={"snapshot_days": 5}).status_code, 400)
        self.assertEqual(self.clients["admin"].post("/api/change-history/cleanup", json={"snapshot_days": 400, "archive_days": 400}).status_code, 400)
        self.assertEqual(len(self._labels()), 3)  # bị từ chối thì không mất gì


if __name__ == "__main__":
    unittest.main()
