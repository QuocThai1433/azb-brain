"""Thêm nhân sự có trong sheet "DS nhân sự theo SDTC mới" của file HCNS nhưng chưa có trong DB.

Sheet này chưa có mã nhân viên nên khớp theo họ tên (không phân biệt dấu). Người chưa có trong DB (kể cả
đã nghỉ) được thêm mới, trạng thái "Đang làm việc", chưa có mã NV. SĐT / ngày vào / ngày sinh / hợp đồng
lấy từ sheet "DS nhân sự hiện tại" nếu có người đó, không thì từ chính sheet SDTC mới.
Tên trùng nhau trong file thì bỏ qua và báo cáo.

Chạy (mặc định chỉ kiểm tra, không ghi):
  python -X utf8 -m backend.hr_add_missing "<file .xlsx>"
  python -X utf8 -m backend.hr_add_missing "<file .xlsx>" --apply
"""
import re
import shutil
import sys
from datetime import datetime

import openpyxl

from .contacts import _fold
from .db import DB_PATH, connect, rows
from .hr_contacts import normalize_date, normalize_phone

SHEET = "DS nhân sự theo SDTC mới"
FALLBACK_SHEET = "DS nhân sự hiện tại"
NOTE = "Chưa có mã NV — bổ sung từ danh sách HCNS (sheet 'DS nhân sự theo SDTC mới')"

# đầu mục trong sheet -> mã đơn vị trên sơ đồ (đầu mục không có ở đây: không gán đơn vị, giữ tên đầu mục)
SECTION_UNIT = {
    "BAN TỔNG GIÁM ĐỐC": "TGD", "BAN HỆ THỐNG": "B-HT", "BP. ISO": "TROLY", "PHÒNG HCNS": "P-HCNS",
    "BP. TUYỂN DỤNG": "P-HCNS", "BP. ĐÀO TẠO": "P-HCNS", "BP. PHÚC LỢI TIỀN LƯƠNG": "P-HCNS",
    "BP. HÀNH CHÍNH": "P-HCNS", "BP. IT": "P-IT", "BP. PHÁT TRIỂN DỰ ÁN": "P-PTDA", "BP. MARKETING": "P-MKT",
    "BP. PHÁP LÝ": "P-PL", "PHÒNG THIẾT KẾ ĐẤU THẦU": "P-TKKT", "BP. THIẾT KẾ": "P-TKKT", "BP. ĐẤU THẦU": "P-DT",
    "BP. BIỆN PHÁP THI CÔNG": "P-KTTC", "BP. BIM": "P-TKKT", "PHÒNG QA/QC": "P-QAQC", "BP. QA/QC": "P-QAQC",
    "BP. BẢO TRÌ": "P-BH", "PHÒNG HSSE": "P-HSSE", "BAN HSE": "P-HSSE", "BAN TƯ VẤN & ĐÀO TẠO HSE": "P-HSSE",
    "PHÒNG CCM": "P-CCM", "PHÒNG VẬT TƯ": "P-VT", "PHÒNG THẦU PHỤ": "P-TP", "PHÒNG THIẾT BỊ": "P-MMTB",
    "BP. THIẾT BỊ": "P-MMTB", "PHÒNG TÀI CHÍNH KẾ TOÁN": "P-KT", "BP. KẾ TOÁN": "P-KT", "BP. TÀI CHÍNH": "P-KT",
}
OFFICE_END = "KHỐI THI CÔNG"      # từ đầu mục này là Khối Thi công · Văn phòng khối
SITE_START = "KHỐI SCM"          # đầu mục này và các đầu mục sau (SCM, Tài chính) lại là Khối Văn phòng
PROJECTS_START = "YONGJIN"       # từ đây là các công trình


def _division(section: str, seen: dict) -> str:
    if section.startswith(OFFICE_END):
        seen["zone"] = "site_office"
    elif section.startswith(SITE_START):
        seen["zone"] = "office"
    elif section.startswith(PROJECTS_START):
        seen["zone"] = "projects"
    return {"office": "Khối Văn phòng", "site_office": "Khối Thi công · Văn phòng khối",
            "projects": "Khối Thi công · Các Ban QLDA"}[seen["zone"]]


def _contract(raw) -> str | None:
    exp = normalize_date(raw)
    if exp:
        return f"Hợp đồng có thời hạn, hết hạn {exp[8:]}/{exp[5:7]}/{exp[:4]} (theo file HCNS)"
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


