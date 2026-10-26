"""Truy vấn tổng hợp dùng chung cho API và trợ lý AI."""
import re
import sqlite3
import unicodedata
from datetime import date

from .db import row, rows

# Loại tài liệu được coi là "đơn vị đã có quy trình / quy định" (bảng processes có cấu trúc đang ít dùng, quy trình thực tế
# nằm trong kho tài liệu)
INTERNAL_DOC_TYPES = "('quy_trinh', 'quy_dinh', 'ram', 'huong_dan', 'bieu_mau', 'so_tay')"
REVIEW_DAYS = 365  # quy trình/tài liệu nội bộ cần rà soát sau 12 tháng

POSITION_SQL = """
SELECT p.id, p.unit_id, p.title, p.title_code, p.is_head, p.headcount, p.notes,
       p.employee_id, e.full_name AS employee_name, e.verified AS employee_verified,
       p.reports_to_employee_id, r.full_name AS reports_to_name
FROM positions p LEFT JOIN employees e ON e.id = p.employee_id
LEFT JOIN employees r ON r.id = p.reports_to_employee_id
"""


def units_flat(conn: sqlite3.Connection) -> list[dict]:
    units = rows(conn, "SELECT * FROM units ORDER BY sort_order, id")
    heads = rows(conn, POSITION_SQL + " WHERE p.is_head = 1 ORDER BY p.sort_order")
    counts = {
        r["unit_id"]: r
        for r in rows(
            conn,
            """SELECT u.id AS unit_id,
                      (SELECT COUNT(*) FROM processes WHERE unit_id = u.id) AS process_count,
                      (SELECT COUNT(*) FROM targets WHERE unit_id = u.id) AS target_count,
                      (SELECT COUNT(*) FROM positions WHERE unit_id = u.id) AS position_count,
                      (SELECT COUNT(*) FROM documents d WHERE doc_type IN """ + INTERNAL_DOC_TYPES + """
                          AND (d.unit_id = u.id OR d.id IN (SELECT doc_id FROM document_units WHERE unit_id = u.id)))
                          AS doc_count
               FROM units u""",
        )
    }
    deputies = rows(conn, POSITION_SQL + " WHERE p.is_head = 0 ORDER BY p.sort_order")
    for u in units:
        h = next((h for h in heads if h["unit_id"] == u["id"]), None)
        u["head"] = (
            {"title_code": h["title_code"], "title": h["title"], "name": h["employee_name"] or "TBA"} if h else None
        )
        # Các chức danh phó (PP...) hiển thị cùng ô trên sơ đồ, như sơ đồ gốc
        u["deputies"] = [
            {"title_code": d["title_code"], "name": d["employee_name"] or "TBA"}
            for d in deputies if d["unit_id"] == u["id"]
        ]
        u.update({k: v for k, v in counts.get(u["id"], {}).items() if k != "unit_id"})
    return units


def org_tree(conn: sqlite3.Connection) -> list[dict]:
    units = units_flat(conn)
    by_id = {u["id"]: {**u, "children": []} for u in units}
    roots = []
    for u in by_id.values():
        parent = by_id.get(u["parent_id"])
        (parent["children"] if parent else roots).append(u)
    return roots


