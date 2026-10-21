"""Thông tin liên hệ nhân sự trong trợ lý AI.

Nguyên tắc: SĐT và email KHÔNG bao giờ đi tới nhà cung cấp AI (Gemini/Groq) và KHÔNG nằm trong văn bản do AI viết.
- AI chỉ chọn người bằng dấu [[LH:<id>]] (id = mã bản ghi nhân viên), đặt ngay sau họ tên đầy đủ.
- Máy chủ tra số từ bảng nhân sự theo đúng id đó, và chỉ điền vào khi hiển thị cho người có quyền.
- Dấu chỉ được chấp nhận khi họ tên của đúng nhân viên đó xuất hiện ngay trước dấu; nếu không thì không điền số (fail closed).
"""
import re
import unicodedata

from .db import rows

MARKER = re.compile(r"\[\[LH:(\d+)\]\]")
PHONE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.-]?\d){8,9}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
HIDDEN = "[đã ẩn]"
NAME_WINDOW = 150  # số ký tự trước dấu được tìm họ tên


def _fold(s: str) -> str:
    """Chữ thường, bỏ dấu (kể cả đ), gom khoảng trắng: để so khớp tên không phụ thuộc cách gõ dấu."""
    s = unicodedata.normalize("NFD", s or "").replace("đ", "d").replace("Đ", "d")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.lower().split())


def scrub(text: str) -> str:
    """Che mọi SĐT/email trong văn bản (dùng cho câu hỏi người dùng, lịch sử và câu trả lời AI viết)."""
    text = EMAIL.sub(HIDDEN, text or "")
    return PHONE.sub(HIDDEN, text)


def marker_ids(text: str) -> set[int]:
    return {int(m) for m in MARKER.findall(text or "")}


def load(conn, ids: set[int]) -> dict[int, dict]:
    """Thông tin nhân sự theo id, lấy trực tiếp từ bảng nhân sự (nguồn duy nhất của số điện thoại/email)."""
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    found = rows(conn, "SELECT e.id, e.full_name, e.display_name, e.job_title, e.phone, e.email, u.name AS unit_name"
                       f" FROM employees e LEFT JOIN units u ON u.id = e.unit_id WHERE e.id IN ({marks})", list(ids))
    return {r["id"]: r for r in found}


def _name_matches(emp: dict, before: str) -> bool:
    ctx = _fold(before)
    return any(_fold(name) and _fold(name) in ctx for name in (emp.get("full_name"), emp.get("display_name")))


def render(text: str, employees: dict[int, dict], can_see: bool) -> str:
    """Thay mỗi dấu [[LH:id]] bằng tên, chức danh, đơn vị và (nếu có quyền) SĐT/email của đúng nhân viên đó."""
    def repl(m: re.Match) -> str:
        emp = employees.get(int(m.group(1)))
        if emp is None:
            return "(không tìm thấy nhân viên này trong dữ liệu)"
        if not _name_matches(emp, text[max(0, m.start() - NAME_WINDOW):m.start()]):
            return "(chưa xác minh được người này; hãy hỏi lại kèm họ tên đầy đủ)"
        info = emp["full_name"]
        place = " – ".join(p for p in (emp.get("job_title"), emp.get("unit_name")) if p)
        if place:
            info += f" ({place})"
        if not can_see:
            return info
        contacts = [f"SĐT: {emp['phone']}" if emp.get("phone") else "", f"email: {emp['email']}" if emp.get("email") else ""]
        contacts = [c for c in contacts if c]
        return f"{info}: {', '.join(contacts)}" if contacts else f"{info} (chưa có SĐT/email trong dữ liệu)"
    return MARKER.sub(repl, text or "")


def render_for_viewer(conn, text: str, can_see: bool) -> str:
    """Điền liên hệ vào văn bản đã lưu (chỉ đọc dữ liệu hiện tại, không lưu lại số vào lịch sử)."""
    return render(text, load(conn, marker_ids(text)), can_see)
