"""Thông tin của chính người đăng nhập: liên kết tài khoản ↔ hồ sơ nhân sự, xem hồ sơ của mình, yêu cầu sửa thông tin sai.

Nguyên tắc:
- Liên kết do admin gán (users.employee_id), không suy từ tên lúc hỏi. Mỗi hồ sơ chỉ gắn một tài khoản.
- AI không nhận SĐT/email/ngày sinh/hợp đồng. Khi người dùng hỏi "thông tin của tôi", AI chỉ viết dấu [[TT]]; máy chủ thay bằng
  hồ sơ của ĐÚNG tài khoản đang xem (dấu không mang id nên AI không thể xin hồ sơ người khác).
- AI không sửa dữ liệu. Người dùng gửi yêu cầu sửa cho hồ sơ của chính mình; chỉ admin duyệt mới ghi vào bảng nhân sự,
  có lưu giá trị cũ/mới và nhật ký.
"""
import re
import sqlite3

from .contacts import EMAIL, _fold
from .db import row, rows

SELF_MARKER = re.compile(r"\[\[TT\]\]")
MAX_PENDING = 10

# trường người dùng được đề nghị sửa: nhãn tiếng Việt
FIELDS = {
    "full_name": "Họ tên",
    "phone": "Số điện thoại",
    "email": "Email",
    "birth_date": "Ngày sinh",
    "joined_date": "Ngày vào công ty",
    "job_title": "Chức danh",
    "contract_term": "Loại hợp đồng",
}
# thông tin riêng của chính người đó, rủi ro thấp: tự sửa ghi thẳng vào hồ sơ (có nhật ký giá trị cũ/mới); các trường còn lại chờ admin duyệt
DIRECT_FIELDS = ("phone", "email", "birth_date")
STATUS_LABELS = {"pending": "Chờ duyệt", "approved": "Đã duyệt", "rejected": "Từ chối"}


def clean_value(field: str, raw) -> str:
    """Chuẩn hoá và kiểm tra giá trị đề nghị; ValueError (thông báo tiếng Việt) nếu không hợp lệ."""
    from . import hr_contacts  # import muộn: hr_contacts kéo theo openpyxl
    if field not in FIELDS:
        raise ValueError("Trường này không được đề nghị sửa")
    text = " ".join(str(raw or "").split())
    if not text:
        raise ValueError("Giá trị mới không được để trống")
    if len(text) > 120:
        raise ValueError("Giá trị quá dài")
    if field == "phone":
        phone = hr_contacts.normalize_phone(text)
        if not phone:
            raise ValueError("Số điện thoại không hợp lệ (cần 10 số, ví dụ 0912345678)")
        return phone
    if field == "email":
        if not EMAIL.fullmatch(text):
            raise ValueError("Email không hợp lệ")
        return text.lower()
    if field in ("birth_date", "joined_date"):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            date = hr_contacts.normalize_date(f"{text[8:]}/{text[5:7]}/{text[:4]}")
        else:
            date = hr_contacts.normalize_date(text)
        if not date:
            raise ValueError("Ngày không hợp lệ (nhập dạng 30/03/2011)")
        return date
    return text


def _employee(conn, employee_id: int) -> dict | None:
    return row(conn, "SELECT e.*, u.name AS unit_name FROM employees e LEFT JOIN units u ON u.id = e.unit_id WHERE e.id = ?",
               (employee_id,))


def profile(conn, employee_id: int | None) -> dict | None:
    """Hồ sơ đầy đủ (kể cả SĐT/email/ngày sinh): CHỈ trả cho chính chủ hoặc admin."""
    if not employee_id:
        return None
    emp = _employee(conn, employee_id)
    if not emp:
        return None
    emp["roles"] = rows(conn, "SELECT p.title, u.name AS unit_name FROM positions p JOIN units u ON u.id = p.unit_id"
                              " WHERE p.employee_id = ? ORDER BY p.sort_order", (employee_id,))
    return emp


