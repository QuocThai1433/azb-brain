"""Nhập danh sách nhân sự hiện hữu do HCNS cập nhật hằng tuần (file Excel).

Chạy: .venv\\Scripts\\python -X utf8 -m backend.hr_import "<đường dẫn file .xlsx>"

Cấu trúc sheet đầu tiên ("NS theo khối"):
  - dòng Khối:       cột A = A/B./C., cột B = tên khối (hoặc cột A trống, cột B = nhóm con của khối thi công)
  - dòng Phòng ban:  cột A = số La Mã, cột D = tên phòng ban / công trình
  - dòng Nhân sự:    C = MNV, D = Họ tên, E = Ngạch, F = Nhóm lao động, G = Chức danh, H = Phòng ban/Bộ phận/Dự án

Nhập lại nhiều lần được: khớp theo mã nhân viên; nhân sự sơ đồ chưa có mã thì khớp theo họ tên
(kể cả tên viết tắt trên sơ đồ như "Ng. V. Trung"). Ai có mã nhưng không còn trong file -> chuyển "Đã nghỉ".
"""
import re
import sys
import unicodedata

import openpyxl

from .db import connect, init_db, rows

# Tên phòng ban trong file HCNS (viết hoa) -> (mã đơn vị trên sơ đồ, tên hiển thị)
DEPARTMENTS = {
    "BAN TỔNG GIÁM ĐỐC": ("TGD", "Ban Tổng Giám đốc"),
    "BAN TRỢ LÝ": ("TROLY", "Ban Trợ lý"),
    "BAN T&D": ("B-TD", "Ban T&D"),
    "PHÒNG IT": ("P-IT", "Phòng IT"),
    "PHÒNG MARKETING": ("P-MKT", "Phòng Marketing"),
    "PHÒNG PHÁP LÝ": ("P-PL", "Phòng Pháp lý"),
    "PHÒNG HCNS": ("P-HCNS", "Phòng Hành chính Nhân sự"),
    "PHÒNG KẾ TOÁN": ("P-KT", "Phòng Kế toán"),
    "BAN QLCN": ("B-QLCN", "Ban Quản lý Công nợ"),
    "PHÒNG THIẾT KẾ - KỸ THUẬT": ("P-TKKT", "Phòng Thiết kế - Kỹ thuật"),
    "PHÒNG ĐẤU THẦU": ("P-DT", "Phòng Đấu thầu"),
    "PHÒNG PHÁT TRIỂN DỰ ÁN": ("P-PTDA", "Phòng Phát triển Dự án"),
    "PHÒNG VẬT TƯ": ("P-VT", "Phòng Vật tư"),
    "PHÒNG THẦU PHỤ": ("P-TP", "Phòng Thầu phụ"),
    "PHÒNG CCM": ("P-CCM", "Phòng CCM"),
    "PHÒNG HSSE": ("P-HSSE", "Phòng HSSE"),
    "KHỐI DỊCH VỤ - PHÒNG HCNS": ("DV-HCNS", "Bộ phận Dịch vụ (Tài xế, Bếp)"),
    "VĂN PHÒNG, KTC PMD": ("K-TC", "Văn phòng Khối Thi công (PMD)"),
    "BỘ PHẬN MEPF": ("P-MEPF", "Phòng MEPF"),
    "PHÒNG QA/QC": ("P-QAQC", "Phòng QA/QC"),
    "PHÒNG LLTC": ("P-LLTC", "Phòng LLTC"),
    "PHÒNG BẢO HÀNH": ("P-BH", "Phòng Bảo hành"),
    "PHÒNG MMTB": ("P-MMTB", "Phòng MMTB"),
    "PHÒNG KỸ THUẬT THI CÔNG": ("P-KTTC", "Phòng Kỹ thuật Thi công"),
}

# Đơn vị chưa có trên sơ đồ, tạo thêm khi nhập: (code, name, unit_type, parent_code, color_group)
EXTRA_UNITS = {
    "DV-HCNS": ("Bộ phận Dịch vụ", "department", "P-HCNS", "hr"),
}

DIVISIONS = {
    "KHỐI VĂN PHÒNG": "Khối Văn phòng",
    "KHỐI DỊCH VỤ": "Khối Dịch vụ",
    "VĂN PHÒNG KHỐI THI CÔNG": "Khối Thi công · Văn phòng khối",
    "CÁC BAN QUẢN LÝ DỰ ÁN": "Khối Thi công · Các Ban QLDA",
}

# Từ giữ nguyên chữ hoa khi đổi tên công trình sang dạng thường
ACRONYMS = {"GĐ", "AZB", "AHA", "VSIP", "APSC", "II", "III", "QLDA"}


