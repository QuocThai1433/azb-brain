"""Bổ sung SĐT, ngày vào công ty, ngày sinh và loại hợp đồng cho nhân sự từ danh sách HCNS (sheet "DS nhân sự hiện tại").

File HCNS chưa có cột mã nhân viên ở các sheet này, nên khớp theo họ tên (không phân biệt dấu):
- Chỉ ghi khi tên trong file khớp đúng MỘT nhân viên đang hoạt động trong DB.
- Trùng tên (trong file hoặc trong DB), không khớp, hoặc các sheet cho số/ngày khác nhau: báo cáo, KHÔNG ghi.
- SĐT chuẩn hoá về dạng 0xxxxxxxxx (nhiều số nối bằng " / "). Ngày chuẩn hoá về YYYY-MM-DD;
  ô chỉ có năm (không đủ ngày) bị bỏ qua và báo cáo.
- Không đụng tới email: nguồn không có email.

Chạy (mặc định chỉ kiểm tra, không ghi):
  python -X utf8 -m backend.hr_contacts "<file .xlsx>"
  python -X utf8 -m backend.hr_contacts "<file .xlsx>" --apply
"""
import re
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import openpyxl

from .contacts import _fold
from .db import DB_PATH, connect, rows

PRIMARY_SHEET = "DS nhân sự hiện tại"
# các sheet cùng cấu trúc, chỉ dùng để đối chiếu
CROSS_SHEETS = ["DS nhân sự theo SDTC mới", "file Chị Hân"]
NAME_COL, BIRTH_COL, PHONE_COL, START_COL, CONTRACT_COL = 2, 5, 6, 7, 8  # C họ tên, F ngày sinh, G số liên lạc, H bắt đầu nhận việc, I hợp đồng (chỉ số 0)


def _one_phone(piece: str) -> str | None:
    digits = re.sub(r"\D", "", piece)
    if digits.startswith("84") and len(digits) in (11, 12):
        digits = "0" + digits[2:]
    if len(digits) == 9 and digits[0] in "35789":  # số di động thiếu số 0 đầu
        digits = "0" + digits
    return digits if re.fullmatch(r"0\d{9}", digits) else None


def normalize_phone(raw) -> str | None:
    """'0989.247.653' -> '0989247653'. Ô có nhiều số ('0909.998.203/ 0898.639.489') giữ đủ, nối bằng ' / '."""
    if raw is None:
        return None
    found = [p for p in (_one_phone(x) for x in re.split(r"[/,;\n]+", str(raw))) if p]
    unique = list(dict.fromkeys(found))
    return " / ".join(unique) if unique else None


def normalize_date(raw) -> str | None:
    """'30/03/2011', datetime(2011, 3, 30) -> '2011-03-30'. Chỉ có năm, hoặc không đọc được -> None."""
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    m = re.fullmatch(r"\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*", str(raw or ""))
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def read_sheet(wb, name: str) -> dict[str, list[dict]]:
    """Trả về {tên đã chuẩn hoá: [{name, phone_raw, start_raw, row}]} cho các dòng có STT là số (người thật)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for i, r in enumerate(wb[name].iter_rows(values_only=True), start=1):
        if not r or len(r) <= START_COL:
            continue
        stt, person = r[0], r[NAME_COL]
        if not (isinstance(stt, int) or (isinstance(stt, str) and stt.strip().isdigit())):
            continue
        if not isinstance(person, str) or not person.strip():
            continue
        clean = re.sub(r"\s+", " ", person).strip()
        out[_fold(clean)].append({"name": clean, "phone_raw": r[PHONE_COL], "start_raw": r[START_COL], "birth_raw": r[BIRTH_COL],
                                  "contract_raw": r[CONTRACT_COL] if len(r) > CONTRACT_COL else None, "row": i})
    return out


def plan(path: str) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    primary = read_sheet(wb, PRIMARY_SHEET)
    cross = {s: read_sheet(wb, s) for s in CROSS_SHEETS}

    with connect() as conn:
        emps = rows(conn, "SELECT id, full_name, phone, joined_date, birth_date, contract_term FROM employees WHERE status = 'active'")
    by_name: dict[str, list[dict]] = defaultdict(list)
    for e in emps:
        by_name[_fold(e["full_name"])].append(e)

    res = {"sheet_people": sum(len(v) for v in primary.values()), "updates": [], "unchanged": 0,
           "ambiguous_file": [], "ambiguous_db": [], "not_in_db": [], "invalid_phone": [], "conflict": [],
           "bad_date": [], "date_conflict": [], "no_phone_in_file": 0, "db_total": len(emps)}
    # Người chỉ có ở sheet đối chiếu (không có ở sheet chính) vẫn được lấy từ sheet đối chiếu đầu tiên có tên đó
    keys = list(primary) + [k for s in cross.values() for k in s if k not in primary]
    for key in dict.fromkeys(keys):
        from_primary = key in primary
        entries = primary[key] if from_primary else next(s[key] for s in cross.values() if key in s)
        if len(entries) > 1:
            res["ambiguous_file"].append(entries[0]["name"])
            continue
        e = entries[0]
        phone = normalize_phone(e["phone_raw"])
        start = normalize_date(e["start_raw"])
        birth = normalize_date(e["birth_raw"])
        # chỉ sheet chính ghi hợp đồng: chữ ("Hợp đồng không XĐTH") giữ nguyên; ngày = ngày hết hạn HĐLĐ có thời hạn
        contract = None
        if from_primary:
            exp = normalize_date(e["contract_raw"])
            if exp:
                contract = f"Hợp đồng có thời hạn, hết hạn {exp[8:]}/{exp[5:7]}/{exp[:4]} (theo file HCNS)"
            elif isinstance(e["contract_raw"], str) and e["contract_raw"].strip():
                contract = e["contract_raw"].strip()
        if phone is None and e["phone_raw"]:
            res["invalid_phone"].append((e["name"], str(e["phone_raw"])))
        if phone is None and start is None and birth is None and contract is None:
            res["no_phone_in_file"] += 1
            continue
        # đối chiếu số, ngày vào và ngày sinh với các sheet còn lại
        pool = [primary] if not from_primary else []
        other_rows = [x[0] for s in [*pool, *cross.values()] for x in [s.get(key, [])] if x and x[0] is not e]
        other_phones = {normalize_phone(x["phone_raw"]) for x in other_rows} - {None}
        other_starts = {normalize_date(x["start_raw"]) for x in other_rows} - {None}
        other_births = {normalize_date(x["birth_raw"]) for x in other_rows} - {None}
        if phone and other_phones - {phone}:
            res["conflict"].append((e["name"], phone, sorted(other_phones)))
            phone = None
        if start and other_starts - {start}:
            res["date_conflict"].append((e["name"], start, sorted(other_starts)))
            start = None
        if birth and other_births - {birth}:
            res["date_conflict"].append((e["name"] + " (ngày sinh)", birth, sorted(other_births)))
            birth = None
        if start is None and e["start_raw"] and normalize_date(e["start_raw"]) is None:
            res["bad_date"].append((e["name"], str(e["start_raw"])))
        if phone is None and start is None and birth is None and contract is None:
            continue
        matches = by_name.get(key, [])
        if not matches:
            res["not_in_db"].append(e["name"])
            continue
        if len(matches) > 1:
            res["ambiguous_db"].append(e["name"])
            continue
        db = matches[0]
        change = {}
        if phone and db["phone"] != phone:
            change["phone"] = phone
        if start and db["joined_date"] != start:
            change["joined_date"] = start
        if birth and db["birth_date"] != birth:
            change["birth_date"] = birth
        if contract and db["contract_term"] != contract:
            change["contract_term"] = contract
        if change:
            res["updates"].append({"employee_id": db["id"], "name": db["full_name"], **change})
        else:
            res["unchanged"] += 1
    return res


def apply(path: str, res: dict) -> str:
    """Sao lưu DB rồi ghi SĐT và ngày vào công ty. Trả về đường dẫn file sao lưu."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = DB_PATH.with_name(f"azb.backup-truoc-SDT-{stamp}.db")
    shutil.copy2(DB_PATH, backup)
    with connect() as conn:
        for u in res["updates"]:
            sets = {k: u[k] for k in ("phone", "joined_date", "birth_date", "contract_term") if k in u}
            clause = ", ".join(f"{k} = ?" for k in sets)
            conn.execute(f"UPDATE employees SET {clause} WHERE id = ?", (*sets.values(), u["employee_id"]))
        conn.execute("INSERT INTO audit_log (action, entity, detail) VALUES ('import','employees',?)",
                     (f"Bổ sung SĐT/ngày vào/ngày sinh/hợp đồng cho {len(res['updates'])} nhân sự từ danh sách HCNS ({Path(path).name})",))
    return str(backup)


