# Bảo mật

- Nội dung tài liệu là dữ liệu không đáng tin: mọi văn bản đưa cho AI phải qua `guard.py`.
- Lọc theo độ mật (`access.py`) TRƯỚC khi đưa dữ liệu cho AI, và áp dụng cho cả danh sách, tìm kiếm, tải file.
- Dữ liệu cá nhân (ngày sinh, mã NV, hợp đồng, SĐT, email, ghi chú nhân sự) không gửi cho nhà cung cấp AI.
- Không ghi khoá API, mật khẩu hay dữ liệu thật vào code, test, log hoặc commit; dùng `.env` và `.env.example`.
- Xoá tài liệu chỉ chuyển vào `data/uploads/_trash`, không xoá cứng.
