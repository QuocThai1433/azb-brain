"""Gán người đăng cho các tài liệu không rõ người tải lên (uploaded_by IS NULL) cho một tài khoản chỉ định.

Sao lưu data/azb.db trước khi chạy --apply. Chạy từ thư mục gốc dự án:
    python -X utf8 -m backend.assign_uploader <tên_đăng_nhập>            # chỉ đếm, không ghi
    python -X utf8 -m backend.assign_uploader <tên_đăng_nhập> --apply    # ghi thật
"""
import sys

from .db import connect, row


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("--"):
        print("Cần tên đăng nhập, ví dụ: python -m backend.assign_uploader admin --apply")
        return 2
    username, apply = argv[0], "--apply" in argv
    with connect() as conn:
        user = row(conn, "SELECT id, username FROM users WHERE username = ?", (username,))
        if not user:
            print(f"Không tìm thấy tài khoản '{username}'. Không ghi gì.")
            return 1
        count = conn.execute("SELECT COUNT(*) FROM documents WHERE uploaded_by IS NULL").fetchone()[0]
        print(f"Tài liệu chưa rõ người đăng: {count}. Gán cho '{user['username']}' (id {user['id']}).")
        if apply:
            cur = conn.execute("UPDATE documents SET uploaded_by = ? WHERE uploaded_by IS NULL", (user["id"],))
            conn.commit()
            print(f"Đã cập nhật {cur.rowcount} tài liệu.")
        else:
            print("Chưa ghi gì. Thêm --apply để ghi thật.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
