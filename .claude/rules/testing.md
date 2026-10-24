---
paths:
  - "tests/**"
  - "backend/**"
---

# Kiểm thử

- Mỗi tính năng có một file `tests/test_<tính năng>.py`, dùng `unittest`.
- Test dùng database tạm, không chạm `data/azb.db` thật.
- Sửa `guard`, `access`, `backup` hoặc `auth` thì chạy tối thiểu `tests.test_security`.
- Chạy toàn bộ test trước khi báo hoàn thành.