def unit_detail(conn: sqlite3.Connection, unit_id: int) -> dict | None:
    u = row(conn, "SELECT * FROM units WHERE id = ?", (unit_id,))
    if not u:
        return None
    u["parent"] = row(conn, "SELECT id, code, name FROM units WHERE id = ?", (u["parent_id"],))
    u["children"] = rows(conn, "SELECT id, code, name, unit_type FROM units WHERE parent_id = ? ORDER BY sort_order",
                         (unit_id,))
    u["positions"] = rows(conn, POSITION_SQL + " WHERE p.unit_id = ? ORDER BY p.is_head DESC, p.sort_order", (unit_id,))
    # Nhân sự thực tế theo danh sách HCNS (giống bảng "Nhân sự theo danh sách HCNS" trên giao diện)
    u["reports_to"] = manager_lookup(conn)(unit_id)
    u["members"] = rows(conn, "SELECT id, employee_code, full_name, job_title, grade FROM employees"
                              " WHERE unit_id = ? AND status != 'inactive' ORDER BY sort_order = 0, sort_order, full_name",
                        (unit_id,))
    u["member_count"] = len(u["members"])
    head = next((p for p in u["positions"] if p["is_head"]), None)
    u["head"] = {"title": head["title"], "name": head["employee_name"] or "TBA (chưa có người)"} if head else None
    u["processes"] = rows(conn, "SELECT * FROM processes WHERE unit_id = ? ORDER BY code, name", (unit_id,))
    # Tài liệu nội bộ của đơn vị (quy trình, quy định, RAM...) trong kho tài liệu
    u["documents"] = rows(conn, "SELECT id AS doc_id, title, doc_type, version FROM documents WHERE (unit_id = ? OR id IN"
                                " (SELECT doc_id FROM document_units WHERE unit_id = ?))"
                                " AND doc_type != 'website' ORDER BY title", (unit_id, unit_id))
    u["targets"] = rows(conn, "SELECT * FROM targets WHERE unit_id = ? ORDER BY period DESC, metric", (unit_id,))
    return u


def employee_roles(conn: sqlite3.Connection, can_see_contacts=lambda e: False) -> list[dict]:
    """Danh sách nhân sự kèm chức danh. Email / số điện thoại chỉ đưa ra với người được `can_see_contacts` cho phép
    (mặc định: không ai). Dữ liệu này cũng được gửi cho nhà cung cấp AI nên trợ lý không lấy liên hệ."""
    emps = rows(conn, "SELECT e.*, u.name AS unit_name FROM employees e LEFT JOIN units u ON u.id = e.unit_id"
                      " ORDER BY e.sort_order = 0, e.sort_order, e.full_name")
    for e in emps:
        if not can_see_contacts(e):
            e.pop("email", None)
            e.pop("phone", None)
    roles = rows(
        conn,
        """SELECT p.employee_id, p.title, p.title_code, p.is_head, u.id AS unit_id, u.name AS unit_name,
                  r.full_name AS reports_to_name
           FROM positions p JOIN units u ON u.id = p.unit_id
           LEFT JOIN employees r ON r.id = p.reports_to_employee_id
           WHERE p.employee_id IS NOT NULL ORDER BY p.sort_order""",
    )
    for e in emps:
        e["roles"] = [r for r in roles if r["employee_id"] == e["id"]]
    return emps


def manager_lookup(conn: sqlite3.Connection):
    """Trả về hàm unit_id -> "Chức danh Họ tên" của cấp quản lý trực tiếp: đi lên cây tổ chức đến đơn vị đầu tiên có
    người đứng đầu (vd. P. QA/QC -> PTGĐ Thường trực; phòng thuộc khối chưa có Giám đốc -> người đứng đầu cấp trên của khối)."""
    parents = {r["id"]: r["parent_id"] for r in rows(conn, "SELECT id, parent_id FROM units")}
    head_of = {r["unit_id"]: f'{r["title"]} {r["name"]}' for r in rows(
        conn, "SELECT p.unit_id, p.title, e.full_name AS name FROM positions p JOIN employees e ON e.id = p.employee_id"
              " WHERE p.is_head = 1 ORDER BY p.sort_order DESC")}

    def manager_of(unit_id):
        up = parents.get(unit_id)
        seen = set()
        while up and up not in head_of and up not in seen:
            seen.add(up)
            up = parents.get(up)
        return head_of.get(up)
    return manager_of