def _ascii(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def _project_name(section: str) -> str:
    name = re.sub(r"^CÔNG TRÌNH\s+", "", section.strip())
    words = [w if w in ACRONYMS or any(ch.isdigit() for ch in w) else w.capitalize() for w in name.split()]
    return "CT. " + " ".join(words)


def _project_code(section: str) -> str:
    name = re.sub(r"^cong trinh\s+", "", _ascii(section.strip()))
    return "CT-" + re.sub(r"[^a-z0-9]+", "-", name).strip("-").upper()


def read_workbook(path: str) -> list[dict]:
    ws = openpyxl.load_workbook(path, data_only=True, read_only=True).worksheets[0]
    division = section = None
    people = []
    for i, r in enumerate(ws.iter_rows(min_row=1, max_col=8, values_only=True)):
        r = [(c.strip() if isinstance(c, str) else c) for c in r] + [None] * (8 - len(r))
        code = str(r[2] or "").strip().upper()
        if re.fullmatch(r"NV\d+", code) and r[3]:
            people.append({
                "employee_code": code, "full_name": re.sub(r"\s+", " ", r[3]), "grade": r[4], "labor_group": r[5],
                "job_title": r[6], "detail": r[7], "division": division, "section": section, "row": i,
            })
        elif isinstance(r[3], str) and r[0] and not r[2]:
            section = r[3].upper()
        elif isinstance(r[1], str) and r[1].upper() in DIVISIONS:
            division = r[1].upper()
            section = None
        elif isinstance(r[0], str) and "do not delete" in r[0].lower():
            break  # phần bảng định biên phía dưới, không phải danh sách nhân sự
    return people


def _name_match(chart_name: str, full_name: str) -> bool:
    """So tên trên sơ đồ (có thể viết tắt "Ng. V. Trung") với họ tên đầy đủ, không phân biệt dấu."""
    a, b = _ascii(chart_name).replace(".", ". ").split(), _ascii(full_name).split()
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x.endswith("."):
            if not y.startswith(x[:-1]):
                return False
        elif x != y:
            return False
    return True


def import_hr(path: str) -> dict:
    init_db()
    people = read_workbook(path)
    if not people:
        raise ValueError("Không tìm thấy dòng nhân sự nào (cột C phải là mã NVxxxxx).")
    with connect() as conn:
        units = {u["code"]: u["id"] for u in rows(conn, "SELECT id, code FROM units")}
        max_sort = conn.execute("SELECT COALESCE(MAX(sort_order), 0) FROM units").fetchone()[0]

        def ensure_unit(code, name, utype, parent_code, color, full_name=None):
            nonlocal max_sort
            if code not in units:
                max_sort += 1
                cur = conn.execute(
                    "INSERT INTO units (code, name, full_name, unit_type, parent_id, color_group, sort_order)"
                    " VALUES (?,?,?,?,?,?,?)", (code, name, full_name, utype, units.get(parent_code), color, max_sort))
                units[code] = cur.lastrowid
                created_units.append(name)
            return units[code]

        created_units: list[str] = []
        existing = rows(conn, "SELECT id, employee_code, full_name, display_name FROM employees")
        by_code = {e["employee_code"]: e for e in existing if e["employee_code"]}
        no_code = [e for e in existing if not e["employee_code"]]
        stats = {"total": len(people), "created": 0, "updated": 0, "matched_chart": []}
        seen = set()
        # Nhân sự trên sơ đồ chưa có mã: chỉ khớp khi đúng một người trong file trùng tên
        chart_match = {}
        for e in no_code:
            hits = [p["employee_code"] for p in people if p["employee_code"] not in by_code and (
                _name_match(e["display_name"] or e["full_name"], p["full_name"]) or _name_match(e["full_name"], p["full_name"]))]
            if len(hits) == 1:
                chart_match[hits[0]] = e

        for p in people:
            if p["section"] in DEPARTMENTS:
                ucode, dept = DEPARTMENTS[p["section"]]
                if ucode in EXTRA_UNITS:
                    name, utype, parent, color = EXTRA_UNITS[ucode]
                    ensure_unit(ucode, name, utype, parent, color)
            elif p["division"] == "CÁC BAN QUẢN LÝ DỰ ÁN" and p["section"]:
                dept = _project_name(p["section"])
                ucode = _project_code(p["section"])
                ensure_unit(ucode, dept, "project", "BQLDA", "construction", p["detail"])
            else:
                ucode, dept = None, (p["section"] or "Khác").capitalize()

            data = {
                "employee_code": p["employee_code"], "full_name": p["full_name"], "job_title": p["job_title"],
                "grade": p["grade"], "labor_group": p["labor_group"], "unit_id": units.get(ucode),
                "hr_department": dept, "hr_division": DIVISIONS.get(p["division"], p["division"]),
                "sort_order": p["row"], "status": "active", "verified": 1,
            }
            seen.add(p["employee_code"])
            emp = by_code.get(p["employee_code"])
            if not emp and p["employee_code"] in chart_match:  # có trên sơ đồ nhưng chưa có mã
                emp = chart_match[p["employee_code"]]
                no_code.remove(emp)
                stats["matched_chart"].append(f'{emp["full_name"]} -> {p["full_name"]}')
            if emp:
                sets = ", ".join(f"{k} = ?" for k in data)
                conn.execute(f"UPDATE employees SET {sets}, notes = CASE WHEN notes LIKE 'Tên đang viết tắt%' THEN NULL"
                             " ELSE notes END WHERE id = ?", (*data.values(), emp["id"]))
                stats["updated"] += 1
            else:
                conn.execute(f"INSERT INTO employees ({', '.join(data)}) VALUES ({', '.join('?' * len(data))})",
                             tuple(data.values()))
                stats["created"] += 1

        left = [c for c in by_code if c not in seen]
        conn.executemany("UPDATE employees SET status = 'inactive' WHERE employee_code = ?", [(c,) for c in left])
        stats["inactive"] = len(left)
        stats["unmatched_chart"] = [e["full_name"] for e in no_code]
        stats["created_units"] = created_units
        conn.execute("INSERT INTO audit_log (action, entity, detail) VALUES ('import','employees',?)",
                     (f"Nhập {len(people)} nhân sự từ danh sách HCNS",))
    return stats


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    s = import_hr(sys.argv[1])
    print(f"Đọc {s['total']} nhân sự: thêm mới {s['created']}, cập nhật {s['updated']}, chuyển 'Đã nghỉ' {s['inactive']}.")
    if s["created_units"]:
        print("Tạo thêm đơn vị:", ", ".join(s["created_units"]))
    for m in s["matched_chart"]:
        print("  Khớp tên sơ đồ:", m)
    if s["unmatched_chart"]:
        print("Nhân sự trên sơ đồ không tìm thấy trong file:", ", ".join(s["unmatched_chart"]))
