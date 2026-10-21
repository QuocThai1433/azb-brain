# AZB Brain

App quản trị tri thức công ty AZB tích hợp trợ lý AI cho Tổng Giám đốc.

## Chạy
1. Copy `.env.example` thành `.env`, điền `GROQ_API_KEY` (trợ lý AI) và `GEMINI_API_KEY` (đọc PDF scan).
2. Bấm đúp `run.bat` (lần đầu tự tạo môi trường và cài thư viện) → mở http://127.0.0.1:8000
3. Lần đầu mở: tạo tài khoản quản trị, sau đó vào "Tài khoản" để cấp tài khoản cho TGĐ / trưởng đơn vị.

Nạp lại sơ đồ gốc (XOÁ toàn bộ dữ liệu đã nhập): `.venv\Scripts\python -X utf8 -m backend.seed`

Nhập danh sách nhân sự HCNS (cập nhật hằng tuần, khớp theo mã NV): nút "Nhập file HCNS" ở trang Nhân sự, hoặc
`.venv\Scripts\python -X utf8 -m backend.hr_import "<file .xlsx>"`

## Cấu trúc
- `backend/db.py` – schema SQLite (`data/azb.db`): units, employees, positions, processes, targets, audit_log
- `backend/seed.py` – dữ liệu sơ đồ điều hành AZB-SDTC-REV02 (01/08/2026)
- `backend/analytics.py` – truy vấn tổng hợp, chỉ dấu tổ chức (kiêm nhiệm, vị trí trống, tầm hạn quản lý...)
- `backend/ai.py` – trợ lý AI dùng tool chỉ-đọc để tra cứu database. Có `GROQ_API_KEY` thì dùng Groq (`openai/gpt-oss-120b`, đổi bằng `AZB_GROQ_MODEL`), không thì Gemini (`gemini-3.8-flash`, `AZB_GEMINI_MODEL`); ép chọn bằng `AI_PROVIDER=groq|gemini`
- `backend/app.py` – REST API + phục vụ giao diện
- `backend/auth.py` – đăng nhập, phiên, phân quyền (admin / ceo / manager / viewer)
- `backend/documents.py` – kho tài liệu: lưu file (`data/uploads`), trích xuất PDF/DOCX/XLSX/TXT, PDF scan đọc bằng Gemini, tìm kiếm toàn văn không dấu
- `frontend/` – giao diện (HTML/JS thuần, không cần build)

## Lưu ý
- Server chỉ nghe ở 127.0.0.1. Muốn cho người khác trong công ty truy cập cần đưa lên máy chủ nội bộ có HTTPS.
- Trợ lý AI đọc được toàn bộ dữ liệu nên chỉ cấp cho vai trò Quản trị và Ban TGĐ.
- Sao lưu: copy cả thư mục `data/` (database + file gốc).
- Mục có nhãn "Cần xác nhận": tên viết tắt trên sơ đồ hoặc giải nghĩa viết tắt phòng ban do AI đoán – cần HCNS xác nhận.