def direct_reports_of(conn: sqlite3.Connection, employee_id: int) -> list[dict]:
    """Các đơn vị mà người này là cấp quản lý trực tiếp nhưng không phải người đứng đầu đơn vị đó
    (vd. PTGĐ Thường trực -> P. QA/QC, P. HSSE, các phòng trong khối mình phụ trách), gom theo đơn vị mà người đó giữ chức."""
    parents = {r["id"]: r["parent_id"] for r in rows(conn, "SELECT id, parent_id FROM units ORDER BY sort_order")}
    names = {r["id"]: r["name"] for r in rows(conn, "SELECT id, name FROM units")}
    head_emp = {}
    for r in rows(conn, "SELECT unit_id, employee_id FROM positions WHERE is_head = 1 AND employee_id IS NOT NULL"
                        " ORDER BY sort_order DESC"):
        head_emp[r["unit_id"]] = r["employee_id"]
    out: dict[int, list[int]] = {}
    for uid in parents:
        if head_emp.get(uid) == employee_id:
            continue
        up = parents[uid]
        while up and up not in head_emp:
            up = parents.get(up)
        if up and head_emp[up] == employee_id:
            out.setdefault(up, []).append(uid)
    return [{"via": names[via], "via_id": via, "units": [names[u] for u in ids], "unit_ids": ids}
            for via, ids in out.items()]


HEAD_CODES = ("TP", "TB", "TBP")   # Trưởng phòng / ban / bộ phận
DEPUTY_CODES = ("PP", "PB")        # Phó phòng / ban


def leadership(conn: sqlite3.Connection) -> dict:
    """Số lượng và danh sách trưởng, phó phòng/ban đang có người giữ (vị trí trống đã nằm ở mục TBA)."""
    out = {}
    for key, codes in (("heads", HEAD_CODES), ("deputies", DEPUTY_CODES)):
        people = rows(
            conn,
            f"""SELECT e.id AS employee_id, e.full_name AS name, p.title, u.id AS unit_id, u.name AS unit_name
                FROM positions p JOIN employees e ON e.id = p.employee_id JOIN units u ON u.id = p.unit_id
                WHERE p.title_code IN ({','.join('?' * len(codes))}) ORDER BY u.sort_order, p.sort_order""",
            codes,
        )
        out[key] = {"count": len(people), "people": people}
    return out


def head_label(conn: sqlite3.Connection, unit_id: int) -> str | None:
    r = row(conn, "SELECT p.title, e.full_name AS name FROM positions p LEFT JOIN employees e ON e.id = p.employee_id"
                  " WHERE p.unit_id = ? AND p.is_head = 1 ORDER BY p.sort_order LIMIT 1", (unit_id,))
    return f'{r["title"]} {r["name"] or "(trống)"}' if r else None