def _print(res: dict) -> None:
    n_phone = sum(1 for u in res["updates"] if "phone" in u)
    n_date = sum(1 for u in res["updates"] if "joined_date" in u)
    print(f"Sheet '{PRIMARY_SHEET}': {res['sheet_people']} người.")
    print(f"  Sẽ ghi (người): {len(res['updates'])} | SĐT: {n_phone} | ngày vào công ty: {n_date}")
    print(f"  Ngày sinh: {sum(1 for u in res['updates'] if 'birth_date' in u)} | loại hợp đồng: {sum(1 for u in res['updates'] if 'contract_term' in u)}")
    print(f"  Đã đúng sẵn: {res['unchanged']}")
    print(f"  Trùng tên trong file (bỏ qua): {len(res['ambiguous_file'])}")
    print(f"  Trùng tên trong DB (bỏ qua): {len(res['ambiguous_db'])}")
    print(f"  Không có trong DB (bỏ qua): {len(res['not_in_db'])}")
    print(f"  Không có SĐT và ngày trong file: {res['no_phone_in_file']}")
    print(f"  Số lỗi (bỏ qua): {len(res['invalid_phone'])} | Ngày không đủ (bỏ qua): {len(res['bad_date'])}")
    print(f"  Lệch giữa các sheet (bỏ qua): số {len(res['conflict'])}, ngày {len(res['date_conflict'])}")
    for label, key in [("Trùng tên trong DB", "ambiguous_db"), ("Không có trong DB", "not_in_db"),
                       ("Trùng tên trong file", "ambiguous_file")]:
        if res[key]:
            print(f"  [{label}]", "; ".join(res[key][:40]))
    if res["bad_date"]:
        print("  [Ngày không đủ]", "; ".join(f"{n}: {d}" for n, d in res["bad_date"]))
    if res["invalid_phone"]:
        print("  [Số lỗi]", "; ".join(f"{n}: {p}" for n, p in res["invalid_phone"][:40]))
    if res["conflict"] or res["date_conflict"]:
        print("  [Lệch giữa các sheet]", "; ".join(f"{n}: {p} / {o}" for n, p, o in res["conflict"]),
              "; ".join(f"{n}: {p} / {o}" for n, p, o in res["date_conflict"]))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--apply"]
    if len(args) != 1:
        sys.exit(__doc__)
    result = plan(args[0])
    _print(result)
    if "--apply" in sys.argv:
        print("Sao lưu:", apply(args[0], result))
        print(f"Đã ghi {len(result['updates'])} nhân sự.")
    else:
        print("Chưa ghi gì. Chạy lại với --apply để ghi.")
