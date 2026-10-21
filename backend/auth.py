"""Đăng nhập, phiên làm việc và phân quyền."""
import hashlib
import hmac
import secrets
import sqlite3

from fastapi import HTTPException, Request

from .db import connect, row

SESSION_COOKIE = "azb_session"
SESSION_DAYS = 7

ROLES = {
    "admin": "Quản trị hệ thống",
    "ceo": "Ban Tổng Giám đốc",
    "manager": "Quản lý đơn vị",
    "viewer": "Chỉ xem",
}
# Quyền dùng trợ lý AI: AI đọc được toàn bộ dữ liệu nên chỉ cấp cho cấp điều hành
AI_ROLES = {"admin", "ceo"}
EDIT_ALL_ROLES = {"admin", "ceo"}

# Tính năng admin cấp riêng cho từng tài khoản (admin/ceo mặc định có đủ)
FEATURES = {
    "import_hr": "Nhập file HCNS",
    "docs_view": "Xem tài liệu",
    "docs_edit": "Sửa tài liệu (thêm/sửa/xoá)",
    "insights": "Xem Phân tích",
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, datetime('now','localtime', ?))",
        (token, user_id, f"+{SESSION_DAYS} days"),
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now','localtime')")
    return token


def user_from_token(token: str | None) -> dict | None:
    if not token:
        return None
    with connect() as conn:
        user = row(
            conn,
            """SELECT u.id, u.username, u.full_name, u.role, u.unit_id FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token = ? AND s.expires_at > datetime('now','localtime') AND u.active = 1""",
            (token,),
        )
        if user:
            user["permissions"] = effective_permissions(conn, user)
        return user


def effective_permissions(conn: sqlite3.Connection, user: dict) -> list[str]:
    if user["role"] in EDIT_ALL_ROLES:
        return list(FEATURES)
    granted = {r[0] for r in conn.execute("SELECT feature FROM user_permissions WHERE user_id = ?", (user["id"],))}
    if "docs_edit" in granted:
        granted.add("docs_view")  # sửa được thì phải xem được
    return [f for f in FEATURES if f in granted]


def require_permission(request: Request, feature: str) -> dict:
    user = current_user(request)
    if feature not in user["permissions"]:
        raise HTTPException(403, "Bạn không có quyền thực hiện thao tác này")
    return user


def current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "Chưa đăng nhập")
    return user


def require_roles(request: Request, roles: set[str]) -> dict:
    user = current_user(request)
    if user["role"] not in roles:
        raise HTTPException(403, "Bạn không có quyền thực hiện thao tác này")
    return user


def managed_unit_ids(conn: sqlite3.Connection, user: dict) -> set[int] | None:
    """Tập đơn vị user được sửa. None = được sửa tất cả."""
    if user["role"] in EDIT_ALL_ROLES:
        return None
    if user["role"] != "manager" or not user["unit_id"]:
        return set()
    ids, frontier = {user["unit_id"]}, [user["unit_id"]]
    while frontier:
        children = [r[0] for r in conn.execute(
            f"SELECT id FROM units WHERE parent_id IN ({','.join('?' * len(frontier))})", frontier)]
        frontier = [c for c in children if c not in ids]
        ids.update(frontier)
    return ids


def check_unit_write(conn: sqlite3.Connection, user: dict, unit_id: int | None) -> None:
    allowed = managed_unit_ids(conn, user)
    if allowed is None:
        return
    if unit_id is None or unit_id not in allowed:
        raise HTTPException(403, "Bạn chỉ được chỉnh sửa dữ liệu của đơn vị mình phụ trách")