def insights(conn: sqlite3.Connection) -> dict:
    """Các chỉ dấu tổ chức tính trực tiếp từ dữ liệu (không suy diễn)."""
    vacancies = rows(
        conn,
        """SELECT u.id AS unit_id, u.name AS unit_name, p.title, p.title_code
           FROM positions p JOIN units u ON u.id = p.unit_id WHERE p.employee_id IS NULL ORDER BY u.sort_order""",
    )
    # Giữ chức ở khối/phòng và ở đơn vị nằm trong nó (vd. Giám đốc Khối và Giám đốc phòng thuộc khối đó) là cùng một mạch
    # quản lý, không phải kiêm nhiệm. Cấp điều hành (PTGĐ, Ban TGĐ) ở trên thì vẫn là một chức riêng nên không gộp.
    parent_of = {r["id"]: r["parent_id"] for r in rows(conn, "SELECT id, parent_id FROM units")}
    line_units = {r["id"] for r in rows(conn, "SELECT id FROM units WHERE unit_type IN ('division', 'department')")}

    def has_held_ancestor(unit_id, held):
        up, seen = parent_of.get(unit_id), set()
        while up and up not in seen:
            if up in held and up in line_units:
                return True
            seen.add(up)
            up = parent_of.get(up)
        return False

    concurrent = []
    for e in employee_roles(conn):
        held = {r["unit_id"] for r in e["roles"]}
        distinct = {u for u in held if not has_held_ancestor(u, held)}
        if len(distinct) > 1:
            concurrent.append({"employee_id": e["id"], "name": e["full_name"],
                               "roles": [f'{r["title"]} – {r["unit_name"]}'
                                         + (f' (báo cáo {r["reports_to_name"]})' if r["reports_to_name"] else "")
                                         for r in e["roles"]],
                               "role_items": [{"title": r["title"], "unit_id": r["unit_id"], "unit_name": r["unit_name"],
                                               "reports_to": r["reports_to_name"]} for r in e["roles"]],
                               "manages": direct_reports_of(conn, e["id"])})
    # Đơn vị cấp phòng/ban mà người phụ trách chỉ là cấp phó (chưa có trưởng)
    deputy_led = rows(
        conn,
        """SELECT u.id AS unit_id, u.name AS unit_name, p.title, e.full_name AS name
           FROM units u JOIN positions p ON p.unit_id = u.id AND p.is_head = 1
           LEFT JOIN employees e ON e.id = p.employee_id
           WHERE u.unit_type = 'department' AND p.title_code IN ('PP', 'PB') ORDER BY u.sort_order""",
    )
    manager_of = manager_lookup(conn)
    for d in deputy_led:
        d["reports_to"] = manager_of(d["unit_id"])
    for v in vacancies:  # vị trí đầu đơn vị còn trống thì cấp trên trực tiếp đang quản lý thay
        v["reports_to"] = manager_of(v["unit_id"])
    span = rows(
        conn,
        """SELECT u.id AS unit_id, u.name AS unit_name, COUNT(c.id) AS direct_reports
           FROM units u JOIN units c ON c.parent_id = u.id
           GROUP BY u.id HAVING COUNT(c.id) > 0 ORDER BY direct_reports DESC""",
    )
    for x in span:
        x["head"] = head_label(conn, x["unit_id"])
        x["reports_to"] = manager_of(x["unit_id"])
    missing_process = rows(  # chưa có quy trình có cấu trúc VÀ chưa có tài liệu quy trình/quy định nào trong kho
        conn,
        """SELECT id AS unit_id, name AS unit_name FROM units
           WHERE unit_type IN ('department','committee')
             AND id NOT IN (SELECT unit_id FROM processes WHERE unit_id IS NOT NULL)
             AND id NOT IN (SELECT unit_id FROM documents WHERE unit_id IS NOT NULL AND doc_type IN """ + INTERNAL_DOC_TYPES + """)
             AND id NOT IN (SELECT du.unit_id FROM document_units du JOIN documents dd ON dd.id = du.doc_id
                            WHERE dd.doc_type IN """ + INTERNAL_DOC_TYPES + """)
           ORDER BY sort_order""",
    )
    for x in missing_process:
        x["reports_to"] = manager_of(x["unit_id"])
    missing_target = rows(
        conn,
        """SELECT id AS unit_id, name AS unit_name FROM units
           WHERE unit_type IN ('division','department') AND id NOT IN (SELECT unit_id FROM targets WHERE unit_id IS NOT NULL)
           ORDER BY sort_order""",
    )
    for x in missing_target:
        x["reports_to"] = manager_of(x["unit_id"])
    unverified = {
        "units": rows(conn, "SELECT id, name, full_name, notes FROM units WHERE verified = 0 ORDER BY sort_order"),
        "employees": rows(conn, "SELECT id, full_name FROM employees WHERE verified = 0 ORDER BY full_name"),
    }
    # Vòng đời: quy trình/tài liệu nội bộ quá REVIEW_DAYS ngày chưa rà soát (hoặc chưa ghi ngày hiệu lực)
    review_cut = f"date('now', 'localtime', '-{REVIEW_DAYS} day')"
    stale_processes = rows(
        conn,
        f"""SELECT p.id, p.code, p.name, p.effective_date, u.id AS unit_id, u.name AS unit_name FROM processes p
           JOIN units u ON u.id = p.unit_id
           WHERE p.status != 'retired' AND (p.effective_date IS NULL OR p.effective_date = ''
                 OR date(p.effective_date) IS NULL OR date(p.effective_date) < {review_cut})
           ORDER BY u.sort_order, p.code""",
    )
    stale_documents = rows(
        conn,
        f"""SELECT d.id, d.title, d.code, d.doc_type, d.uploaded_at, d.unit_id, u.name AS unit_name FROM documents d
           LEFT JOIN units u ON u.id = d.unit_id
           WHERE d.doc_type IN {INTERNAL_DOC_TYPES} AND date(d.uploaded_at) < {review_cut}
           ORDER BY d.uploaded_at""",
    )
    # Biên chế: định biên trên sơ đồ (tổng headcount) so với số người đang gán trên sơ đồ và số nhân sự thực tế theo HCNS
    staffing = rows(
        conn,
        """SELECT u.id AS unit_id, u.name AS unit_name, u.unit_type,
                  (SELECT COALESCE(SUM(headcount), 0) FROM positions WHERE unit_id = u.id) AS planned,
                  (SELECT COUNT(*) FROM positions WHERE unit_id = u.id AND employee_id IS NOT NULL) AS seated,
                  (SELECT COUNT(*) FROM employees WHERE unit_id = u.id AND status != 'inactive') AS hcns_active
           FROM units u WHERE u.unit_type IN ('division', 'department', 'committee') ORDER BY u.sort_order""",
    )
    for s in staffing:
        s["open_on_chart"] = max(0, s["planned"] - s["seated"])
        s["reports_to"] = manager_of(s["unit_id"])
        s["gap"] = s["hcns_active"] - s["planned"]  # âm = thiếu so với định biên, dương = dư
    draft_processes = rows(
        conn,
        "SELECT p.id, p.code, p.name, u.id AS unit_id, u.name AS unit_name FROM processes p JOIN units u ON u.id = p.unit_id"
        " WHERE p.status = 'draft' ORDER BY u.sort_order, p.code",
    )
    stats = row(
        conn,
        """SELECT (SELECT COUNT(*) FROM units WHERE unit_type = 'division') AS divisions,
                  (SELECT COUNT(*) FROM units WHERE unit_type IN ('department','committee')) AS departments,
                  (SELECT COUNT(*) FROM employees WHERE status = 'active') AS employees,
                  (SELECT COUNT(*) FROM positions) AS positions,
                  (SELECT COUNT(*) FROM positions WHERE employee_id IS NULL) AS vacancies,
                  (SELECT COUNT(*) FROM processes) AS processes,
                  (SELECT COUNT(*) FROM targets) AS targets""",
    )
    return {
        "stats": stats,
        "vacancies": vacancies,
        "concurrent_roles": concurrent,
        "deputy_led_departments": deputy_led,
        "leadership": leadership(conn),
        "span_of_control": span,
        "units_without_process": missing_process,
        "units_without_target": missing_target,
        "unverified": unverified,
        "stale_processes": stale_processes,
        "stale_documents": stale_documents,
        "draft_processes": draft_processes,
        "staffing": staffing,
    }


