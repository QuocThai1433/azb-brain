"""Tìm theo ý nghĩa: tạo vector tăng dần, lọc theo quyền, tạo lại khi đổi nội dung, xoá khi xoá tài liệu,
và bổ sung tài liệu gần nghĩa vào kết quả từ khoá. Dùng hàm embed giả (không gọi API thật)."""
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import db, documents, semantic

# Từ điển giả: "trễ" và "chậm" dùng chung một chiều vector (gần nghĩa); "thầu phụ" và "đào tạo" khác hẳn nhau
VOCAB = {"thầu": 0, "phụ": 1, "chậm": 2, "trễ": 2, "đào": 3, "tạo": 4, "nhân": 5, "viên": 6, "hạn": 7, "công": 8, "trình": 8}


def fake_embed(texts, task):
    out = []
    for t in texts:
        v = [0.0] * 9
        for w in t.lower().split():
            if w in VOCAB:
                v[VOCAB[w]] += 1
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


class SemanticTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.patch = mock.patch.object(db, "DB_PATH", Path(self.tmp.name) / "azb.db")
        self.patch.start()
        self.embed = mock.patch.object(semantic, "_embed_override", fake_embed)
        self.embed.start()
        db.init_db()
        with db.connect() as c:
            c.executemany(
                "INSERT INTO documents (id, title, filename, stored_path, extract_status, unit_id, access_level) VALUES (?,?,?,?,?,?,?)",
                [(1, "Quy trình thầu phụ", "a.pdf", "a", "ok", None, "internal"),
                 (2, "Đào tạo nhân viên", "b.pdf", "b", "ok", None, "internal"),
                 (3, "Tiến độ công trình", "c.pdf", "c", "ok", None, "internal")])
            c.executemany("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) VALUES (?,?,?,?)",
                          [("thầu phụ chậm tiến độ", 1, 0, 1), ("đào tạo nhân viên mới", 2, 0, 1),
                           ("trễ hạn", 3, 0, 1)])
            self.conn = c
            semantic._cache["version"] += 1

    def tearDown(self):
        self.embed.stop()
        self.patch.stop()
        self.tmp.cleanup()

    def test_sync_is_incremental(self):
        self.assertEqual(semantic.sync(self.conn), 3)
        self.assertEqual(semantic.sync(self.conn), 0)  # đã có đủ, lần sau không gọi lại

    def test_search_ranks_related_and_skips_unrelated(self):
        semantic.sync(self.conn)
        hits = semantic.search(self.conn, "thầu phụ chậm", k=5)
        ids = [h[1] for h in hits]
        self.assertEqual(ids[0], 1)
        self.assertNotIn(2, ids)  # "đào tạo nhân viên" không gần nghĩa, bị loại theo ngưỡng

    def test_permission_filter_applies_before_ranking(self):
        semantic.sync(self.conn)
        self.assertEqual([h[1] for h in semantic.search(self.conn, "thầu phụ chậm", allowed_ids={2}, k=5)], [])

    def test_changed_document_is_reembedded(self):
        semantic.sync(self.conn)
        self.conn.execute("UPDATE documents SET title = 'Quy trình thầu phụ (sửa)', uploaded_at = '2099-01-01' WHERE id = 1")
        self.conn.commit()
        self.assertEqual(semantic.sync(self.conn), 1)  # chỉ tài liệu 1 được tạo lại

    def test_deleted_document_vectors_are_removed(self):
        semantic.sync(self.conn)
        self.conn.execute("DELETE FROM documents WHERE id = 2")
        self.conn.commit()
        semantic.sync(self.conn)
        left = {r[0] for r in self.conn.execute("SELECT DISTINCT doc_id FROM doc_vectors")}
        self.assertNotIn(2, left)

    def test_keyword_search_is_extended_with_semantic_match(self):
        # "chậm" khớp từ khoá ở tài liệu 1; tài liệu 3 chỉ có "trễ" nhưng gần nghĩa nên được bổ sung
        semantic.sync(self.conn)
        res = documents.ai_search(self.conn, "chậm", limit=5)
        by_id = {r["doc_id"]: r for r in res["results"]}
        self.assertIn(1, by_id)
        self.assertIn(3, by_id)
        self.assertEqual(by_id[3]["matched_in"], "nội dung (theo ý nghĩa)")
        self.assertNotIn(2, by_id)

    def test_no_index_means_keyword_only(self):
        res = documents.ai_search(self.conn, "chậm", limit=5)  # chưa sync: không có vector nào
        self.assertEqual({r["doc_id"] for r in res["results"]}, {1})

    def test_errors_in_embedding_do_not_break_search(self):
        semantic.sync(self.conn)
        def boom(*a, **k):
            raise RuntimeError("mất mạng")
        with mock.patch.object(semantic, "_embed_override", boom):
            res = documents.ai_search(self.conn, "chậm", limit=5)
        self.assertEqual({r["doc_id"] for r in res["results"]}, {1})


if __name__ == "__main__":
    unittest.main()
