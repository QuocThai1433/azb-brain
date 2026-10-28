"""Tổng quan điều hành cho Ban TGĐ: gom ngân sách, mục tiêu, đề xuất và nhân sự thành một bản tin.

Tính hoàn toàn bằng quy tắc trên dữ liệu có sẵn, không gọi AI và không đưa dữ liệu cá nhân ra ngoài.
Chỉ trả về số đếm và tên đơn vị / hạng mục, không có ngày sinh, SĐT, email hay mã nhân viên.
"""
import sqlite3
from datetime import date

from . import analytics, opbudget, proposals
from .db import rows

LEVEL_ORDER = {"red": 0, "amb": 1, "gry": 2}
METRIC = {"doanh_so": "Doanh số", "doanh_thu": "Doanh thu", "loi_nhuan": "Lợi nhuận", "dong_tien": "Dòng tiền", "okr_du_an": "OKR dự án"}


def _budget(conn) -> dict:
    d = opbudget.dashboard(conn)
    if not d.get("has_plan"):
        return {"has_plan": False}
    t = d["totals"]
    return {"has_plan": True, "year": d["year"], "as_of": d["as_of"], "percent": t["percent"],
            "expected_pct": round(t["expected"] / t["plan"] * 100, 1) if t["plan"] > 0 else 0.0,
            "status": t["status"], "over": t["over"], "near": t["near"], "pace": t["pace"], "blocked": t["blocked"],
            "sections": [{"name": s["name"], "percent": s["percent"], "status": s["status"]} for s in d["sections"]],
            "alerts": [{"name": a["name"], "status": a["status"], "percent": a["percent"], "blocked": a["blocked"]} for a in d["alerts"][:3]]}


def _okr(conn, today: date) -> dict:
    items = rows(conn, "SELECT t.*, u.name AS unit_name FROM targets t LEFT JOIN units u ON u.id = t.unit_id")
    prog = analytics.target_progress(items, None, today)
    with_data = [i["pct"] for i in prog["items"] if i["pct"] is not None]
    s = prog["summary"]
    return {"period": prog["period"], "total": s["total"], "with_data": len(with_data), "behind": s["behind"], "watch": s["watch"],
            "avg_pct": round(sum(with_data) / len(with_data), 1) if with_data else None, "elapsed_pct": prog["elapsed_pct"],
            "behind_names": [i.get("metric_name") or METRIC.get(i["metric"], i["metric"]) for i in prog["items"] if i["status"] == "behind"][:3]}


def _proposals(conn, today: date) -> dict:
    iso = today.isoformat()
    one = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]
    oldest = rows(conn, f"SELECT p.title, date({proposals.REVIEW_SINCE}) AS since FROM proposals p WHERE p.status = 'review' "
                        "ORDER BY since LIMIT 1")
    return {"new": one("SELECT COUNT(*) FROM proposals WHERE status = 'new'"),
            "review": one("SELECT COUNT(*) FROM proposals WHERE status = 'review'"),
            "stale_review": proposals.stale_review_count(conn),
            "overdue": one("SELECT COUNT(*) FROM proposals WHERE due_date IS NOT NULL AND due_date < ? AND status IN ('new','in_progress','review')", (iso,)),
            "in_progress": one("SELECT COUNT(*) FROM proposals WHERE status = 'in_progress'"),
            "oldest_review": oldest[0]["title"] if oldest else None,
            "queue": _queue(conn, today)}


def _queue(conn, today: date) -> list[dict]:
    """Đề xuất đang chờ Ban TGĐ xử lý ngay (chờ nghiệm thu trước, rồi chờ duyệt), mỗi loại cũ nhất trước."""
    items = rows(conn, f"SELECT p.id, p.title, p.status, p.owner_user_id, p.due_date, p.priority, {proposals.REVIEW_SINCE} AS review_since,"
                       " o.full_name AS owner_name FROM proposals p LEFT JOIN users o ON o.id = p.owner_user_id"
                       " WHERE p.status IN ('new', 'review') ORDER BY p.status = 'new', p.id LIMIT 5")
    for p in items:
        since = p.pop("review_since")
        p["review_days"] = (today - date.fromisoformat(since[:10])).days if p["status"] == "review" and since else None
    return items


def _hr(conn, today: date) -> dict:
    ins = analytics.insights(conn)
    month = today.strftime("%Y-%m")
    joined = conn.execute("SELECT COUNT(*) FROM employees WHERE status = 'active' AND substr(joined_date, 1, 7) = ?", (month,)).fetchone()[0]
    return {"vacancies": len(ins["vacancies"]), "vacancy_units": sorted({v["unit_name"] for v in ins["vacancies"]})[:3],
            "concurrent": len(ins["concurrent_roles"]), "deputy_led": len(ins["deputy_led_departments"]),
            "unverified": len(ins["unverified"]["units"]) + len(ins["unverified"]["employees"]), "joined_month": joined}