# Cách gọi thường ngày của từng đơn vị (mã đơn vị -> từ khoá phụ), để tìm "IT", "HCNS", "kế toán"... ra đúng đơn vị.
UNIT_ALIASES = {
    "P-IT": "it cntt công nghệ thông tin tin học helpdesk phần mềm hạ tầng",
    "P-HCNS": "hcns hành chính nhân sự nhân sự hr hành chính",
    "K-NSHC": "nhân sự hành chính hcns",
    "B-HT": "hệ thống iso qlht quản lý hệ thống",
    "P-MKT": "marketing mkt truyền thông thương hiệu",
    "P-PL": "pháp lý pháp chế luật",
    "B-TD": "đào tạo phát triển training t&d td",
    "P-KT": "kế toán kt",
    "B-TC": "tài chính",
    "B-QLCN": "công nợ qlcn",
    "P-TKKT": "thiết kế kỹ thuật tkkt",
    "P-DT": "đấu thầu tender bid dự thầu",
    "P-PTDA": "phát triển dự án ptda",
    "P-CCM": "ccm chi phí hợp đồng quản lý chi phí cost contract",
    "P-MEPF": "mepf cơ điện điện nước phccc",
    "P-BH": "bảo hành bảo trì",
    "P-MMTB": "mmtb máy móc thiết bị kho",
    "P-KTTC": "kttc kỹ thuật thi công",
    "P-LLTC": "lltc lực lượng thi công tổ đội",
    "P-QAQC": "qaqc qa qc chất lượng",
    "P-HSSE": "hsse hse an toàn sức khỏe môi trường an ninh",
    "P-VT": "vật tư mua hàng",
    "P-TP": "thầu phụ",
    "PMSM": "pm sm chỉ huy trưởng quản lý dự án",
    "TGD": "tổng giám đốc tgd ceo ban giám đốc",
    "TROLY": "trợ lý",
    "HDQT": "hội đồng quản trị hđqt",
    "KSNB": "kiểm soát nội bộ audit kiểm toán nội bộ",
    "BQLDA": "ban quản lý dự án bqlda công trình",
    "DV-HCNS": "dịch vụ tài xế bếp",
}
_PREFIX_STOP = {"phong", "ban", "khoi", "p", "b", "k", "ct", "bo", "phan", "cua", "la", "ai", "co", "bao",
                "nhieu", "dang", "nao", "o", "va", "nguoi", "may", "cho", "toi", "biet", "hay", "gi", "the", "truong",
                "pho", "thuoc", "phu", "trach", "dang", "hien", "bao", "nhieu", "con", "khong", "duoc", "do"}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower().replace("đ", "d").replace("Đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c))


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9&]+", _fold(s))


