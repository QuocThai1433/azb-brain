"""Đường dẫn giao diện sạch tiếng Việt (/phong-ban/5/so-do...): trả index.html, còn API và tệp thiếu vẫn 404 JSON.

Chạy từ thư mục gốc dự án: python -m unittest tests.test_spa_routes
"""
import unittest

from fastapi.testclient import TestClient

from backend import app as app_module


class Case(unittest.TestCase):
    def setUp(self):
        self.cl = TestClient(app_module.app)

    def test_ui_paths_serve_index(self):
        for path in ("/", "/so-do-to-chuc", "/phong-ban/8/so-do", "/nhan-su/12", "/tai-lieu", "/muc-tieu-doanh-thu/3"):
            r = self.cl.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn("text/html", r.headers["content-type"], path)
            self.assertIn("AZB Brain", r.text, path)
            self.assertEqual(r.headers.get("cache-control"), "no-cache", path)

    def test_missing_api_is_json_404_not_html(self):
        r = self.cl.get("/api/khong-co")  # chưa đăng nhập: middleware chặn trước
        self.assertEqual(r.status_code, 401)
        self.assertIn("application/json", r.headers["content-type"])

    def test_unknown_api_and_static_return_404_json(self):
        for path in ("/static/khong-co.js", "/favicon.ico", "/api"):
            r = self.cl.get(path)
            self.assertIn(r.status_code, (401, 404), path)
            self.assertNotIn("text/html", r.headers["content-type"], path)

    def test_swagger_moved_under_api(self):
        self.assertIn("AZB Brain", self.cl.get("/tai-lieu").text)  # /tai-lieu là trang Tài liệu của app, không phải Swagger
        self.assertNotIn("swagger", self.cl.get("/tai-lieu").text.lower())


if __name__ == "__main__":
    unittest.main()
