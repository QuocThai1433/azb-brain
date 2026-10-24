"""Người tải lên của file chưa đọc: lấy tên và đơn vị từ hồ sơ nhân sự đã liên kết, định danh bằng employee id (trùng tên vẫn đúng người).

Chạy từ thư mục gốc dự án: python -m unittest tests.test_uploader_link
"""
import unittest
from unittest import mock

from backend import app as app_module, auth, db
from tests.test_security import DbCase


class UploaderLinkTest(DbCase):
    def setUp(self):
        super().setUp()
        with db.connect() as c:
            # Hai hồ sơ cùng tên ở hai phòng khác nhau
            c.execute("INSERT INTO employees (id, employee_code, full_name, unit_id) VALUES (2,'NV002','Nguyễn Văn An',3)")
            c.execute("UPDATE users SET employee_id = 1 WHERE id = 2")  # mgrA = hồ sơ 1 (phòng A)
            c.execute("UPDATE users SET employee_id = 2 WHERE id = 3")  # view = hồ sơ 2 (phòng B)
            # 1: failed, đăng bởi mgrA; 2: needs_ocr, đăng bởi view; 3: failed, đăng bởi ceo (chưa liên kết hồ sơ);
            # 4: đã đọc được, đăng bởi mgrA
            for doc_id, uploader, status in ((1, 2, "failed"), (2, 3, "needs_ocr"), (3, 1, "failed"), (4, 2, "ok")):
                c.execute("UPDATE documents SET uploaded_by = ?, extract_status = ? WHERE id = ?", (uploader, status, doc_id))

    def listing(self):
        with mock.patch.object(auth, "require_permission", return_value=self.ceo), \
                mock.patch.object(auth, "current_user", return_value=self.ceo):
            return {d["id"]: d for d in app_module.list_documents(request=None)}

    def test_same_name_resolves_to_each_own_employee(self):
        docs = self.listing()
        self.assertEqual(docs[1]["uploader_employee_id"], 1)
        self.assertEqual(docs[2]["uploader_employee_id"], 2)
        self.assertEqual(docs[1]["uploader_name"], docs[2]["uploader_name"])  # cùng tên
        self.assertEqual(docs[1]["uploader_unit"], "Phòng A")
        self.assertEqual(docs[2]["uploader_unit"], "Phòng B")

    def test_unlinked_uploader_has_no_employee_link(self):
        docs = self.listing()
        self.assertIsNone(docs[3]["uploader_employee_id"])
        self.assertEqual(docs[3]["uploader_name"], "ceo")  # rơi về tên tài khoản

    def detail(self, user, doc_id):
        with mock.patch.object(auth, "require_permission", return_value=user), \
                mock.patch.object(auth, "current_user", return_value=user):
            return app_module.get_document(doc_id, request=None)

    def test_edit_form_shows_uploader_to_editors_only(self):
        editor = dict(self.ceo, permissions=["docs_view", "docs_edit"])
        viewer = dict(self.view, permissions=["docs_view"])
        d = self.detail(editor, 2)
        self.assertEqual((d["uploader_name"], d["uploader_unit"], d["uploader_employee_id"]), ("Nguyễn Văn An", "Phòng B", 2))
        self.assertNotIn("uploader_name", self.detail(viewer, 2))

    def test_readable_file_carries_no_uploader_info(self):
        docs = self.listing()
        self.assertIsNone(docs[4]["uploader_name"])
        self.assertIsNone(docs[4]["uploader_employee_id"])
        self.assertIsNone(docs[4]["uploader_unit"])


if __name__ == "__main__":
    unittest.main()
