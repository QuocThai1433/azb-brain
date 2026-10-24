# Kiến trúc

- `db.py` giữ schema SQLite (`data/azb.db`); đổi schema phải có bước migrate trong `init_db`, không phá dữ liệu cũ.
- `app.py` chỉ chứa route REST; logic nghiệp vụ đặt ở module riêng (`analytics`, `documents`, `memory`...).
- `ai.py` chỉ dùng tool đọc, chạy trên kết nối `query_only`. Không thêm tool ghi cho AI; thay đổi do AI đề xuất đi qua luồng proposals.
- Frontend là HTML/JS thuần, không thêm bước build hay framework nếu chưa được yêu cầu.
- Script chạy một lần (`seed`, `hr_import`, `hr_add_missing`, `retry_ocr`, `verify_scan`) chạy bằng `python -m backend.<tên>`; giữ nguyên tên module vì README và `app.py` tham chiếu.