def _unit_score(u: dict, q_words: list[str], q_phrase: str, df: dict | None = None) -> int:
    """Điểm khớp giữa câu hỏi và một đơn vị (0 = không khớp). Khớp theo TỪ nguyên vẹn, bỏ dấu, bỏ tiền tố Phòng/Ban/P."""
    name_words = set(_words(f"{u['name']} {u.get('full_name') or ''} {u['code']}"))
    alias_words = set(_words(UNIT_ALIASES.get(u["code"], "")))
    name_phrase = " ".join(_words(f"{u['name']} {u.get('full_name') or ''}"))
    alias_phrase = " ".join(_words(UNIT_ALIASES.get(u["code"], "")))
    core = [w for w in q_words if w not in _PREFIX_STOP] or q_words
    if not core:
        return 0
    phrase = " ".join(core)
    if phrase and f" {phrase} " in f" {name_phrase} ":
        return 100
    if phrase and f" {phrase} " in f" {alias_phrase} ":
        return 90
    for n in range(min(len(core), 6), 1, -1):  # cụm từ liền nhau dài nhất trong câu hỏi có trong tên/viết tắt đơn vị
        for i in range(len(core) - n + 1):
            gram = " " + " ".join(core[i:i + n]) + " "
            if (gram in f" {name_phrase} " or gram in f" {alias_phrase} ")                     and sum(gram in ph for ph in (df or {}).get("__phrases__", [""])) <= 3:  # bỏ cụm quá chung như "quản lý"
                return 70 + n
    hit_words = [w for w in core if w in name_words or w in alias_words]
    if len(hit_words) == len(core):
        return 70 + len(hit_words)
    if any((df or {}).get(w, 99) == 1 for w in hit_words):  # từ chỉ riêng một đơn vị có (IT, MMTB, HSSE...)
        return 80
    # Khớp một phần (câu hỏi dài): từ càng hiếm (ít đơn vị chứa) càng có trọng số, từ phổ biến như "nhân sự" gần như vô nghĩa
    weight = sum(1 / (df or {}).get(w, 1) for w in hit_words)
    return int(min(60, 10 * weight)) if weight >= 0.5 else 0