def _attention(b: dict, o: dict, p: dict, h: dict) -> list[dict]:
    out = []

    def add(level, title, desc, tag, view, focus=""):
        out.append({"level": level, "title": title, "desc": desc, "tag": tag, "view": view, "focus": focus})

    if p["stale_review"]:
        add("red", f"{p['stale_review']} đề xuất chờ nghiệm thu quá {proposals.STALE_REVIEW_DAYS} ngày",
            f"Cũ nhất: {p['oldest_review']}" if p["oldest_review"] else "Cần Ban TGĐ nghiệm thu", f"{p['stale_review']} đề xuất", "proposals")
    if p["overdue"]:
        add("red", f"{p['overdue']} đề xuất / việc được giao đã quá hạn", "Đã qua hạn hoàn thành mà chưa xong", f"{p['overdue']} việc", "proposals")
    if b.get("has_plan") and (b["over"] or b["blocked"]):
        add("red", f"{b['over']} hạng mục ngân sách đã vượt kế hoạch" if b["over"] else f"{b['blocked']} hạng mục ngân sách đang bị chặn",
            ", ".join(a["name"] for a in b["alerts"]) or "Xem chi tiết ở mục Ngân sách", "Vượt ngân sách" if b["over"] else "Đang chặn", "budget")
    elif b.get("has_plan") and (b["near"] or b["pace"]):
        add("amb", f"{b['near'] + b['pace']} hạng mục ngân sách sắp vượt hoặc chi nhanh hơn tiến độ",
            ", ".join(a["name"] for a in b["alerts"]), "Cảnh báo", "budget")
    if p["new"]:
        add("amb", f"{p['new']} đề xuất mới chờ duyệt", "Chưa giao người phụ trách", f"{p['new']} đề xuất", "proposals")
    if o["behind"]:
        add("amb", f"{o['behind']} mục tiêu đang chậm tiến độ", ", ".join(o["behind_names"]), f"{o['behind']} mục tiêu", "targets")
    if h["vacancies"]:
        add("amb", f"{h['vacancies']} vị trí đang trống", ", ".join(h["vacancy_units"]), f"{h['vacancies']} vị trí", "insights", "vacancies")
    if h["deputy_led"]:
        add("amb", f"{h['deputy_led']} phòng do cấp phó phụ trách", "Chưa có Trưởng phòng", f"{h['deputy_led']} phòng", "insights", "deputy")
    if h["concurrent"]:
        add("gry", f"{h['concurrent']} người kiêm nhiệm nhiều đơn vị", "Giữ chức danh ở từ 2 đơn vị trở lên", "Theo dõi", "insights", "concurrent")
    out.sort(key=lambda a: LEVEL_ORDER[a["level"]])
    return out


def _brief(b: dict, o: dict, p: dict, h: dict) -> list[dict]:
    out = []
    if b.get("has_plan"):
        gap = round(b["percent"] - b["expected_pct"], 1)
        lvl = "red" if b["over"] or b["status"] in ("over", "near") else "amb" if gap > 5 else "grn"
        out.append({"level": lvl, "view": "budget", "sub": f"Ngân sách {b['year']} · đến tháng {b['as_of']}",
                    "text": f"Đã chi {b['percent']:g}% ngân sách năm khi tiến độ thời gian là {b['expected_pct']:g}%"
                            + (f" (nhanh hơn {gap:g} điểm %)." if gap > 0 else ".")})
    if p["new"] or p["review"]:
        out.append({"level": "red" if p["stale_review"] else "amb", "view": "proposals", "sub": "Đề xuất",
                    "text": f"{p['new']} đề xuất chờ duyệt, {p['review']} chờ nghiệm thu"
                            + (f" ({p['stale_review']} quá {proposals.STALE_REVIEW_DAYS} ngày)." if p["stale_review"] else ".")})
    if o["total"]:
        if o["avg_pct"] is None:
            out.append({"level": "amb", "view": "targets", "sub": f"Mục tiêu {o['period']}",
                        "text": f"{o['total']} mục tiêu năm {o['period']} nhưng chưa có số thực hiện nào được nhập."})
        else:
            out.append({"level": "amb" if o["behind"] else "grn", "view": "targets", "sub": f"Mục tiêu {o['period']}",
                        "text": f"Trung bình đạt {o['avg_pct']:g}% chỉ tiêu ({o['with_data']}/{o['total']} mục có số đo)"
                                + (f", {o['behind']} mục chậm tiến độ." if o["behind"] else ".")})
    out.append({"level": "amb" if h["vacancies"] else "grn", "view": "insights", "sub": "Nhân sự",
                "text": f"Tháng này có {h['joined_month']} người vào làm; {h['vacancies']} vị trí đang trống."})
    return out


def executive(conn: sqlite3.Connection, today: date | None = None) -> dict:
    today = today or date.today()
    b, o, p, h = _budget(conn), _okr(conn, today), _proposals(conn, today), _hr(conn, today)
    return {"as_of": today.isoformat(), "budget": b, "okr": o, "proposals": p, "hr": h,
            "attention": _attention(b, o, p, h), "brief": _brief(b, o, p, h)}
