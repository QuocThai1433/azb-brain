"""Phân quyền xem tài liệu theo độ mật và đơn vị. Dùng chung cho API và trợ lý AI.

Độ mật (documents.access_level):
  public     – công khai (vd tài liệu website)
  internal   – nội bộ: mọi tài khoản có quyền xem tài liệu
  restricted – hạn chế: chỉ người thuộc đơn vị chủ quản (và đơn vị con) của tài liệu, cùng admin/ceo
  secret     – mật: chỉ admin/ceo

Lọc luôn làm TRƯỚC khi dữ liệu tới AI: tài liệu người hỏi không được xem thì AI không bao giờ nhận được nội dung,
nên không thể bị hỏi lộ ra.
"""
import sqlite3

from . import auth
from .db import row

LEVELS = {
    "public": "Công khai",
    "internal": "Nội bộ",
    "restricted": "Hạn chế (theo đơn vị)",
    "secret": "Mật (chỉ Ban TGĐ/Admin)",
}
DEFAULT_LEVEL = "internal"


def is_exec(user: dict) -> bool:
    return user["role"] in auth.EDIT_ALL_ROLES


def unit_tree(conn: sqlite3.Connection, unit_id: int | None) -> set[int]:
    """Đơn vị này và mọi đơn vị con."""
    if not unit_id:
        return set()
    ids, frontier = {unit_id}, [unit_id]
    while frontier:
        children = [r[0] for r in conn.execute(
            f"SELECT id FROM units WHERE parent_id IN ({','.join('?' * len(frontier))})", frontier)]
        frontier = [c for c in children if c not in ids]
        ids.update(frontier)
    return ids


def doc_scope(conn: sqlite3.Connection, user: dict, alias: str = "d") -> tuple[str, list]:
    """Mệnh đề SQL (và tham số) giới hạn bảng documents theo quyền của user.

    Tài liệu 'private' (file đính kèm chat) chỉ thuộc về chủ của nó, kể cả admin/ceo: tìm kiếm và trợ lý AI của người
    khác không bao giờ chạm tới. Admin/ceo xem được file riêng của người khác qua màn quản lý (can_view_doc as_admin)."""
    own = f"({alias}.access_level = 'private' AND {alias}.owner_id = ?)"
    if is_exec(user):
        return f"({alias}.access_level != 'private' OR {own})", [user["id"]]
    clause = f"({alias}.access_level IN ('public', 'internal') OR {own}"
    params: list = [user["id"]]
    units = unit_tree(conn, user.get("unit_id"))
    if units:
        clause += f" OR ({alias}.access_level = 'restricted' AND {alias}.unit_id IN ({','.join('?' * len(units))}))"
        params += sorted(units)
    return clause + ")", params


def visible_doc_ids(conn: sqlite3.Connection, user: dict, include_private: bool = True) -> set[int]:
    """Tập id tài liệu user được dùng khi tìm kiếm/đọc. include_private=False: chỉ thư viện chung (không kèm file riêng)."""
    where, params = doc_scope(conn, user)
    if not include_private:
        where += " AND d.access_level != 'private'"
    return {r[0] for r in conn.execute(f"SELECT d.id FROM documents d WHERE {where}", params)}


def can_view_doc(conn: sqlite3.Connection, user: dict, doc_id: int, as_admin: bool = False) -> bool:
    """as_admin=True (chỉ dùng cho màn quản lý do người thật thao tác, không dùng cho AI): admin/ceo xem được mọi tài liệu."""
    if as_admin and is_exec(user):
        return conn.execute("SELECT 1 FROM documents WHERE id = ?", (doc_id,)).fetchone() is not None
    where, params = doc_scope(conn, user)
    return conn.execute(f"SELECT 1 FROM documents d WHERE d.id = ? AND {where}", [doc_id, *params]).fetchone() is not None


def settable_levels(user: dict) -> list[str]:
    """Độ mật user được gán cho tài liệu: chỉ admin/ceo được đặt 'Mật'."""
    return list(LEVELS) if is_exec(user) else [k for k in LEVELS if k != "secret"]


def check_level(user: dict, level: str) -> str:
    from fastapi import HTTPException
    if level not in LEVELS:
        raise HTTPException(400, "Độ mật không hợp lệ")
    if level not in settable_levels(user):
        raise HTTPException(403, "Chỉ admin/Ban Tổng Giám đốc được đặt tài liệu ở mức Mật")
    return level


def check_doc_write(conn: sqlite3.Connection, user: dict, doc_id: int) -> dict:
    """Tài liệu phải thấy được mới sửa/xoá được; tài liệu Mật chỉ admin/ceo. Không thấy thì báo 'không tìm thấy' (không lộ tồn tại)."""
    from fastapi import HTTPException
    d = row(conn, "SELECT unit_id, stored_path, access_level FROM documents WHERE id = ?", (doc_id,))
    if not d or not can_view_doc(conn, user, doc_id) or d["access_level"] == "private":
        raise HTTPException(404, "Không tìm thấy tài liệu")  # file riêng chỉ sửa/xoá qua /api/my-files
    if d["access_level"] == "secret" and not is_exec(user):
        raise HTTPException(403, "Tài liệu Mật chỉ admin/Ban Tổng Giám đốc được chỉnh sửa")
    return d


def target_units(conn: sqlite3.Connection, user: dict) -> set[int] | None:
    """Mục tiêu doanh thu/lợi nhuận là số nhạy cảm: chỉ xem mục tiêu của đơn vị mình quản lý (None = tất cả)."""
    return auth.managed_unit_ids(conn, user)
