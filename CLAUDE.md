# AZB Brain

App quản trị tri thức công ty AZB, tích hợp trợ lý AI cho Tổng Giám đốc. Backend FastAPI + SQLite, frontend HTML/JS thuần (không build). Giới thiệu và hướng dẫn người dùng: `README.md`.

## Lệnh thường dùng (Windows, chạy từ thư mục gốc)
- Chạy app: `scripts\run.bat` (hoặc `.venv\Scripts\python -X utf8 -m uvicorn backend.app:app --port 8000`)
- Test toàn bộ: `.venv\Scripts\python -X utf8 -m unittest discover -s tests -t .`
- Test một file: `.venv\Scripts\python -X utf8 -m unittest tests.test_security`
- Luôn dùng `-X utf8` vì dữ liệu tiếng Việt.

## Cấu trúc
- `backend/` – package Python phẳng, các module import chéo nhau (`app.py` kéo `seed`, `hr_import`, `verify_scan`), nên không tự ý chia thư mục con.
- `frontend/` – `index.html`, `app.js`, `styles.css`, logo. Do `backend/app.py` phục vụ trực tiếp.
- `tests/` – unittest, mỗi tính năng một file `test_*.py`.
- `scripts/` – file `.bat` chạy app. `docs/` – lộ trình, bản demo giao diện.
- `data/`, `_backup/`, `.env`, `.venv/` – dữ liệu thật và bí mật, đã gitignore. Không đọc, không sửa, không commit.

## Quy ước
- Quy tắc chi tiết ở `.claude/rules/` (kiến trúc, bảo mật, test).
- Thông điệp commit và giao diện bằng tiếng Việt; tên module/hàm bằng tiếng Anh.
- Thêm biến môi trường mới thì ghi vào `.env.example`.
