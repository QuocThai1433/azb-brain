"""Tự đọc lại tài liệu bị lỗi TẠM THỜI khi OCR: AI quá tải (500/502/503/504/529) hoặc hết hạn mức (429).

Lỗi dạng này thường tự hết sau vài phút nên không cần người bấm đọc lại và không cần gọi nhà cung cấp thứ hai.
Chỉ thử lại file có ghi chú lỗi đúng định dạng của `documents._friendly_error`; lỗi khác (file hỏng, thiếu khoá, ảnh quá lớn...)
đọc lại cũng vô ích nên để nguyên. Mỗi file tối đa AZB_OCR_RETRY_MAX lần (đếm trong bộ nhớ, khởi động lại server thì đếm lại).

Biến môi trường: AZB_OCR_RETRY_MINUTES=5 (chu kỳ quét, 0 = tắt), AZB_OCR_RETRY_MAX=3.
Lưu ý chi phí: file nhiều cụm trang có thể đã trả tiền cho cụm đầu trước khi lỗi, thử lại sẽ trả lại cụm đó.
"""
import os
import re
import threading
import time
from collections import Counter

from . import documents
from .db import connect, row, rows

EVERY_MIN = float(os.environ.get("AZB_OCR_RETRY_MINUTES", "5"))
MAX_TRIES = int(os.environ.get("AZB_OCR_RETRY_MAX", "3"))
_TRANSIENT = re.compile(r"\((429|500|502|503|504|529)\)")
_tries: Counter = Counter()


def is_transient(note: str | None) -> bool:
    return bool(_TRANSIENT.search(note or ""))


def sweep() -> int:
    """Một lượt: đọc lại nối tiếp các file lỗi tạm thời. Gặp lại lỗi tạm thời thì dừng cả lượt (AI vẫn đang quá tải,
    thử tiếp chỉ làm đốt lần thử). Trả về số file đã đọc xong."""
    with connect() as conn:
        failed = rows(conn, "SELECT id, extract_note FROM documents WHERE extract_status = 'failed' ORDER BY id")
    done = 0
    for d in failed:
        if not is_transient(d["extract_note"]) or _tries[d["id"]] >= MAX_TRIES:
            continue
        _tries[d["id"]] += 1
        documents.process_document(d["id"])
        with connect() as conn:
            cur = row(conn, "SELECT extract_status, extract_note FROM documents WHERE id = ?", (d["id"],))
            if not cur or cur["extract_status"] != "failed":
                done += cur is not None
                continue
            if _tries[d["id"]] >= MAX_TRIES:  # hết lượt tự thử: báo để người dùng biết phải đọc lại tay
                conn.execute("UPDATE documents SET extract_note = ? WHERE id = ?",
                             (f"{cur['extract_note']} (Đã tự thử lại {MAX_TRIES} lần, hãy bấm đọc lại sau.)", d["id"]))
        if is_transient(cur["extract_note"]):
            break
    return done


def _loop() -> None:
    while True:
        time.sleep(EVERY_MIN * 60)
        try:
            sweep()
        except Exception:
            pass  # lượt quét lỗi không được làm sập máy chủ; lượt sau thử lại


def start_scheduler() -> None:
    if EVERY_MIN > 0:
        threading.Thread(target=_loop, name="azb-ocr-retry", daemon=True).start()
