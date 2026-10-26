"""Chỉ dấu kiêm nhiệm: giữ chức ở khối và ở phòng duy nhất của khối đó không tính là kiêm nhiệm."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import analytics, db


class ConcurrentRolesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        db.init_db()
        with db.connect() as c:
            c.executescript("""
                INSERT INTO units (id, code, name, unit_type, parent_id) VALUES
                  (1,'K1','Khối một phòng','division',NULL), (2,'P1','Phòng duy nhất','department',1),
                  (3,'K2','Khối hai phòng','division',NULL), (4,'P2','Phòng A','department',3),
                  (5,'P3','Phòng B','department',3),
                  (6,'K3','Khối ba phòng','division',NULL), (7,'P4','Phòng C','department',6),
                  (8,'P5','Phòng D','department',6), (9,'B1','Bộ phận con','section',8),
                  (10,'P6','Phòng độc lập','department',NULL);
                INSERT INTO employees (id, full_name) VALUES (1,'Hân'), (2,'Bình'), (3,'Thiện'), (4,'Kiêm thật');
                INSERT INTO positions (unit_id, title, title_code, employee_id, is_head) VALUES
                  (1,'Giám đốc Khối','GĐ',1,1), (2,'Giám đốc','GĐ',1,1),
                  (3,'Giám đốc Khối','GĐ',2,1), (4,'Trưởng phòng','TP',2,1),
                  (6,'Giám đốc Khối','GĐ',3,1), (7,'Giám đốc','GĐ',3,1), (9,'Trưởng bộ phận','TBP',3,1),
                  (4,'Trưởng phòng','TP',4,1), (10,'Trưởng phòng','TP',4,1);
            """)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_sole_child_is_not_concurrent_but_multi_child_is(self):
        with db.connect() as c:
            names = [x["name"] for x in analytics.insights(c)["concurrent_roles"]]
        self.assertNotIn("Hân", names)

    def test_head_of_division_and_its_departments_is_not_concurrent(self):
        with db.connect() as c:
            names = [x["name"] for x in analytics.insights(c)["concurrent_roles"]]
        self.assertNotIn("Bình", names)   # Giám đốc Khối + Trưởng phòng trong khối
        self.assertNotIn("Thiện", names)  # cả phòng con và bộ phận cháu trong khối
        self.assertIn("Kiêm thật", names)  # hai nhánh tách biệt: P. A (khối 2) và phòng độc lập


if __name__ == "__main__":
    unittest.main()