def _read(wb, name: str) -> list[dict]:
    """Người trong sheet kèm đầu mục (section) đứng trước."""
    out, section = [], None
    for r in wb[name].iter_rows(values_only=True):
        if not r or len(r) < 9:
            continue
        if r[0] is None and r[1] is None and isinstance(r[2], str) and r[2].strip():
            section = re.sub(r"\s+", " ", r[2]).strip().upper()
        elif isinstance(r[0], int) and isinstance(r[2], str) and r[2].strip():
            out.append({"name": re.sub(r"\s+", " ", r[2]).strip(), "title": (r[3] or "").strip() or None,
                        "dept": (r[4] or "").strip() or None, "birth": r[5], "phone": r[6], "start": r[7],
                        "contract": r[8], "section": section})
    return out


def plan(path: str) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    people = _read(wb, SHEET)
    fallback = {}
    for p in _read(wb, FALLBACK_SHEET):
        fallback.setdefault(_fold(p["name"]), []).append(p)
    counts = {}
    for p in people:
        counts[_fold(p["name"])] = counts.get(_fold(p["name"]), 0) + 1
    with connect() as conn:
        existing = {_fold(e["full_name"]) for e in rows(conn, "SELECT full_name FROM employees")}
        units = {u["code"]: u["id"] for u in rows(conn, "SELECT id, code FROM units")}
        unit_names = {_fold(u["name"]): u["id"] for u in rows(conn, "SELECT id, name FROM units")}
        max_sort = conn.execute("SELECT COALESCE(MAX(sort_order), 0) FROM employees").fetchone()[0]
    res = {"add": [], "ambiguous": [], "total": len(people)}
    seen = {"zone": "office"}
    for p in people:
        division = _division(p["section"], seen)
        key = _fold(p["name"])
        if key in existing:
            continue
        if counts[key] > 1:
            res["ambiguous"].append(p["name"])
            continue
        src = fallback.get(key, [p])[0] if len(fallback.get(key, [])) == 1 else p
        if p["section"] in SECTION_UNIT:
            unit_id = units.get(SECTION_UNIT[p["section"]])
            dept = p["dept"] or p["section"].title()
        else:
            dept = f"CT. {p['dept']}" if division.endswith("QLDA") and p["dept"] else (p["dept"] or p["section"].title())
            unit_id = unit_names.get(_fold(dept))
        max_sort += 1
        res["add"].append({
            "full_name": p["name"], "job_title": p["title"], "unit_id": unit_id, "hr_department": dept,
            "hr_division": division, "phone": normalize_phone(src["phone"]) or normalize_phone(p["phone"]),
            "joined_date": normalize_date(src["start"]) or normalize_date(p["start"]),
            "birth_date": normalize_date(src["birth"]) or normalize_date(p["birth"]),
            "contract_term": _contract(src["contract"]) or _contract(p["contract"]),
            "grade": "Nhân viên", "status": "active", "verified": 1, "notes": NOTE, "sort_order": 10000 + max_sort,
        })
    return res


def apply(path: str, res: dict) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = DB_PATH.with_name(f"azb.backup-truoc-them-thieu-{stamp}.db")
    shutil.copy2(DB_PATH, backup)
    with connect() as conn:
        for e in res["add"]:
            conn.execute(f"INSERT INTO employees ({', '.join(e)}) VALUES ({', '.join('?' * len(e))})", tuple(e.values()))
        conn.execute("INSERT INTO audit_log (action, entity, detail) VALUES ('import','employees',?)",
                     (f"Thêm {len(res['add'])} nhân sự còn thiếu từ danh sách HCNS ({path.split(chr(92))[-1]})",))
    return str(backup)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--apply"]
    if len(args) != 1:
        sys.exit(__doc__)
    result = plan(args[0])
    add = result["add"]
    print(f"Sheet '{SHEET}': {result['total']} người. Sẽ thêm mới: {len(add)} "
          f"(có SĐT {sum(1 for e in add if e['phone'])}, ngày vào {sum(1 for e in add if e['joined_date'])}, "
          f"ngày sinh {sum(1 for e in add if e['birth_date'])}, gán đơn vị {sum(1 for e in add if e['unit_id'])}).")
    print("Trùng tên trong file (bỏ qua):", "; ".join(result["ambiguous"]) or "không")
    if "--apply" in sys.argv:
        print("Sao lưu:", apply(args[0], result))
        print(f"Đã thêm {len(add)} nhân sự.")
    else:
        for e in add[:8]:
            print("  ", e["full_name"], "|", e["job_title"], "|", e["hr_department"], "|", e["phone"], "|", e["joined_date"])
        print("Chưa ghi gì. Chạy lại với --apply để ghi.")
