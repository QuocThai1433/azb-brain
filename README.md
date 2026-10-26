# AZB Brain

App quản trị tri thức công ty AZB tích hợp trợ lý AI cho Tổng Giám đốc.

## Chạy
1. Copy `.env.example` thành `.env`, điền `ANTHROPIC_API_KEY` (trợ lý AI, đọc ảnh/PDF scan).
2. Bấm đúp `scripts\run.bat` (lần đầu tự tạo môi trường và cài thư viện) → mở http://127.0.0.1:8000
3. Lần đầu mở: tạo tài khoản quản trị, sau đó vào "Tài khoản" để cấp tài khoản cho TGĐ / trưởng đơn vị.

Nạp lại sơ đồ gốc (XOÁ toàn bộ dữ liệu đã nhập): `.venv\Scripts\python -X utf8 -m backend.seed`

Nhập danh sách nhân sự HCNS (cập nhật hằng tuần, khớp theo mã NV): nút "Nhập file HCNS" ở trang Nhân sự, hoặc
`.venv\Scripts\python -X utf8 -m backend.hr_import "<file .xlsx>"`

## Cấu trúc
- `backend/db.py` – schema SQLite (`data/azb.db`): units, employees, positions, processes, targets, audit_log
- `backend/seed.py` – dữ liệu sơ đồ điều hành AZB-SDTC-REV02 (01/08/2026)
- `backend/analytics.py` – truy vấn tổng hợp, chỉ dấu tổ chức (kiêm nhiệm, vị trí trống, tầm hạn quản lý...)
- `backend/ai.py` – trợ lý AI dùng tool chỉ-đọc để tra cứu database. Mặc định dùng Claude (`claude-opus-5-5`, đổi bằng `AZB_ANTHROPIC_MODEL`), dự phòng Groq nếu có `GROQ_API_KEY`; ép chọn bằng `AI_PROVIDER=anthropic|groq`. Gỡ băng ghi âm và tìm theo ý nghĩa vẫn cần `GEMINI_API_KEY` (tuỳ chọn)
- `backend/app.py` – REST API + phục vụ giao diện
- `backend/auth.py` – đăng nhập, phiên, phân quyền (admin / ceo / manager / viewer)
- `backend/documents.py` – kho tài liệu: lưu file (`data/uploads`), trích xuất PDF/DOCX/XLSX/TXT, PDF scan/ảnh đọc bằng Claude, tìm kiếm toàn văn không dấu
- `frontend/` – giao diện (HTML/JS thuần, không cần build)

## Lưu ý
- Server chỉ nghe ở 127.0.0.1. Muốn cho người khác trong công ty truy cập cần đưa lên máy chủ nội bộ có HTTPS. Không dùng `scripts\run-lan.bat` cho dữ liệu thật vì đi qua http, không mã hoá.
- Trợ lý AI đọc được toàn bộ dữ liệu nên chỉ cấp cho vai trò Quản trị và Ban TGĐ.
- Sao lưu: copy cả thư mục `data/` (database + file gốc).
- Mục có nhãn "Cần xác nhận": tên viết tắt trên sơ đồ hoặc giải nghĩa viết tắt phòng ban do AI đoán – cần HCNS xác nhận.

## Bảo mật trợ lý AI
- **AI chỉ đọc**: AI chỉ có các công cụ tra cứu, chạy trên kết nối database `query_only` – không gửi email, xoá hay sửa dữ liệu/file gốc được, kể cả khi tài liệu chứa lệnh độc hại.
- **Chống prompt injection** (`backend/guard.py`): nội dung tài liệu là dữ liệu không đáng tin; ký tự ẩn bị xoá, câu giống "bỏ qua hướng dẫn..." bị vô hiệu hoá + cảnh báo (cả lúc tải lên và lúc AI đọc); ảnh/link markdown ra ngoài trong câu trả lời bị bỏ.
- **Độ mật tài liệu** (`backend/access.py`): Công khai / Nội bộ / Hạn chế (theo đơn vị) / Mật (chỉ admin, ceo). Lọc theo quyền người hỏi TRƯỚC khi đưa cho AI, và áp dụng cho cả danh sách/tìm kiếm/tải file. Tài liệu cũ mặc định "Nội bộ", tài liệu website "Công khai". Mục tiêu doanh thu chỉ xem được với đơn vị mình quản lý.
- **Dữ liệu cá nhân** (ngày sinh, mã NV, hợp đồng, SĐT, email, ghi chú nhân sự) không gửi cho nhà cung cấp AI.
- **Nhật ký**: mọi câu hỏi AI ghi vào `ai_query_log` (admin xem tại `GET /api/ai/audit`, `?flagged_only=true` để lọc cảnh báo). Giới hạn 8 câu/phút và 300 câu/ngày mỗi tài khoản.
- **Sao lưu**: tự động mỗi 24 giờ (database + bản sao file gốc, giữ 14 bản). Admin: `GET/POST /api/admin/backups`. Đặt `AZB_BACKUP_DIR` sang ổ khác. Xoá tài liệu chỉ chuyển file vào `data/uploads/_trash`.
- Chạy kiểm thử: `.venv\Scripts\python -X utf8 -m unittest tests.test_security tests.test_contacts`