def identity_note(employee_id: int | None) -> str:
    """Câu báo cho AI người đang hỏi là ai trong danh sách nhân sự (chỉ tên/chức danh/đơn vị, không có dữ liệu cá nhân)."""
    from .db import connect
    if not employee_id:
        return ("Tài khoản của người đang hỏi CHƯA được liên kết với hồ sơ nhân sự, nên chưa thể tra thông tin cá nhân của họ.")
    with connect() as conn:
        emp = _employee(conn, employee_id)
    if not emp:
        return "Tài khoản của người đang hỏi CHƯA được liên kết với hồ sơ nhân sự."
    place = " – ".join(p for p in (emp.get("job_title"), emp.get("unit_name")) if p)
    return (f"Người đang hỏi chính là nhân viên \"{emp['full_name']}\"" + (f" ({place})" if place else "")
            + f", id nhân sự {emp['id']}. Khi họ nói \"tôi\", \"của tôi\" thì hiểu là người này.")


def _fmt_date(value: str | None) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else (value or "")


def render_profile(emp: dict | None) -> str:
    """Khối hồ sơ (markdown) thay cho dấu [[TT]]."""
    if not emp:
        return ("(Tài khoản của bạn chưa được liên kết với hồ sơ nhân sự. Hãy nhờ quản trị viên gán tài khoản ở mục Tài khoản.)")
    lines = [("Họ tên", emp["full_name"]), ("Mã nhân viên", emp.get("employee_code")), ("Chức danh", emp.get("job_title")),
             ("Đơn vị", emp.get("unit_name") or emp.get("hr_department")), ("Khối", emp.get("hr_division")),
             ("Số điện thoại", emp.get("phone")), ("Email", emp.get("email")),
             ("Ngày sinh", _fmt_date(emp.get("birth_date"))), ("Ngày vào công ty", _fmt_date(emp.get("joined_date"))),
             ("Loại hợp đồng", emp.get("contract_term"))]
    out = [f"- **{label}:** {value or '_chưa có dữ liệu_'}" for label, value in lines
           if value or label in ("Số điện thoại", "Email", "Ngày sinh", "Ngày vào công ty", "Loại hợp đồng")]
    if emp.get("roles"):
        out.append("- **Chức vụ trên sơ đồ:** " + "; ".join(f"{r['title']} – {r['unit_name']}" for r in emp["roles"]))
    return "\n".join(out)


def apply_marker(conn, user: dict, text: str) -> str:
    """Thay [[TT]] bằng hồ sơ của chính người đang xem. Không có dấu thì trả nguyên văn."""
    if not SELF_MARKER.search(text or ""):
        return text
    block = render_profile(profile(conn, user.get("employee_id")))
    return SELF_MARKER.sub(lambda _: "\n" + block + "\n", text)


# ---------------- Liên kết tài khoản ↔ nhân sự (admin) ----------------
def link_options(conn) -> dict:
    """Danh sách nhân sự để chọn khi gán (không kèm SĐT/email) và gợi ý tự động theo họ tên (chỉ khi khớp đúng một người)."""
    emps = rows(conn, "SELECT e.id, e.full_name, e.display_name, e.job_title, u.name AS unit_name,"
                      " (SELECT x.id FROM users x WHERE x.employee_id = e.id) AS linked_user_id"
                      " FROM employees e LEFT JOIN units u ON u.id = e.unit_id WHERE e.status = 'active' ORDER BY e.full_name")
    by_name: dict[str, list[dict]] = {}
    for e in emps:
        for name in {_fold(e["full_name"]), _fold(e["display_name"] or "")} - {""}:
            by_name.setdefault(name, []).append(e)
    suggestions = {}
    for u in rows(conn, "SELECT id, full_name FROM users WHERE employee_id IS NULL AND active = 1 AND full_name IS NOT NULL"):
        found = {e["id"]: e for e in by_name.get(_fold(u["full_name"]), []) if not e["linked_user_id"]}
        if len(found) == 1:
            suggestions[u["id"]] = next(iter(found))
    return {"employees": emps, "suggestions": suggestions}


