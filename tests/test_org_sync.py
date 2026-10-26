"""Đồng bộ sơ đồ gốc: bổ sung phòng/chức danh thiếu mà không ghi đè tên đã điền.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_org_sync
"""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import analytics, db, org_sync, seed


class OrgSyncTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(db, "DB_PATH", Path(tmp.name) / "t.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        seed.seed()
        gc.collect()

    def test_restores_missing_unit_and_deputies_without_overwriting(self):
        with db.connect() as conn:
            # Giả lập: mất PM/SM và phó phòng; ô TBA của Khối Vận hành đã được điền tên
            conn.execute("DELETE FROM units WHERE code = 'PMSM'")
            conn.execute("DELETE FROM positions WHERE title_code = 'PP' AND unit_id IN"
                         " (SELECT id FROM units WHERE code IN ('P-HCNS','P-DT','P-CCM'))")
            conn.execute("INSERT INTO employees (full_name) VALUES ('Người Đã Điền')")
            conn.execute("UPDATE positions SET employee_id = (SELECT id FROM employees WHERE full_name='Người Đã Điền')"
                         " WHERE unit_id = (SELECT id FROM units WHERE code='K-VH') AND is_head = 1")

            changes = org_sync.sync(conn)
            self.assertTrue(any("PM/SM" in c for c in changes))
            self.assertEqual(org_sync.sync(conn), [])  # chạy lại không đổi gì

            tree = {u["code"]: u for u in analytics.units_flat(conn)}
            self.assertEqual(tree["K-VH"]["head"]["name"], "Người Đã Điền")
            self.assertEqual(tree["PMSM"]["parent_id"], tree["K-TC"]["id"])
            self.assertEqual([d["name"] for d in tree["P-HCNS"]["deputies"]], ["Võ Văn Cường"])
            self.assertEqual(len(tree["P-CCM"]["deputies"]), 1)  # chỉ Ng. Q. Hải; Trần M. Triết là trưởng đơn vị


if __name__ == "__main__":
    unittest.main()
