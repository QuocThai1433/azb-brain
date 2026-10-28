"""Đề xuất cải tiến: giao việc, quy tắc chuyển trạng thái, file kết quả và quyền xem.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_proposals
"""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from backend import db, documents, proposals


class ProposalWorkflowTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        for p in (mock.patch.object(db, "DB_PATH", Path(tmp.name) / "t.db"),
                  mock.patch.object(documents, "UPLOAD_DIR", Path(tmp.name) / "uploads")):
            p.start()
            self.addCleanup(p.stop)
        db.init_db()
        with db.connect() as conn:
            for i, (name, role) in enumerate((("ceo", "ceo"), ("nv", "viewer"), ("khac", "viewer")), 1):
                conn.execute("INSERT INTO users (id, username, full_name, role, password_hash) VALUES (?,?,?,?,'x')", (i, name, name.upper(), role))
        self.ceo, self.nv, self.other = ({"id": i, "role": r} for i, r in ((1, "ceo"), (2, "viewer"), (3, "viewer")))
        gc.collect()

    def fail(self, fn, *a, code=None, **kw):
        with self.assertRaises(HTTPException) as cm:
            fn(*a, **kw)
        if code:
            self.assertEqual(cm.exception.status_code, code)
        return cm.exception.detail

    def new(self, conn, assign=True):
        pid = proposals.create(conn, self.nv, "Cải tiến A", "nội dung")["id"]
        if assign:
            proposals.update(conn, self.ceo, pid, {"owner_user_id": 2, "due_date": "2026-12-31", "priority": "high"})
        return pid

    def test_full_lifecycle_needs_result_file(self):
        with db.connect() as conn:
            pid = self.new(conn)
            proposals.update(conn, self.ceo, pid, {"status": "in_progress"})
            self.assertIn("file kết quả", self.fail(proposals.update, conn, self.nv, pid, {"status": "review"}, code=400))
            proposals.add_file(conn, self.nv, pid, "result", "ketqua.pdf", b"%PDF-1")
            proposals.update(conn, self.nv, pid, {"status": "review"})
            self.fail(proposals.update, conn, self.nv, pid, {"status": "done"}, code=403)  # chỉ Ban TGĐ nghiệm thu
            proposals.update(conn, self.ceo, pid, {"status": "done"})
            d = proposals.detail(conn, self.ceo, pid)
            self.assertEqual([e["to_status"] for e in d["events"] if e["kind"] == "status"], ["in_progress", "review", "done"])
            self.assertEqual(d["owner_name"], "NV")

    def test_assign_before_approve_and_dropped_needs_reason(self):
        with db.connect() as conn:
            pid = self.new(conn, assign=False)
            self.assertIn("người phụ trách", self.fail(proposals.update, conn, self.ceo, pid, {"status": "in_progress"}))
            self.assertIn("lý do", self.fail(proposals.update, conn, self.ceo, pid, {"status": "dropped"}))
            proposals.update(conn, self.ceo, pid, {"status": "dropped", "status_note": "Chưa cần"})
            self.assertEqual(proposals.detail(conn, self.ceo, pid)["status"], "dropped")

    def test_invalid_transition_and_roles(self):
        with db.connect() as conn:
            pid = self.new(conn)
            self.fail(proposals.update, conn, self.ceo, pid, {"status": "done"}, code=400)  # Mới → Hoàn thành
            self.fail(proposals.update, conn, self.nv, pid, {"status": "in_progress"}, code=403)  # người phụ trách không tự duyệt / tự bắt đầu
            self.fail(proposals.update, conn, self.nv, pid, {"owner_user_id": 3}, code=403)
            self.fail(proposals.update, conn, self.ceo, pid, {"due_date": "31/12/2026"}, code=400)

    def test_visibility(self):
        with db.connect() as conn:
            pid = self.new(conn)
            self.fail(proposals.detail, conn, self.other, pid, code=404)
            self.assertEqual(proposals.list_proposals(conn, self.other), [])
            self.assertEqual(len(proposals.list_proposals(conn, self.nv)), 1)
            self.assertEqual(len(proposals.list_proposals(conn, self.ceo)), 1)
            self.assertEqual(len(proposals.list_proposals(conn, self.ceo, mine=True)), 0)
            self.fail(proposals.add_file, conn, self.other, pid, "ref", "a.pdf", b"x", code=404)

    def test_file_rules_and_trash(self):
        with db.connect() as conn:
            pid = self.new(conn)
            self.fail(proposals.add_file, conn, self.nv, pid, "ref", "virus.exe", b"x", code=400)
            self.fail(proposals.add_file, conn, self.nv, pid, "ref", "a.pdf", b"", code=400)
            ref = proposals.add_file(conn, self.nv, pid, "ref", "tham-khao.pdf", b"abc")
            self.fail(proposals.delete_file, conn, self.ceo, pid, 999, code=404)
            stored = Path(proposals.get_file(conn, self.nv, pid, ref)["stored_path"])
            self.assertTrue(stored.is_file())
            proposals.delete_file(conn, self.nv, pid, ref)
            self.assertFalse(stored.exists())
            self.assertTrue((documents.UPLOAD_DIR / "_trash" / stored.name).is_file())  # chỉ chuyển vào thùng rác
            self.assertEqual(proposals.detail(conn, self.ceo, pid)["files"], [])

    def test_cannot_delete_last_result_while_in_review(self):
        with db.connect() as conn:
            pid = self.new(conn)
            proposals.update(conn, self.ceo, pid, {"status": "in_progress"})
            fid = proposals.add_file(conn, self.nv, pid, "result", "kq.docx", b"x")
            proposals.update(conn, self.nv, pid, {"status": "review"})
            self.fail(proposals.delete_file, conn, self.nv, pid, fid, code=400)

    def test_overdue_flag_and_assigned_count(self):
        with db.connect() as conn:
            pid = self.new(conn)
            proposals.update(conn, self.ceo, pid, {"due_date": "2020-01-01", "status": "in_progress"})
            self.assertTrue(proposals.detail(conn, self.ceo, pid)["overdue"])
            self.assertEqual(proposals.open_assigned_count(conn, 2), 1)

    def to_done(self, conn, pid, *, files=1):
        proposals.update(conn, self.ceo, pid, {"status": "in_progress"})
        for i in range(files):
            proposals.add_file(conn, self.nv, pid, "result", f"kq{i}.txt", b"noi dung ket qua")
        proposals.update(conn, self.nv, pid, {"status": "review"})
        proposals.update(conn, self.ceo, pid, {"status": "done"})

    def test_archive_results_copies_to_documents_once(self):
        with db.connect() as conn:
            pid = self.new(conn)
            self.fail(proposals.archive_results, conn, self.ceo, pid, code=400)  # chưa nghiệm thu
            self.to_done(conn, pid, files=2)
            self.assertTrue(proposals.detail(conn, self.ceo, pid)["can_archive"])
            self.fail(proposals.archive_results, conn, self.nv, pid, code=403)  # chỉ Ban TGĐ
            ids = proposals.archive_results(conn, self.ceo, pid, "restricted")
            self.assertEqual(len(ids), 2)
            doc = db.row(conn, "SELECT * FROM documents WHERE id = ?", (ids[0],))
            self.assertEqual((doc["access_level"], doc["uploaded_by"]), ("restricted", 1))
            self.assertTrue(Path(doc["stored_path"]).is_file())
            d = proposals.detail(conn, self.ceo, pid)
            self.assertFalse(d["can_archive"])
            self.assertTrue(all(f["archived"] for f in d["files"]))
            self.assertEqual(len([f for f in d["files"] if f["doc_id"]]), 2)  # file gốc vẫn còn ở đề xuất
            self.fail(proposals.archive_results, conn, self.ceo, pid, code=400)  # không lưu trùng lần hai

    def test_archive_rejects_bad_level(self):
        with db.connect() as conn:
            pid = self.new(conn)
            self.to_done(conn, pid)
            self.fail(proposals.archive_results, conn, self.ceo, pid, "bi_mat_la", code=400)

    def test_stale_review_reminder(self):
        with db.connect() as conn:
            pid = self.new(conn)
            self.to_done(conn, pid)
            proposals.update(conn, self.ceo, pid, {"status": "in_progress"})
            proposals.update(conn, self.nv, pid, {"status": "review"})
            self.assertFalse(proposals.detail(conn, self.ceo, pid)["review_stale"])
            self.assertEqual(proposals.stale_review_count(conn), 0)
            conn.execute("UPDATE proposal_events SET at = datetime('now','localtime','-5 days') WHERE proposal_id = ? AND to_status = 'review'", (pid,))
            d = proposals.detail(conn, self.ceo, pid)
            self.assertTrue(d["review_stale"])
            self.assertGreaterEqual(d["review_days"], 5)
            self.assertEqual(proposals.stale_review_count(conn), 1)
            self.assertTrue(proposals.list_proposals(conn, self.ceo)[0]["review_stale"])
            proposals.update(conn, self.ceo, pid, {"status": "done"})  # nghiệm thu xong thì hết nhắc
            self.assertEqual(proposals.stale_review_count(conn), 0)

    def test_pending_count_for_boss_and_assignee(self):
        with db.connect() as conn:
            pid = self.new(conn)
            self.assertEqual(proposals.pending_count(conn, self.ceo), 1)  # đề xuất mới chờ duyệt
            self.assertEqual(proposals.pending_count(conn, self.nv), 0)  # chưa duyệt thì người phụ trách chưa phải làm
            proposals.update(conn, self.ceo, pid, {"status": "in_progress"})
            self.assertEqual(proposals.pending_count(conn, self.ceo), 0)
            self.assertEqual(proposals.pending_count(conn, self.nv), 1)
            self.assertEqual(proposals.pending_count(conn, self.other), 0)


if __name__ == "__main__":
    unittest.main()