def search(conn: sqlite3.Connection, q: str) -> dict:
    """Tìm đơn vị / nhân sự / quy trình. Đơn vị được xếp theo độ khớp; `units` rỗng nghĩa là KHÔNG có đơn vị nào khớp."""
    q = (q or "").strip()
    q_words = _words(q)
    all_units = rows(conn, "SELECT id, code, name, full_name, parent_id, functions, notes FROM units")
    df: dict[str, int] = {}
    for u in all_units:
        for w in set(_words(f"{u['name']} {u.get('full_name') or ''} {u['code']} {UNIT_ALIASES.get(u['code'], '')}")):
            df[w] = df.get(w, 0) + 1
    df["__phrases__"] = [" " + " ".join(_words(f"{u['name']} {u.get('full_name') or ''} {UNIT_ALIASES.get(u['code'], '')}")) + " "
                         for u in all_units]
    scored = sorted(((_unit_score(u, q_words, q, df), u) for u in all_units), key=lambda t: -t[0])
    if scored and scored[0][0] < 70:  # chỉ có khớp một phần: giữ nhóm điểm cao nhất thôi
        top = scored[0][0]
        scored = [t for t in scored if t[0] >= top]
    if any(sc >= 70 for sc, _ in scored):  # đã có khớp tốt thì bỏ các khớp một phần cho đỡ nhiễu
        scored = [(sc, u) for sc, u in scored if sc >= 70]
    units = [
        {"id": u["id"], "code": u["code"], "name": u["name"], "full_name": u["full_name"], "match_score": sc}
        for sc, u in scored if sc > 0
    ][:8]
    like = f"%{q}%"
    ql = q.lower()
    for u in all_units:  # khớp nội dung chức năng/ghi chú: điểm thấp, chỉ bổ sung nếu chưa có
        text = f"{u.get('functions') or ''} {u.get('notes') or ''}".lower()
        if len(ql) >= 3 and ql in text and all(x["id"] != u["id"] for x in units):
            units.append({"id": u["id"], "code": u["code"], "name": u["name"], "full_name": u["full_name"],
                          "match_score": 10})
    emp_rows = rows(conn, "SELECT e.id, e.employee_code, e.full_name, e.display_name, e.job_title, e.unit_id,"
                          " u.name AS unit_name FROM employees e LEFT JOIN units u ON u.id = e.unit_id")
    core = [w for w in q_words if w not in {"ai", "la", "cua", "phong", "ban", "anh", "chi"}]
    employees = []
    if core:
        for e in emp_rows:
            ew = set(_words(f"{e['full_name']} {e['display_name'] or ''} {e['employee_code'] or ''}"))
            if all(w in ew for w in core):
                employees.append({k: e[k] for k in ("id", "employee_code", "full_name", "job_title", "unit_id", "unit_name")})
    result = {
        "units": units,
        "employees": employees[:20],
        "processes": rows(conn, "SELECT id, unit_id, code, name FROM processes WHERE name LIKE ? OR code LIKE ?"
                                " OR content LIKE ? OR purpose LIKE ?", (like,) * 4),
    }
    if not units and not employees:
        result["hint"] = ("Không có đơn vị nào khớp từ khoá này. KHÔNG được đoán sang đơn vị có tên gần nghĩa: hãy thử từ khoá "
                          "khác (tên viết tắt, tên đầy đủ) hoặc gọi get_org_overview để xem đúng tên đơn vị, rồi hỏi lại TGĐ nếu vẫn chưa chắc.")
    elif len(units) > 1 and units[0]["match_score"] == units[1]["match_score"]:
        result["hint"] = ("Có nhiều đơn vị khớp ngang nhau (có thể là khối và phòng cùng tên, hoặc hai đơn vị khác nhau): chọn đơn vị đúng "
                          "với câu hỏi, gọi get_unit_detail để xác minh, và nêu rõ tên đơn vị đang trả lời.")
    return result


