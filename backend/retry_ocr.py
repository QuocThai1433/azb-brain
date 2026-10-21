"""Đọc lại các tài liệu bị lỗi do hết hạn mức Gemini (429). Dừng ngay khi gặp lại lỗi hạn mức.

Chạy: python -m backend.retry_ocr   (từ thư mục gốc dự án)
"""
import time

from .db import connect, rows
from .documents import process_document


def main() -> None:
    with connect() as conn:
        todo = rows(conn, "SELECT id, title FROM documents WHERE extract_status IN ('failed','pending','processing')"
                          " AND (extract_note LIKE '%429%' OR extract_note LIKE '%RESOURCE_EXHAUSTED%' OR extract_note IS NULL)"
                          " ORDER BY id")
    print(f"Cần đọc lại: {len(todo)} tài liệu", flush=True)
    done = 0
    for d in todo:
        process_document(d["id"])
        with connect() as conn:
            r = conn.execute("SELECT extract_status, extract_note FROM documents WHERE id = ?", (d["id"],)).fetchone()
        if r["extract_status"] == "failed":
            print(f"DỪNG tại #{d['id']} {d['title'][:50]}: {(r['extract_note'] or '')[:120]}", flush=True)
            break
        done += 1
        print(f"OK #{d['id']} {d['title'][:60]}", flush=True)
        time.sleep(3)
    with connect() as conn:
        left = conn.execute("SELECT COUNT(*) FROM documents WHERE extract_status != 'ok'").fetchone()[0]
    print(f"Xong {done} tài liệu, còn {left} chưa đọc được", flush=True)


if __name__ == "__main__":
    main()
