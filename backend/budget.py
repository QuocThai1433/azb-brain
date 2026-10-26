"""Trần chi tiêu AI mỗi ngày (USD): toàn công ty và từng người. Đặt 0 để tắt.

Tiền lấy từ ai_query_log (chat) và ai_usage_log (OCR, tóm tắt web, ghi chú) theo giờ máy chủ; chỉ là ước tính theo bảng giá trong ai.py.
"""
import os
import sqlite3

from . import auth

DAILY_BUDGET_USD = float(os.environ.get("AZB_DAILY_BUDGET_USD", "10"))
USER_DAILY_BUDGET_USD = float(os.environ.get("AZB_USER_DAILY_BUDGET_USD", "2"))
_TODAY = "date(ts) = date('now','localtime')"


def spent_today(conn: sqlite3.Connection, user_id: int | None = None) -> float:
    """Chi phí AI đã dùng hôm nay: của một người (chat + đọc scan/ảnh do file của họ) hoặc cả công ty (kể cả việc nền)."""
    if user_id is not None:
        chat = conn.execute(f"SELECT COALESCE(SUM(cost_usd), 0) FROM ai_query_log WHERE user_id = ? AND {_TODAY}",
                            (user_id,)).fetchone()[0]
        other = conn.execute(f"SELECT COALESCE(SUM(cost_usd), 0) FROM ai_usage_log WHERE user_id = ? AND {_TODAY}",
                             (user_id,)).fetchone()[0]
        return chat + other
    chat = conn.execute(f"SELECT COALESCE(SUM(cost_usd), 0) FROM ai_query_log WHERE {_TODAY}").fetchone()[0]
    other = conn.execute(f"SELECT COALESCE(SUM(cost_usd), 0) FROM ai_usage_log WHERE {_TODAY}").fetchone()[0]
    return chat + other


def check(conn: sqlite3.Connection, user: dict) -> str | None:
    """Thông báo cho người dùng khi đã chạm trần hôm nay, không thì None. Admin/TGĐ không bị trần cá nhân."""
    if DAILY_BUDGET_USD > 0 and spent_today(conn) >= DAILY_BUDGET_USD:
        return "Hôm nay trợ lý AI đã đạt ngân sách chi tiêu của công ty. Mai thử lại, hoặc nhờ quản trị viên tăng ngân sách."
    if USER_DAILY_BUDGET_USD > 0 and user["role"] not in auth.EDIT_ALL_ROLES \
            and spent_today(conn, user["id"]) >= USER_DAILY_BUDGET_USD:
        return "Hôm nay bạn đã dùng hết ngân sách trợ lý AI của mình. Mai thử lại, hoặc nhờ quản trị viên tăng ngân sách."
    return None
