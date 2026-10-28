"""Tổng quan điều hành: bản tin, danh sách cần chú ý và việc không lộ dữ liệu cá nhân.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_overview
"""
import gc
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from backend import db, overview


class OverviewTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        p = mock.patch.object(db, "DB_PATH", Path(tmp.name) / "t.db")
        p.start()
        self.addCleanup(p.stop)
        db.init_db()
        gc.collect()

    def test_empty_database_has_no_alerts_and_no_budget(self):
        with db.connect() as conn:
            ov = overview.executive(conn, date(2026, 10, 28))
        self.assertFalse(ov["budget"]["has_plan"])
        self.assertEqual(ov["attention"], [])
        self.assertEqual(ov["okr"]["total"], 0)
        self.assertIsNone(ov["okr"]["avg_pct"])

    def test_proposals_overdue_and_new_become_alerts(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO users (id, username, full_name, role, password_hash) VALUES (1,'ceo','CEO','ceo','x')")
            conn.execute("INSERT INTO proposals (title, status, created_by, due_date) VALUES ('A','new',1,'2026-10-01')")
            conn.execute("INSERT INTO proposals (title, status, created_by) VALUES ('B','in_progress',1)")
            ov = overview.executive(conn, date(2026, 10, 28))
        self.assertEqual(ov["proposals"]["new"], 1)
        self.assertEqual(ov["proposals"]["overdue"], 1)
        titles = [a["title"] for a in ov["attention"]]
        self.assertTrue(any("quá hạn" in t for t in titles))
        self.assertTrue(any("chờ duyệt" in t for t in titles))
        self.assertEqual(ov["attention"][0]["level"], "red")  # mục khẩn xếp trước
        ranks = [overview.LEVEL_ORDER[a["level"]] for a in ov["attention"]]
        self.assertEqual(ranks, sorted(ranks))

    def test_queue_lists_review_first_then_new_and_caps_at_five(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO users (id, username, full_name, role, password_hash) VALUES (1,'nv','Nhan Vien','viewer','x')")
            for i in range(6):
                conn.execute("INSERT INTO proposals (title, status, created_by) VALUES (?, 'new', 1)", (f"Mới {i}",))
            conn.execute("INSERT INTO proposals (title, status, created_by, owner_user_id) VALUES ('Chờ NT','review',1,1)")
            conn.execute("INSERT INTO proposals (title, status, created_by) VALUES ('Đang làm','in_progress',1)")
            pid = conn.execute("SELECT id FROM proposals WHERE title = 'Chờ NT'").fetchone()[0]
            conn.execute("INSERT INTO proposal_events (proposal_id, kind, to_status, at) VALUES (?, 'status', 'review', '2026-10-20 08:00:00')", (pid,))
            q = overview.executive(conn, date(2026, 10, 28))["proposals"]["queue"]
        self.assertEqual(len(q), 5)
        self.assertEqual(q[0]["title"], "Chờ NT")
        self.assertEqual(q[0]["review_days"], 8)
        self.assertEqual(q[0]["owner_name"], "Nhan Vien")
        self.assertTrue(all(x["status"] in ("new", "review") for x in q))
        self.assertTrue(all(x["review_days"] is None for x in q[1:]))

    def test_okr_without_actuals_is_not_reported_as_zero(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO targets (period, metric, target_value) VALUES ('2026','doanh_thu',100)")
            ov = overview.executive(conn, date(2026, 10, 28))
        self.assertEqual(ov["okr"]["total"], 1)
        self.assertEqual(ov["okr"]["with_data"], 0)
        self.assertIsNone(ov["okr"]["avg_pct"])
        self.assertIn("chưa có số thực hiện", " ".join(b["text"] for b in ov["brief"]))

    def test_okr_behind_target_is_flagged(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO targets (period, metric, target_value, actual_value) VALUES ('2026','doanh_thu',100,10)")
            ov = overview.executive(conn, date(2026, 10, 28))
        self.assertEqual(ov["okr"]["behind"], 1)
        behind = next(a for a in ov["attention"] if "chậm tiến độ" in a["title"])
        self.assertEqual(behind["desc"], "Doanh thu")  # tên hiển thị, không lộ khoá kỹ thuật

    def test_payload_has_no_personal_data(self):
        with db.connect() as conn:
            conn.execute("INSERT INTO employees (full_name, email, phone, employee_code, status, joined_date) "
                         "VALUES ('Nguyen Van A','a@x.vn','0901234567','NV001','active','2026-10-05')")
            ov = overview.executive(conn, date(2026, 10, 28))
        text = json.dumps(ov, ensure_ascii=False)
        for secret in ("a@x.vn", "0901234567", "NV001", "Nguyen Van A"):
            self.assertNotIn(secret, text)
        self.assertEqual(ov["hr"]["joined_month"], 1)


if __name__ == "__main__":
    unittest.main()