def link(conn, user_id: int, employee_id: int | None) -> dict:
    """Gán (hoặc gỡ khi employee_id rỗng) hồ sơ nhân sự cho tài khoản. ValueError nếu không hợp lệ."""
    if not row(conn, "SELECT id FROM users WHERE id = ?", (user_id,)):
        raise ValueError("Không tìm thấy tài khoản")
    if employee_id:
        emp = row(conn, "SELECT id, full_name FROM employees WHERE id = ?", (employee_id,))
        if not emp:
            raise ValueError("Không tìm thấy nhân viên này trong danh sách nhân sự")
        other = row(conn, "SELECT username FROM users WHERE employee_id = ? AND id != ?", (employee_id, user_id))
        if other:
            raise ValueError(f"Hồ sơ này đã gắn với tài khoản {other['username']}. Gỡ liên kết đó trước.")
    conn.execute("UPDATE users SET employee_id = ? WHERE id = ?", (employee_id or None, user_id))
    return {"employee_id": employee_id or None}


# ---------------- Người dùng tự xin liên kết (admin duyệt) ----------------
def free_employees(conn) -> list[dict]:
    """Nhân sự đang làm việc và chưa gắn tài khoản nào, để người dùng chọn hồ sơ của mình (không kèm SĐT/email)."""
    return rows(conn, "SELECT e.id, e.full_name, e.job_title, u.name AS unit_name FROM employees e"
                      " LEFT JOIN units u ON u.id = e.unit_id WHERE e.status = 'active'"
                      " AND NOT EXISTS (SELECT 1 FROM users x WHERE x.employee_id = e.id) ORDER BY e.full_name")


def submit_link(conn, user: dict, employee_id) -> dict:
    """Người dùng chọn hồ sơ của mình; chưa liên kết cho tới khi admin duyệt. Gửi lại thì thay đơn đang chờ."""
    if user.get("employee_id"):
        raise ValueError("Tài khoản của bạn đã được liên kết với hồ sơ nhân sự")
    emp = row(conn, "SELECT id FROM employees WHERE id = ? AND status = 'active'", (employee_id,)) if employee_id else None
    if not emp:
        raise ValueError("Hãy chọn một nhân viên trong danh sách")
    if row(conn, "SELECT 1 AS x FROM users WHERE employee_id = ?", (emp["id"],)):
        raise ValueError("Hồ sơ này đã gắn với một tài khoản khác. Hãy liên hệ quản trị viên nếu đó là hồ sơ của bạn.")
    conn.execute("DELETE FROM link_requests WHERE user_id = ? AND status = 'pending'", (user["id"],))
    cur = conn.execute("INSERT INTO link_requests (user_id, employee_id) VALUES (?,?)", (user["id"], emp["id"]))
    return {"id": cur.lastrowid}


def notice_count(conn, user_id: int) -> int:
    """Số kết quả duyệt (liên kết hồ sơ, sửa thông tin) mà người dùng chưa xem: hiện ở huy hiệu menu."""
    return sum(conn.execute(f"SELECT COUNT(*) FROM {t} WHERE user_id = ? AND seen_by_user = 0", (user_id,)).fetchone()[0]
               for t in ("link_requests", "employee_change_requests"))


def link_notice(conn, user_id: int) -> dict | None:
    """Kết quả duyệt liên kết mới nhất mà người dùng chưa xem (duyệt hoặc từ chối)."""
    return row(conn, "SELECT r.status, r.admin_note, e.full_name AS employee_name FROM link_requests r"
                     " JOIN employees e ON e.id = r.employee_id WHERE r.user_id = ? AND r.seen_by_user = 0"
                     " ORDER BY r.id DESC LIMIT 1", (user_id,))


def mark_seen(conn, user_id: int) -> None:
    for t in ("link_requests", "employee_change_requests"):
        conn.execute(f"UPDATE {t} SET seen_by_user = 1 WHERE user_id = ? AND seen_by_user = 0", (user_id,))


def my_link_request(conn, user_id: int) -> dict | None:
    """Đơn liên kết gần nhất của người dùng (đang chờ, hoặc kết quả vừa có nếu bị từ chối)."""
    return row(conn, "SELECT r.id, r.status, r.created_at, r.admin_note, e.full_name AS employee_name, e.job_title"
                     " FROM link_requests r JOIN employees e ON e.id = r.employee_id"
                     " WHERE r.user_id = ? AND r.status != 'approved' ORDER BY r.id DESC LIMIT 1", (user_id,))


