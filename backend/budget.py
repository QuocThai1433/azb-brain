"""Trần chi tiêu AI mỗi ngày (USD): toàn công ty và từng người. Đặt 0 để tắt.

Tiền lấy từ ai_query_log (chat) và ai_usage_log (OCR, tóm tắt web, ghi chú) theo giờ máy chủ; chỉ là ước tính theo bảng giá trong ai.py.
"""
import os
import sqlite3
import threading
from datetime import datetime, time, timedelta

from . import auth

DAILY_BUDGET_USD = float(os.environ.get("AZB_DAILY_BUDGET_USD", "10"))
USER_DAILY_BUDGET_USD = float(os.environ.get("AZB_USER_DAILY_BUDGET_USD", "2"))
# Admin/TGĐ không bị trần cá nhân thường nhưng có trần riêng cao hơn, để một người không thể dùng hết ngân sách của cả công ty.
EXEC_DAILY_BUDGET_USD = float(os.environ.get("AZB_EXEC_DAILY_BUDGET_USD", "6"))
# Tiền giữ chỗ cho mỗi câu hỏi đang chạy (chưa ghi nhật ký): nhiều câu hỏi cùng lúc không cùng lọt qua một lần kiểm tra.
RESERVE_USD = float(os.environ.get("AZB_RESERVE_USD", "0.3"))
# Số tiền đã nạp vào tài khoản Anthropic (USD) để trang Chi phí AI hiện số dư còn lại; 0 = không hiện. AZB_CREDIT_SINCE (YYYY-MM-DD)
# chỉ tính chi phí từ ngày nạp trở đi; bỏ trống = tính toàn bộ nhật ký. Chỉ là ước tính, số dư thật xem ở console.anthropic.com.
CREDIT_USD = float(os.environ.get("AZB_CREDIT_USD", "0"))
CREDIT_SINCE = os.environ.get("AZB_CREDIT_SINCE", "").strip()
_lock = threading.Lock()
_inflight: dict[int, int] = {}  # user_id -> số câu hỏi đang chạy
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


def _held(user_id: int | None = None) -> float:
    return RESERVE_USD * (_inflight.get(user_id, 0) if user_id is not None else sum(_inflight.values()))


def status(conn: sqlite3.Connection, user: dict) -> dict | None:
    """Mức đã dùng hôm nay so với trần đang áp cho người này (cá nhân hoặc công ty, cái nào gần chạm hơn), None nếu không có trần.

    Chỉ trả phần trăm, không trả số tiền: người dùng thường không cần biết đơn giá. Trần reset lúc 0 giờ theo giờ máy chủ."""
    limits = []
    if DAILY_BUDGET_USD > 0:
        limits.append(("company", spent_today(conn) / DAILY_BUDGET_USD))
    if USER_DAILY_BUDGET_USD > 0 and user["role"] not in auth.EDIT_ALL_ROLES:
        limits.append(("user", spent_today(conn, user["id"]) / USER_DAILY_BUDGET_USD))
    if not limits:
        return None
    scope, ratio = max(limits, key=lambda x: x[1])
    now = datetime.now()
    resets_in = int((datetime.combine(now.date() + timedelta(days=1), time.min) - now).total_seconds())
    return {"percent": min(100, round(ratio * 100)), "scope": scope, "resets_in_seconds": resets_in}


def credit(conn: sqlite3.Connection) -> dict | None:
    """Số dư tín dụng ước tính = tiền đã nạp trừ chi phí đã ghi nhật ký (từ ngày nạp nếu có đặt). None nếu chưa đặt số tiền nạp."""
    if CREDIT_USD <= 0:
        return None
    since, args = ("WHERE date(ts) >= ?", (CREDIT_SINCE,)) if CREDIT_SINCE else ("", ())
    used = conn.execute(f"SELECT COALESCE(SUM(cost_usd), 0) FROM (SELECT ts, cost_usd FROM ai_query_log WHERE model IS NOT NULL"
                        f" UNION ALL SELECT ts, cost_usd FROM ai_usage_log) {since}", args).fetchone()[0]
    return {"total_usd": CREDIT_USD, "used_usd": round(used, 4), "remaining_usd": round(CREDIT_USD - used, 4),
            "percent_used": min(100, round(used / CREDIT_USD * 100, 1)), "since": CREDIT_SINCE or None}


