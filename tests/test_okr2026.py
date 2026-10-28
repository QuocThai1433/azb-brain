import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db, okr2026


class Okr2026Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        self.clients = {}
        with db.connect() as c:
            for uid, name, role in ((1, "ceo", "ceo"), (2, "manager", "manager"), (3, "viewer", "viewer")):
                c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (?,?,?,'x')", (uid, name, role))
                cl = TestClient(app_module.app)
                cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
                self.clients[name] = cl

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def _import(self):
        with db.connect() as c:
            return okr2026.import_okr_2026(c)

    def test_import_matches_sample_and_is_idempotent(self):
        self.assertEqual(self._import(), {"targets": 9, "action_programs": 5})
        self.assertEqual(self._import(), {"targets": 0, "action_programs": 0})
        with db.connect() as c:
            t = {r["metric"]: r for r in c.execute("SELECT * FROM targets WHERE metric != 'khac'")}
            self.assertEqual(t["doanh_so"]["target_value"], 3_168e9)
            self.assertEqual(t["doanh_thu"]["target_value"], 2_568e9)
            self.assertEqual(t["okr_du_an"]["target_value"], 90)
            self.assertTrue(all(r["unit_id"] is None and r["actual_value"] is None for r in c.execute("SELECT * FROM targets")))
            pct = sorted(r["target_value"] for r in c.execute("SELECT * FROM targets WHERE metric = 'khac'"))
            self.assertEqual(pct, [1, 2, 90, 90, 100, 100])
            poa = c.execute("SELECT code, owner, start_date, end_date FROM action_programs ORDER BY sort_order").fetchall()
            self.assertEqual([p["code"] for p in poa], [f"POA 0{i}" for i in range(1, 6)])
            self.assertEqual([p["owner"] for p in poa], ["Ban Dự án"] * 3 + ["Ban T&D", "Toàn công ty"])
            self.assertTrue(all(p["start_date"] == "2026-01-02" and p["end_date"] == "2026-12-31" for p in poa))

    def test_programs_read_by_all_write_by_exec_only(self):
        self._import()
        for who in ("ceo", "manager", "viewer"):
            r = self.clients[who].get("/api/action-programs?year=2026")
            self.assertEqual(len(r.json()), 5, who)
        body = {"year": "2026", "code": "POA 06", "name": "Chương trình thử"}
        self.assertEqual(self.clients["manager"].post("/api/action_programs", json=body).status_code, 403)
        self.assertEqual(self.clients["viewer"].post("/api/action_programs", json=body).status_code, 403)
        created = self.clients["ceo"].post("/api/action_programs", json=body)
        self.assertEqual(created.status_code, 200)
        pid = created.json()["id"]
        self.assertEqual(created.json()["status"], "doing")
        upd = self.clients["ceo"].put(f"/api/action_programs/{pid}", json={"status": "done", "progress": 100})
        self.assertEqual(upd.json()["status"], "done")
        self.assertEqual(self.clients["manager"].delete(f"/api/action_programs/{pid}").status_code, 403)
        self.assertEqual(self.clients["ceo"].delete(f"/api/action_programs/{pid}").status_code, 200)

    def test_targets_visible_to_ceo(self):
        self._import()
        items = self.clients["ceo"].get("/api/targets/progress?period=2026").json()["items"]
        self.assertEqual(len(items), 9)
        self.assertEqual(self.clients["ceo"].get("/api/targets/progress?period=2026").json()["summary"]["no_data"], 9)


if __name__ == "__main__":
    unittest.main()
