"""Tài liệu hiện ở nhiều phòng ban: đơn vị chủ quản + đơn vị dùng chung (bảng document_units).

Chạy từ thư mục gốc dự án: python -m unittest tests.test_document_units
"""
import unittest
from unittest import mock

from backend import access, analytics, app as app_module, auth, db
from tests.test_security import DbCase


class DocumentUnitsTest(DbCase):
    def setUp(self):
        super().setUp()
        with db.connect() as c:
            c.execute("INSERT INTO document_units (doc_id, unit_id) VALUES (3, 2)")  # hạn chế của B, chia sẻ cho A
            c.execute("INSERT INTO document_units (doc_id, unit_id) VALUES (1, 3)")  # nội bộ của A, chia sẻ cho B

    def as_user(self, user):
        return mock.patch.multiple(auth, require_permission=mock.Mock(return_value=user), current_user=mock.Mock(return_value=user))

    def test_unit_detail_lists_owned_and_shared_with_flag(self):
        user = dict(self.ceo, permissions=["docs_view"])
        with self.as_user(user), mock.patch.object(auth, "managed_unit_ids", return_value=None):
            a = {d["id"]: d for d in app_module.get_unit(2, request=mock.Mock(state=mock.Mock(user=user)))["documents"]}
        self.assertTrue(a[1]["is_owner"] and a[2]["is_owner"])
        self.assertFalse(a[3]["is_owner"])
        self.assertEqual(a[3]["owner_unit_name"], "Phòng B")
        self.assertEqual(a[1]["other_units"], "Phòng B")

    def test_restricted_doc_visible_to_unit_it_is_shared_with(self):
        with db.connect() as c:
            self.assertIn(3, access.visible_doc_ids(c, self.mgr))  # mgrA thuộc A, doc 3 chủ quản B nhưng chia sẻ cho A
            self.assertNotIn(4, access.visible_doc_ids(c, self.mgr))  # mật vẫn ẩn

    def test_sharing_does_not_open_restricted_doc_to_other_units(self):
        with db.connect() as c:
            other = {"id": 9, "role": "viewer", "unit_id": 3}
            c.execute("DELETE FROM document_units WHERE doc_id = 3")
            self.assertNotIn(2, access.visible_doc_ids(c, other))  # restricted A, chưa chia sẻ cho B
            c.execute("INSERT INTO document_units (doc_id, unit_id) VALUES (2, 3)")
            self.assertIn(2, access.visible_doc_ids(c, other))

    def test_list_filter_by_unit_includes_shared(self):
        user = dict(self.ceo, permissions=["docs_view"])
        with self.as_user(user):
            ids = {d["id"] for d in app_module.list_documents(request=None, unit_id=2)}
            docs = {d["id"]: d for d in app_module.list_documents(request=None)}
        self.assertEqual(ids, {1, 2, 3})
        self.assertEqual(docs[1]["shared_units"], [{"id": 3, "name": "Phòng B"}])

    def test_set_shared_units_dedups_and_skips_primary_and_unknown(self):
        with db.connect() as c:
            out = access.set_shared_units(c, 1, [3, 3, 2, 999, "x"], primary=2)
            self.assertEqual(out, [3])
            self.assertEqual(access.shared_unit_ids(c, 1), [3])

    def test_update_document_replaces_shared_units(self):
        user = dict(self.ceo, permissions=["docs_view", "docs_edit"])
        with self.as_user(user), mock.patch.object(auth, "check_unit_write"):
            app_module.update_document(1, {"shared_unit_ids": [1]}, request=None)
        with db.connect() as c:
            self.assertEqual(access.shared_unit_ids(c, 1), [1])

    def test_doc_count_in_org_tree_counts_shared(self):
        with db.connect() as c:
            c.execute("UPDATE documents SET doc_type = 'quy_trinh' WHERE id = 1")
            counts = {u["id"]: u["doc_count"] for u in analytics.units_flat(c)}
        self.assertEqual(counts[3], 3)  # tài liệu 3 và 4 (chủ quản) + tài liệu 1 (dùng chung)

    def test_ai_search_unit_filter_matches_shared_unit(self):
        from backend import documents
        with db.connect() as c:
            res = documents.ai_search(c, "noibo", unit_id=3, allowed_ids=access.visible_doc_ids(c, self.ceo))
        self.assertIn(1, {r["doc_id"] for r in res["results"]})

    def test_deleting_unit_drops_links(self):
        with db.connect() as c:
            c.execute("DELETE FROM units WHERE id = 3")
            self.assertEqual(access.shared_unit_ids(c, 1), [])


if __name__ == "__main__":
    unittest.main()