def report(conn: sqlite3.Connection, days: int = 7) -> dict:
    """Chi phí AI N ngày gần nhất theo ngày, theo người và theo loại việc (chat, OCR, tóm tắt web...), kèm trần đang đặt."""
    days = max(1, min(days, 365))
    since = f"-{days - 1} days"
    both = ("SELECT date(ts) AS day, user_id, 'chat' AS kind, model, input_tokens, output_tokens, cost_usd FROM ai_query_log"
            " WHERE model IS NOT NULL AND date(ts) >= date('now','localtime',?)"
            " UNION ALL SELECT date(ts), user_id, kind, model, input_tokens, output_tokens, cost_usd FROM ai_usage_log"
            " WHERE date(ts) >= date('now','localtime',?)")
    args = (since, since)
    daily = conn.execute(f"SELECT day, COUNT(*) AS calls, COALESCE(SUM(input_tokens),0) AS input_tokens,"
                         f" COALESCE(SUM(output_tokens),0) AS output_tokens, ROUND(COALESCE(SUM(cost_usd),0), 4) AS cost_usd"
                         f" FROM ({both}) GROUP BY day ORDER BY day", args).fetchall()
    by_kind = conn.execute(f"SELECT kind, model, COUNT(*) AS calls, ROUND(COALESCE(SUM(cost_usd),0), 4) AS cost_usd"
                           f" FROM ({both}) GROUP BY kind, model ORDER BY SUM(cost_usd) DESC", args).fetchall()
    by_user = conn.execute(f"SELECT t.user_id, COALESCE(u.full_name, u.username, 'Hệ thống / việc nền') AS name, COUNT(*) AS calls,"
                           f" ROUND(COALESCE(SUM(t.cost_usd),0), 4) AS cost_usd FROM ({both}) t"
                           f" LEFT JOIN users u ON u.id = t.user_id GROUP BY t.user_id ORDER BY SUM(t.cost_usd) DESC", args).fetchall()
    # Từng lượt gọi mới nhất trước (chat kèm câu hỏi, việc nền kèm nhãn); token vào gồm cả token cache như log_cost
    recent = conn.execute(
        "SELECT ts, 'chat' AS kind, SUBSTR(question, 1, 120) AS label, model,"
        " COALESCE(input_tokens,0) + COALESCE(cache_read_tokens,0) + COALESCE(cache_write_tokens,0) AS input_tokens,"
        " COALESCE(output_tokens,0) AS output_tokens, cost_usd, user_id FROM ai_query_log"
        " WHERE model IS NOT NULL AND date(ts) >= date('now','localtime',?)"
        " UNION ALL SELECT ts, kind, SUBSTR(label, 1, 120), model, COALESCE(input_tokens,0), COALESCE(output_tokens,0), cost_usd, user_id"
        " FROM ai_usage_log WHERE date(ts) >= date('now','localtime',?) ORDER BY ts DESC LIMIT 200", args).fetchall()
    total = round(sum(r[4] or 0 for r in daily), 4)
    everything = ("SELECT date(ts) AS day, input_tokens, output_tokens, cost_usd FROM ai_query_log WHERE model IS NOT NULL"
                  " UNION ALL SELECT date(ts), input_tokens, output_tokens, cost_usd FROM ai_usage_log")
    n, tin, tout, usd, first = conn.execute(f"SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0),"
                                            f" ROUND(COALESCE(SUM(cost_usd),0), 4), MIN(day) FROM ({everything})").fetchone()
    return {"days": days, "total_usd": total, "today_usd": round(spent_today(conn), 4),
            "credit": credit(conn),
            "all_time": {"calls": n, "input_tokens": tin, "output_tokens": tout, "cost_usd": usd, "since": first},
            "daily_limit_usd": DAILY_BUDGET_USD, "user_limit_usd": USER_DAILY_BUDGET_USD,
            "daily": [dict(zip(("day", "calls", "input_tokens", "output_tokens", "cost_usd"), r)) for r in daily],
            "by_kind": [dict(zip(("kind", "model", "calls", "cost_usd"), r)) for r in by_kind],
            "by_user": [dict(zip(("user_id", "name", "calls", "cost_usd"), r)) for r in by_user],
            "recent": [dict(zip(("ts", "kind", "label", "model", "input_tokens", "output_tokens", "cost_usd", "user_id"), r)) for r in recent]}


def check(conn: sqlite3.Connection, user: dict) -> str | None:
    """Thông báo cho người dùng khi đã chạm trần hôm nay, không thì None. Tính cả các câu hỏi đang chạy (giữ chỗ)."""
    if DAILY_BUDGET_USD > 0 and spent_today(conn) + _held() >= DAILY_BUDGET_USD:
        return "Hôm nay trợ lý AI đã đạt ngân sách chi tiêu của công ty. Mai thử lại, hoặc nhờ quản trị viên tăng ngân sách."
    cap = EXEC_DAILY_BUDGET_USD if user["role"] in auth.EDIT_ALL_ROLES else USER_DAILY_BUDGET_USD
    if cap > 0 and spent_today(conn, user["id"]) + _held(user["id"]) >= cap:
        return "Hôm nay bạn đã dùng hết ngân sách trợ lý AI của mình. Mai thử lại, hoặc nhờ quản trị viên tăng ngân sách."
    return None


def reserve(conn: sqlite3.Connection, user: dict) -> str | None:
    """Kiểm tra trần và giữ chỗ cho một câu hỏi, trong một bước không bị chen ngang. None = được hỏi (phải gọi release sau đó)."""
    with _lock:
        over = check(conn, user)
        if not over:
            _inflight[user["id"]] = _inflight.get(user["id"], 0) + 1
        return over


def release(user_id: int) -> None:
    """Trả chỗ giữ khi câu hỏi đã xong và chi phí thật đã được ghi vào nhật ký."""
    with _lock:
        left = _inflight.get(user_id, 0) - 1
        if left > 0:
            _inflight[user_id] = left
        else:
            _inflight.pop(user_id, None)