def withdraw_link(conn, user_id: int, req_id: int) -> None:
    cur = conn.execute("DELETE FROM link_requests WHERE id = ? AND user_id = ? AND status = 'pending'", (req_id, user_id))
    if not cur.rowcount:
        raise ValueError("Không tìm thấy yêu cầu đang chờ duyệt")


def list_link_requests(conn) -> list[dict]:
    return rows(conn, "SELECT r.id, r.created_at, u.username, u.full_name AS user_name, e.full_name AS employee_name, e.job_title,"
                      " x.name AS unit_name FROM link_requests r JOIN users u ON u.id = r.user_id"
                      " JOIN employees e ON e.id = r.employee_id LEFT JOIN units x ON x.id = e.unit_id"
                      " WHERE r.status = 'pending' ORDER BY r.id")


def decide_link(conn, admin: dict, req_id: int, approve: bool, note: str = "") -> dict:
    req = row(conn, "SELECT * FROM link_requests WHERE id = ?", (req_id,))
    if not req or req["status"] != "pending":
        raise ValueError("Yêu cầu không còn ở trạng thái chờ duyệt")
    if approve:
        link(conn, req["user_id"], req["employee_id"])  # ValueError nếu hồ sơ đã gắn tài khoản khác
    conn.execute("UPDATE link_requests SET status = ?, decided_by = ?, decided_at = datetime('now','localtime'), admin_note = ?,"
                 " seen_by_user = 0 WHERE id = ?", ("approved" if approve else "rejected", admin["id"], (note or "")[:300], req_id))
    return {"status": "approved" if approve else "rejected"}


# ---------------- Yêu cầu sửa thông tin ----------------
def submit(conn, user: dict, field: str, value, reason: str = "") -> dict:
    """Người dùng đề nghị sửa một trường trong hồ sơ CỦA CHÍNH MÌNH. ValueError nếu không hợp lệ."""
    emp_id = user.get("employee_id")
    emp = _employee(conn, emp_id) if emp_id else None
    if not emp:
        raise ValueError("Tài khoản của bạn chưa được liên kết với hồ sơ nhân sự, chưa gửi yêu cầu sửa được")
    new = clean_value(field, value)
    old = emp.get(field)
    if (old or "") == new:
        raise ValueError("Giá trị mới trùng với dữ liệu hiện tại")
    # mỗi trường chỉ giữ một yêu cầu đang chờ: gửi lại thì thay giá trị cũ
    existing = row(conn, "SELECT id FROM employee_change_requests WHERE user_id = ? AND field = ? AND status = 'pending'",
                   (user["id"], field))
    if existing:
        conn.execute("UPDATE employee_change_requests SET new_value = ?, old_value = ?, reason = ?,"
                     " created_at = datetime('now','localtime') WHERE id = ?", (new, old, (reason or "")[:300], existing["id"]))
        return {"id": existing["id"], "replaced": True}
    pending = conn.execute("SELECT COUNT(*) FROM employee_change_requests WHERE user_id = ? AND status = 'pending'",
                           (user["id"],)).fetchone()[0]
    if pending >= MAX_PENDING:
        raise ValueError("Bạn đang có quá nhiều yêu cầu chờ duyệt")
    cur = conn.execute("INSERT INTO employee_change_requests (user_id, employee_id, field, old_value, new_value, reason)"
                       " VALUES (?,?,?,?,?,?)", (user["id"], emp_id, field, old, new, (reason or "")[:300]))
    return {"id": cur.lastrowid, "replaced": False}


