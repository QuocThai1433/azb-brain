"""Kho riêng theo tài khoản: file/ảnh đính kèm khi chat (documents.access_level = 'private', owner_id = người gửi).

- Chỉ chủ file (và admin/ceo, để quản lý) xem được; tìm kiếm thư viện và trợ lý AI của người khác không thấy (xem access.py).
- Hạn mức dung lượng mỗi người (tính theo file gốc đã tải lên); admin/ceo không giới hạn; admin nâng riêng cho từng người
  qua users.quota_mb.
- Ảnh/scan/ghi âm KHÔNG đọc bằng AI lúc tải lên mà chỉ khi người dùng gửi câu hỏi (tiết kiệm hạn mức Gemini); mỗi người có
  trần số lần đọc mỗi ngày.
"""
import re
import shutil
import sqlite3
from pathlib import Path

from fastapi import HTTPException

from . import access, documents
from .db import connect, row

DEFAULT_QUOTA_MB = 300
OCR_DAILY_LIMIT = 20  # số lần đọc ảnh/scan/ghi âm bằng AI mỗi người mỗi ngày
MB = 1024 * 1024
_ATTACH_ID = re.compile(r"id tài liệu (\d+)")


def quota_mb(conn: sqlite3.Connection, user: dict) -> int | None:
    """Hạn mức (MB) của user; None = không giới hạn (admin/ceo)."""
    if access.is_exec(user):
        return None
    r = conn.execute("SELECT quota_mb FROM users WHERE id = ?", (user["id"],)).fetchone()
    return r[0] if r and r[0] else DEFAULT_QUOTA_MB


def used_bytes(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM documents WHERE access_level = 'private' AND owner_id = ?",
                        (user_id,)).fetchone()[0]


def usage(conn: sqlite3.Connection, user: dict) -> dict:
    used = used_bytes(conn, user["id"])
    q = quota_mb(conn, user)
    out = {"used_mb": round(used / MB, 1), "quota_mb": q, "remaining_mb": None, "percent": None}
    if q is not None:
        out["remaining_mb"] = round(max(q * MB - used, 0) / MB, 1)
        out["percent"] = min(100, round(used * 100 / (q * MB)))
    return out


def check_quota(conn: sqlite3.Connection, user: dict, add_bytes: int) -> None:
    q = quota_mb(conn, user)
    if q is not None and used_bytes(conn, user["id"]) + add_bytes > q * MB:
        left = max(q * MB - used_bytes(conn, user["id"]), 0) / MB
        raise HTTPException(400, f"Không đủ dung lượng: hạn mức {q} MB, còn {left:.1f} MB. Hãy xoá bớt file cũ trong "
                                 "\"Dữ liệu của tôi\" hoặc nhờ admin nâng hạn mức.")


def ocr_take(conn: sqlite3.Connection, user_id: int) -> bool:
    """Xin một lượt đọc bằng AI trong ngày; False nếu đã hết trần của người này."""
    day = conn.execute("SELECT date('now','localtime')").fetchone()[0]
    conn.execute("INSERT OR IGNORE INTO ocr_usage (user_id, day, n) VALUES (?, ?, 0)", (user_id, day))
    cur = conn.execute("UPDATE ocr_usage SET n = n + 1 WHERE user_id = ? AND day = ? AND n < ?", (user_id, day, OCR_DAILY_LIMIT))
    return cur.rowcount == 1


def get_file(conn: sqlite3.Connection, user: dict, doc_id: int) -> dict:
    """File riêng của chính user; admin/ceo xem được của người khác (quản lý). Không phải thì báo không tìm thấy."""
    d = row(conn, "SELECT d.*, o.username AS owner_username, o.full_name AS owner_name FROM documents d"
                  " LEFT JOIN users o ON o.id = d.owner_id WHERE d.id = ? AND d.access_level = 'private'", (doc_id,))
    if not d or not (d["owner_id"] == user["id"] or access.is_exec(user)):
        raise HTTPException(404, "Không tìm thấy file")
    return d