# ---------- Tiến độ mục tiêu doanh thu ----------
TARGET_WATCH_PCT = 70  # dưới mức này là "chậm" (đỏ); từ mức này đến 100% là "cần theo dõi" (vàng)
TARGET_STATUS_ORDER = {"behind": 0, "watch": 1, "ok": 2, "no_data": 3}


def period_elapsed(period: str | None, today: date | None = None) -> float | None:
    """Tỷ lệ thời gian đã trôi qua của kỳ (0..1): '2026' (năm), '2026-Q4' (quý), '2026-10' (tháng). Kỳ lạ -> None."""
    today = today or date.today()
    m = re.fullmatch(r"(\d{4})(?:-(?:Q([1-4])|(0[1-9]|1[0-2])))?", (period or "").strip())
    if not m:
        return None
    y, q, mo = int(m.group(1)), m.group(2), m.group(3)
    if q:
        a, b = (int(q) - 1) * 3 + 1, int(q) * 3 + 1
    elif mo:
        a, b = int(mo), int(mo) + 1
    else:
        a, b = 1, 13
    start = date(y, a, 1)
    end = date(y + 1, 1, 1) if b == 13 else date(y, b, 1)
    return max(0.0, min(1.0, ((today - start).days + 1) / (end - start).days))


FORECAST_MIN_ELAPSED = 0.1  # quá đầu kỳ thì ngoại suy không đáng tin


def target_progress(targets: list[dict], period: str | None = None, today: date | None = None) -> dict:
    """Tiến độ các mục tiêu của MỘT kỳ (mặc định kỳ mới nhất): % thực hiện, trạng thái, so với thời gian đã trôi qua,
    dự báo cuối kỳ (theo tốc độ hiện tại) và lịch sử các kỳ của cùng đơn vị + chỉ tiêu.
    `targets` là danh sách đã lọc theo quyền người xem (xem app.list_targets)."""
    periods = sorted({t["period"] for t in targets if t.get("period")}, reverse=True)
    chosen = period if period in periods else (periods[0] if periods else None)
    elapsed = period_elapsed(chosen, today)

    def pct_of(t):
        target, actual = t.get("target_value"), t.get("actual_value")
        return None if actual is None or not target else round(actual / target * 100, 1)

    items = []
    for t in targets:
        if t.get("period") != chosen:
            continue
        pct = pct_of(t)
        status = "no_data" if pct is None else "ok" if pct >= 100 else "watch" if pct >= TARGET_WATCH_PCT else "behind"
        forecast_pct = None
        if pct is not None and elapsed is not None and elapsed >= FORECAST_MIN_ELAPSED:
            forecast_pct = round(pct / elapsed, 1)
        history = sorted(
            ({"period": h["period"], "target_value": h.get("target_value"), "actual_value": h.get("actual_value"), "pct": pct_of(h)}
             for h in targets if h.get("unit_id") == t.get("unit_id") and h.get("metric") == t.get("metric")
             and h.get("metric_name") == t.get("metric_name")),
            key=lambda h: h["period"])
        items.append({**t, "pct": pct, "status": status, "forecast_pct": forecast_pct,
                      "forecast_value": round(t["target_value"] * forecast_pct / 100) if forecast_pct is not None else None,
                      "history": history})
    items.sort(key=lambda x: (TARGET_STATUS_ORDER[x["status"]], -(x["pct"] or 0), x.get("unit_name") or ""))
    summary = {k: sum(1 for x in items if x["status"] == k) for k in TARGET_STATUS_ORDER}
    summary["total"] = len(items)
    return {"periods": periods, "period": chosen, "elapsed_pct": None if elapsed is None else round(elapsed * 100, 1),
            "items": items, "summary": summary}
