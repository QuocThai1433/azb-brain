"""Lịch sử thay đổi: sửa sơ đồ/nhân sự ghi lại trường đổi từ gì sang gì; thông tin cá nhân chỉ ghi tên trường; chỉ Ban TGĐ/quản trị xem."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend import app as app_module, auth, db


class ChangeHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        self.clients = {}
        with db.connect() as c:
            c.execute("INSERT INTO units (id, code, name, unit_type) VALUES (1, 'P-A', 'Phòng A', 'department')")
            c.execute("INSERT INTO employees (id, full_name, phone, email) VALUES (1, 'Nguyễn Văn A', '0900000000', 'a@azb.vn')")
            for uid, name, role in ((1, "ceo", "ceo"), (2, "manager", "manager")):
                c.execute("INSERT INTO users (id, username, role, password_hash) VALUES (?,?,?,'x')", (uid, name, role))
                cl = TestClient(app_module.app)
                cl.cookies.set(auth.SESSION_COOKIE, auth.create_session(c, uid))
                self.clients[name] = cl

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def _unit_name(self):
        with db.connect() as c:
            return c.execute("SELECT name FROM units WHERE id = 1").fetchone()[0]

    def test_unit_rename_records_old_and_new_value(self):
        r = self.clients["ceo"].put("/api/units/1", json={"name": "Phòng A mới"})
        self.assertEqual(r.status_code, 200, r.text)
        out = self.clients["ceo"].get("/api/change-history").json()
        self.assertEqual(out[0]["action"], "update")
        self.assertEqual(out[0]["name"], "Phòng A mới")
        self.assertEqual(out[0]["changes"], {"name": ["Phòng A", "Phòng A mới"]})

    def test_sensitive_fields_are_masked(self):
        self.clients["ceo"].put("/api/employees/1", json={"phone": "0911111111", "full_name": "Nguyễn Văn A"})
        out = self.clients["ceo"].get("/api/change-history").json()
        changes = out[0]["changes"]
        self.assertEqual(changes, {"phone": ["(đã ẩn)", "(đã ẩn)"]})  # không lộ số điện thoại cũ/mới
        self.assertNotIn("0900000000", json.dumps(out, ensure_ascii=False))
        self.assertNotIn("0911111111", json.dumps(out, ensure_ascii=False))

    def test_no_change_writes_no_log(self):
        self.clients["ceo"].put("/api/units/1", json={"name": "Phòng A"})  # giá trị không đổi
        self.assertEqual(self.clients["ceo"].get("/api/change-history").json(), [])

    def test_same_value_in_other_type_is_not_a_change(self):
        ceo = self.clients["ceo"]
        t = ceo.post("/api/targets", json={"unit_id": 1, "period": "2026", "metric": "dt", "target_value": 5}).json()
        ceo.put(f"/api/targets/{t['id']}", json={"unit_id": "1", "target_value": "5", "actual_value": 3})  # form gửi chuỗi
        out = ceo.get("/api/change-history").json()
        self.assertEqual(set(out[0]["changes"]), {"actual_value"})

    def test_delete_keeps_name(self):
        ceo = self.clients["ceo"]
        t = ceo.post("/api/targets", json={"unit_id": 1, "period": "2026", "metric": "dt", "metric_name": "Doanh thu", "target_value": 5}).json()
        ceo.delete(f"/api/targets/{t['id']}")
        self.assertEqual(ceo.get("/api/change-history").json()[0]["name"], "Doanh thu 2026")

    def test_page_filters_and_total(self):
        ceo = self.clients["ceo"]
        for i in range(3):
            ceo.post("/api/targets", json={"unit_id": 1, "period": f"2026-0{i + 1}", "metric": "dt", "metric_name": f"Chỉ tiêu {i}"})
        ceo.put("/api/units/1", json={"name": "Phòng A mới"})
        page = ceo.get("/api/change-history/page?limit=2").json()
        self.assertEqual((page["total"], len(page["items"])), (4, 2))
        self.assertEqual(len(ceo.get("/api/change-history/page?limit=2&offset=2").json()["items"]), 2)
        self.assertEqual(ceo.get("/api/change-history/page?action=update").json()["total"], 1)
        self.assertEqual(ceo.get("/api/change-history/page?q=Chỉ tiêu 1").json()["total"], 1)
        self.assertEqual(ceo.get("/api/change-history/page?q=%25").json()["total"], 0)  # % không phải ký tự đại diện
        self.assertEqual(ceo.get("/api/change-history/page?date_from=2999-01-01").json()["total"], 0)
        self.assertEqual(ceo.get("/api/change-history/page?user_id=1").json()["total"], 4)
        self.assertEqual(ceo.get("/api/change-history/page?user_id=2").json()["total"], 0)

    def test_unit_names_resolved_for_references(self):
        ceo = self.clients["ceo"]
        ceo.post("/api/units", json={"code": "P-B", "name": "Phòng B", "unit_type": "department"})
        ceo.put("/api/employees/1", json={"unit_id": 1})
        page = ceo.get("/api/change-history/page").json()
        self.assertEqual(page["refs"]["units"], {"1": "Phòng A"})

    def test_export_xlsx(self):
        ceo = self.clients["ceo"]
        ceo.put("/api/units/1", json={"name": "Phòng A mới"})
        r = ceo.get("/api/change-history/export")
        self.assertEqual(r.status_code, 200)
        import io
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
        text = " ".join(str(c.value) for row in ws.iter_rows() for c in row)
        self.assertIn("Phòng A → Phòng A mới", text)
        self.assertIn("Tên: ", text)
        self.assertEqual(self.clients["manager"].get("/api/change-history/export").status_code, 403)

    def test_undo_update(self):
        ceo = self.clients["ceo"]
        ceo.put("/api/units/1", json={"name": "Phòng A mới"})
        log = ceo.get("/api/change-history/page").json()["items"][0]
        self.assertTrue(log["can_undo"])
        self.assertEqual(ceo.post(f"/api/change-history/{log['id']}/undo").status_code, 200)
        self.assertEqual(self._unit_name(), "Phòng A")
        items = ceo.get("/api/change-history/page").json()["items"]
        self.assertEqual(items[0]["changes"], {"name": ["Phòng A mới", "Phòng A"]})  # việc hoàn tác cũng được ghi lại
        self.assertTrue(items[1]["undone"])
        self.assertEqual(ceo.post(f"/api/change-history/{log['id']}/undo").status_code, 409)  # không hoàn tác hai lần

    def test_undo_update_refused_when_edited_again(self):
        ceo = self.clients["ceo"]
        ceo.put("/api/units/1", json={"name": "B"})
        first = ceo.get("/api/change-history/page").json()["items"][0]["id"]
        ceo.put("/api/units/1", json={"name": "C"})
        self.assertEqual(ceo.post(f"/api/change-history/{first}/undo").status_code, 409)
        self.assertEqual(self._unit_name(), "C")

    def test_undo_delete_and_create_of_target(self):
        ceo = self.clients["ceo"]
        t = ceo.post("/api/targets", json={"unit_id": 1, "period": "2026", "metric": "dt", "target_value": 7}).json()
        ceo.delete(f"/api/targets/{t['id']}")
        deleted = ceo.get("/api/change-history/page").json()["items"][0]
        self.assertEqual(ceo.post(f"/api/change-history/{deleted['id']}/undo").status_code, 200)
        with db.connect() as c:
            back = c.execute("SELECT id, target_value FROM targets WHERE id = ?", (t["id"],)).fetchone()
        self.assertEqual((back["id"], back["target_value"]), (t["id"], 7))
        restored = ceo.get("/api/change-history/page").json()["items"][0]
        self.assertEqual(restored["action"], "create")  # khôi phục được ghi như một lần thêm
        self.assertEqual(ceo.post(f"/api/change-history/{restored['id']}/undo").status_code, 200)  # và hoàn tác lại được
        with db.connect() as c:
            self.assertIsNone(c.execute("SELECT id FROM targets WHERE id = ?", (t["id"],)).fetchone())

    def test_undo_not_allowed_for_units_delete_or_viewer_roles(self):
        ceo = self.clients["ceo"]
        new = ceo.post("/api/units", json={"code": "P-B", "name": "Phòng B", "unit_type": "department"}).json()
        ceo.delete(f"/api/units/{new['id']}")
        deleted = ceo.get("/api/change-history/page").json()["items"][0]
        self.assertFalse(deleted["can_undo"])
        self.assertEqual(ceo.post(f"/api/change-history/{deleted['id']}/undo").status_code, 400)
        self.assertEqual(self.clients["manager"].post(f"/api/change-history/{deleted['id']}/undo").status_code, 403)

    def test_sensitive_values_not_in_page_response(self):
        self.clients["ceo"].put("/api/employees/1", json={"phone": "0911111111"})
        page = self.clients["ceo"].get("/api/change-history/page").json()
        self.assertNotIn("0911111111", json.dumps(page, ensure_ascii=False))
        self.assertNotIn("snapshot", json.dumps(page))

    def test_create_and_delete_are_listed(self):
        ceo = self.clients["ceo"]
        new = ceo.post("/api/units", json={"code": "P-B", "name": "Phòng B", "unit_type": "department"}).json()
        ceo.delete(f"/api/units/{new['id']}")
        actions = [x["action"] for x in ceo.get("/api/change-history").json()]
        self.assertEqual(actions, ["delete", "create"])

    def test_target_is_named_by_metric_and_period(self):
        self.clients["ceo"].post("/api/targets", json={"unit_id": 1, "period": "2026-10", "metric": "doanh_thu", "target_value": 5})
        out = self.clients["ceo"].get("/api/change-history?entity=targets").json()
        self.assertEqual(out[0]["name"], "doanh_thu 2026-10")

    def test_only_ceo_and_admin_can_view(self):
        self.assertEqual(self.clients["manager"].get("/api/change-history").status_code, 403)

    def test_entity_filter(self):
        self.clients["ceo"].put("/api/units/1", json={"name": "X"})
        self.clients["ceo"].put("/api/employees/1", json={"full_name": "Y"})
        out = self.clients["ceo"].get("/api/change-history?entity=units").json()
        self.assertEqual({x["entity"] for x in out}, {"units"})

    def test_change_detail_helper(self):
        from backend.app import _change_detail
        self.assertIsNone(_change_detail({"a": 1}, {"a": 1}))
        self.assertEqual(json.loads(_change_detail({"a": 1, "b": None}, {"a": 2, "b": None})), {"a": [1, 2]})


if __name__ == "__main__":
    unittest.main()