def submit_many(conn, user: dict, values: dict, reason: str = "") -> dict:
    """Người dùng cập nhật nhiều thông tin cùng lúc (form đã điền sẵn giá trị hiện tại): trường để trống hoặc không đổi thì bỏ qua.
    DIRECT_FIELDS ghi thẳng vào hồ sơ (kèm nhật ký), trường còn lại gửi yêu cầu chờ admin duyệt. Kiểm tra hết trước khi ghi.
    Trả về {"applied": [...], "pending": [...]} (tên trường)."""
    emp_id = user.get("employee_id")
    emp = _employee(conn, emp_id) if emp_id else None
    if not emp:
        raise ValueError("Tài khoản của bạn chưa được liên kết với hồ sơ nhân sự, chưa gửi yêu cầu sửa được")
    todo = {}
    for field, raw in (values or {}).items():
        if field not in FIELDS or not str(raw or "").strip():
            continue
        try:
            new = clean_value(field, raw)
        except ValueError as e:
            raise ValueError(f"{FIELDS[field]}: {e}") from None
        if new != (emp.get(field) or ""):
            todo[field] = new
    if not todo:
        raise ValueError("Bạn chưa thay đổi thông tin nào")
    out = {"applied": [], "pending": []}
    for field, new in todo.items():
        if field in DIRECT_FIELDS:
            conn.execute(f"UPDATE employees SET {field} = ? WHERE id = ?", (new, emp_id))
            conn.execute("DELETE FROM employee_change_requests WHERE user_id = ? AND field = ? AND status = 'pending'",
                         (user["id"], field))  # đơn cũ cùng trường không còn ý nghĩa
            conn.execute("INSERT INTO audit_log (action, entity, entity_id, detail, user_id) VALUES (?,?,?,?,?)",
                         ("profile_self_edit", "employees", emp_id, f"{field}: {emp.get(field)!r} -> {new!r}", user["id"]))
            out["applied"].append(field)
        else:
            submit(conn, user, field, new, reason)
            out["pending"].append(field)
    return out


def my_requests(conn, user_id: int) -> list[dict]:
    return rows(conn, "SELECT id, field, old_value, new_value, reason, status, created_at, decided_at, admin_note, seen_by_user"
                      " FROM employee_change_requests WHERE user_id = ? ORDER BY id DESC LIMIT 30", (user_id,))


def withdraw(conn, user_id: int, req_id: int) -> None:
    cur = conn.execute("DELETE FROM employee_change_requests WHERE id = ? AND user_id = ? AND status = 'pending'",
                       (req_id, user_id))
    if not cur.rowcount:
        raise ValueError("Không tìm thấy yêu cầu đang chờ duyệt")


def list_requests(conn, status: str | None = "pending") -> list[dict]:
    sql = ("SELECT r.*, u.username, u.full_name AS user_name, e.full_name AS employee_name, e.job_title"
           " FROM employee_change_requests r JOIN users u ON u.id = r.user_id JOIN employees e ON e.id = r.employee_id")
    if status:
        return rows(conn, sql + " WHERE r.status = ? ORDER BY r.id DESC LIMIT 200", (status,))
    return rows(conn, sql + " ORDER BY r.id DESC LIMIT 200")


def decide(conn, admin: dict, req_id: int, approve: bool, note: str = "") -> dict:
    """Admin duyệt/từ chối. Duyệt: ghi giá trị mới vào hồ sơ nhân sự và nhật ký (giữ giá trị cũ để khôi phục)."""
    req = row(conn, "SELECT * FROM employee_change_requests WHERE id = ?", (req_id,))
    if not req or req["status"] != "pending":
        raise ValueError("Yêu cầu không còn ở trạng thái chờ duyệt")
    if approve:
        value = clean_value(req["field"], req["new_value"])  # kiểm tra lại trước khi ghi
        owner = row(conn, "SELECT employee_id FROM users WHERE id = ?", (req["user_id"],))
        if not owner or owner["employee_id"] != req["employee_id"]:
            raise ValueError("Tài khoản này không còn liên kết với hồ sơ đó nên không thể duyệt")
        current = row(conn, f"SELECT {req['field']} AS v FROM employees WHERE id = ?", (req["employee_id"],))
        conn.execute(f"UPDATE employees SET {req['field']} = ? WHERE id = ?", (value, req["employee_id"]))
        conn.execute("INSERT INTO audit_log (action, entity, entity_id, detail, user_id) VALUES (?,?,?,?,?)",
                     ("profile_change", "employees", req["employee_id"],
                      f"{req['field']}: {(current or {}).get('v')!r} -> {value!r} (yêu cầu #{req_id})", admin["id"]))
    conn.execute("UPDATE employee_change_requests SET status = ?, decided_by = ?, decided_at = datetime('now','localtime'),"
                 " admin_note = ?, seen_by_user = 0 WHERE id = ?", ("approved" if approve else "rejected", admin["id"], (note or "")[:300], req_id))
    return {"status": "approved" if approve else "rejected"}