def prepare_attachments(user: dict, text: str) -> list[str]:
    """Trước khi AI trả lời: đọc (OCR) các file đính kèm của chính user còn chờ đọc. Trả về các cảnh báo cho AI/người dùng."""
    notes = []
    for doc_id in list(dict.fromkeys(int(i) for i in _ATTACH_ID.findall(text)))[:10]:
        with connect() as conn:
            d = row(conn, "SELECT id, title, extract_status, extract_note FROM documents"
                          " WHERE id = ? AND owner_id = ? AND access_level = 'private'", (doc_id, user["id"]))
            if not d:
                continue
            retry = d["extract_status"] == "failed" and any(k in (d["extract_note"] or "") for k in ("429", "quá tải"))
            if d["extract_status"] != "needs_ocr" and not retry:
                continue
            if not ocr_take(conn, user["id"]):
                notes.append(f'File "{d["title"]}" chưa được đọc vì hôm nay bạn đã dùng hết {OCR_DAILY_LIMIT} lượt đọc ảnh/scan.')
                continue
        documents.process_document(doc_id, use_ocr=True)
        with connect() as conn:
            d = row(conn, "SELECT title, extract_status, extract_note FROM documents WHERE id = ?", (doc_id,))
        if d["extract_status"] != "ok":
            notes.append(f'File "{d["title"]}" chưa đọc được: {d["extract_note"] or d["extract_status"]}')
    return notes


def publish_copy(conn: sqlite3.Connection, user: dict, doc_id: int, unit_id: int | None, level: str, title: str) -> int:
    """Sao chép file riêng sang thư viện chung (bản gốc vẫn của chủ). Trả về id tài liệu mới."""
    src = get_file(conn, user, doc_id)
    if src["owner_id"] != user["id"]:
        raise HTTPException(403, "Chỉ chủ file mới đưa lên thư viện chung")
    if src["extract_status"] != "ok":
        raise HTTPException(400, "File chưa đọc được nội dung, hãy đọc xong rồi mới đưa lên thư viện")
    cur = conn.execute(
        "INSERT INTO documents (unit_id, title, doc_type, filename, stored_path, mime, size_bytes, page_count, char_count,"
        " extract_status, extract_note, content, uploaded_by, access_level) VALUES (?,?,'khac',?,'',?,?,?,?,?,?,?,?,?)",
        (unit_id, title.strip() or src["title"], src["filename"], src["mime"], src["size_bytes"], src["page_count"],
         src["char_count"], src["extract_status"], src["extract_note"], src["content"], user["id"], level))
    new_id = cur.lastrowid
    path = documents.UPLOAD_DIR / f"{new_id}_{documents.safe_filename(src['filename'])}"
    shutil.copyfile(src["stored_path"], path)
    conn.execute("UPDATE documents SET stored_path = ? WHERE id = ?", (str(path), new_id))
    conn.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) SELECT text, ?, chunk_no, page FROM doc_chunks WHERE doc_id = ?",
                 (new_id, doc_id))
    return new_id


def remove(conn: sqlite3.Connection, doc_id: int) -> None:
    """Xoá một file riêng: bỏ dữ liệu/chỉ mục, file gốc chuyển vào thùng rác (_trash) để lấy lại được nếu lỡ tay."""
    d = row(conn, "SELECT stored_path FROM documents WHERE id = ? AND access_level = 'private'", (doc_id,))
    if not d:
        return
    conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    src = Path(d["stored_path"] or "")
    if src.is_file():
        trash = documents.UPLOAD_DIR / "_trash"
        trash.mkdir(exist_ok=True)
        shutil.move(str(src), str(trash / src.name))


def conversation_files(conn: sqlite3.Connection, user_id: int, conv_id: int) -> dict:
    """File riêng của user được đính kèm trong đoạn chat này. `files` = chỉ dùng trong đoạn chat này (xoá chat có thể xoá luôn);
    `kept` = số file còn được đoạn chat khác của user dùng nên luôn giữ lại."""
    def ids_in(sql: str, args: tuple) -> set[int]:
        return {int(i) for (text,) in conn.execute(sql, args) for i in _ATTACH_ID.findall(text or "")}
    here = ids_in("SELECT m.content FROM chat_messages m JOIN conversations c ON c.id = m.conversation_id"
                  " WHERE c.id = ? AND c.user_id = ? AND m.role = 'user'", (conv_id, user_id))
    elsewhere = ids_in("SELECT m.content FROM chat_messages m JOIN conversations c ON c.id = m.conversation_id"
                       " WHERE c.id != ? AND c.user_id = ? AND m.role = 'user'", (conv_id, user_id))
    mine = {}
    if here:
        marks = ",".join("?" * len(here))
        mine = {r["id"]: dict(r) for r in conn.execute(
            f"SELECT id, title, filename, size_bytes FROM documents WHERE access_level = 'private' AND owner_id = ?"
            f" AND id IN ({marks})", (user_id, *sorted(here)))}
    only_here = [d for i, d in sorted(mine.items()) if i not in elsewhere]
    return {"files": only_here, "kept": len(mine) - len(only_here)}
