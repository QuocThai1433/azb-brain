"""Nhân viên nghỉ việc: giữ dữ liệu riêng 90 ngày rồi admin duyệt xoá.

Khi admin khoá tài khoản (users.active = 0) hệ thống ghi users.deactivated_at. Trong RETENTION_DAYS ngày dữ liệu riêng của
tài khoản (file đính kèm chat, ghi chú AI, lịch sử chat) được giữ nguyên để admin/ban TGĐ xem và bàn giao. Hết hạn, dữ liệu
chỉ bị xoá khi admin bấm duyệt (không tự xoá). Mở khoá lại tài khoản thì bỏ đồng hồ 90 ngày.

Không xoá: tài liệu đã đưa lên thư viện chung (tài sản công ty) và nhật ký hệ thống (audit_log, ai_query_log).
"""
import sqlite3

from fastapi import HTTPException

from . import privatefiles
from .db import row, rows

RETENTION_DAYS = 90


def overview(conn: sqlite3.Connection) -> list[dict]:
    """Tài khoản đã khoá còn dữ liệu riêng, kèm số ngày giữ còn lại (<= 0 là đã đến hạn chờ admin duyệt xoá)."""
    out = rows(conn, """
        SELECT u.id, u.username, u.full_name, u.role, u.deactivated_at, u.data_purged_at,
               CAST(? - (julianday('now','localtime') - julianday(u.deactivated_at)) AS INTEGER) AS days_left,
               (SELECT COUNT(*) FROM documents d WHERE d.access_level = 'private' AND d.owner_id = u.id) AS files,
               (SELECT COALESCE(SUM(size_bytes), 0) FROM documents d WHERE d.access_level = 'private' AND d.owner_id = u.id) AS bytes,
               (SELECT COUNT(*) FROM user_memories m WHERE m.user_id = u.id) AS notes,
               (SELECT COUNT(*) FROM conversations c WHERE c.user_id = u.id) AS conversations
        FROM users u WHERE u.active = 0 ORDER BY u.deactivated_at""", (RETENTION_DAYS,))
    for u in out:
        u["due"] = u["days_left"] is not None and u["days_left"] <= 0
        u["has_data"] = bool(u["files"] or u["notes"] or u["conversations"])
    return [u for u in out if u["has_data"]]


def purge(conn: sqlite3.Connection, user_id: int, confirm: str) -> dict:
    """Xoá vĩnh viễn dữ liệu riêng của một tài khoản đã khoá quá hạn. `confirm` phải là tên đăng nhập (admin gõ lại để xác nhận)."""
    u = row(conn, "SELECT id, username, active FROM users WHERE id = ?", (user_id,))
    if not u:
        raise HTTPException(404, "Không tìm thấy tài khoản")
    if u["active"]:
        raise HTTPException(400, "Tài khoản này đang hoạt động, không xoá dữ liệu.")
    if (confirm or "").strip().lower() != u["username"].lower():
        raise HTTPException(400, "Hãy gõ đúng tên đăng nhập để xác nhận xoá.")
    info = next((o for o in overview(conn) if o["id"] == user_id), None)
    if info is None:
        raise HTTPException(400, "Tài khoản này không còn dữ liệu riêng để xoá.")
    if not info["due"]:
        raise HTTPException(400, f"Chưa đủ {RETENTION_DAYS} ngày giữ dữ liệu: còn {info['days_left']} ngày.")
    file_ids = [r[0] for r in conn.execute("SELECT id FROM documents WHERE access_level = 'private' AND owner_id = ?", (user_id,))]
    for doc_id in file_ids:
        privatefiles.remove(conn, doc_id)
    notes = conn.execute("DELETE FROM user_memories WHERE user_id = ?", (user_id,)).rowcount
    convs = conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,)).rowcount  # chat_messages xoá theo (CASCADE)
    conn.execute("DELETE FROM ocr_usage WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE users SET memory_on = 0, data_purged_at = datetime('now','localtime') WHERE id = ?", (user_id,))
    return {"files": len(file_ids), "notes": notes, "conversations": convs}
