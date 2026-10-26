"""Bổ sung đơn vị / chức danh còn thiếu so với sơ đồ gốc REV02, KHÔNG xoá hay ghi đè dữ liệu đang có.

Chạy: python -m backend.org_sync
(khác `backend.seed` vốn xoá và nạp lại toàn bộ: tên người đã điền cho các ô TBA được giữ nguyên.)
"""
import sqlite3

from .db import connect, init_db
from .seed import EMPLOYEES, POSITIONS, UNITS

_EMP = {key: (full, display, verified) for key, full, display, verified in EMPLOYEES}


def sync(conn: sqlite3.Connection) -> list[str]:
    """Trả về danh sách thay đổi đã thực hiện (rỗng nếu dữ liệu đã đủ)."""
    log: list[str] = []
    unit_ids = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM units")}

    for i, (code, name, full, utype, parent, color, verified, notes) in enumerate(UNITS):
        if code in unit_ids:
            continue
        cur = conn.execute(
            "INSERT INTO units (code, name, full_name, unit_type, parent_id, color_group, verified, notes, sort_order)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (code, name, full, utype, unit_ids.get(parent), color, verified, notes, i),
        )
        unit_ids[code] = cur.lastrowid
        log.append(f"Thêm đơn vị {name}")

    seed_count: dict[tuple[str, str], int] = {}
    for ucode, _t, tcode, *_ in POSITIONS:
        seed_count[(ucode, tcode)] = seed_count.get((ucode, tcode), 0) + 1

    def employee_id_of(key):
        full, display, _v = _EMP[key]
        r = conn.execute("SELECT id FROM employees WHERE full_name = ? OR display_name = ?", (full, display)).fetchone()
        return r["id"] if r else None

    for i, (ucode, title, tcode, ekey, is_head, *rest) in enumerate(POSITIONS):
        uid = unit_ids[ucode]
        have = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE unit_id = ? AND title_code = ?", (uid, tcode)
        ).fetchone()[0]
        if have >= seed_count[(ucode, tcode)]:
            continue
        emp_id = None
        if ekey:
            full, display, verified = _EMP[ekey]
            same = conn.execute(
                "SELECT e.id FROM employees e WHERE e.full_name = ? OR e.display_name = ?", (full, display)
            ).fetchone()
            if same and conn.execute(
                "SELECT 1 FROM positions WHERE unit_id = ? AND employee_id = ?", (uid, same["id"])
            ).fetchone():
                continue  # người này đã có chức danh khác trong đơn vị
            emp_id = same["id"] if same else conn.execute(
                "INSERT INTO employees (full_name, display_name, verified, notes) VALUES (?,?,?,?)",
                (full, display, verified, None if verified else "Tên đang viết tắt theo sơ đồ – cần bổ sung họ tên đầy đủ."),
            ).lastrowid
        conn.execute(
            "INSERT INTO positions (unit_id, title, title_code, employee_id, is_head, sort_order, reports_to_employee_id)"
            " VALUES (?,?,?,?,?,?,?)",
            (uid, title, tcode, emp_id, is_head, i, employee_id_of(rest[0]) if rest else None),
        )
        log.append(f"Thêm chức danh {tcode} ({full if ekey else 'TBA'}) vào {ucode}")
    return log


def main() -> None:
    init_db()
    with connect() as conn:
        conn.row_factory = sqlite3.Row
        changes = sync(conn)
        if changes:
            conn.execute(
                "INSERT INTO audit_log (action, entity, detail) VALUES ('org_sync','units',?)",
                (f"Bổ sung {len(changes)} mục theo sơ đồ gốc REV02",),
            )
    print("\n".join(changes) if changes else "Sơ đồ đã đủ, không có gì cần bổ sung.")


if __name__ == "__main__":
    main()
