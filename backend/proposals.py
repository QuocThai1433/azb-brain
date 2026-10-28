"""Đề xuất cải tiến: giao việc, tiến trình có quy tắc, file đính kèm và nghiệm thu.

Vòng đời: Mới → Đang thực hiện → Chờ nghiệm thu → Hoàn thành (hoặc Không thực hiện, kèm lý do).
Ban TGĐ / quản trị duyệt, giao việc và nghiệm thu; người phụ trách (một tài khoản) cập nhật tiến độ, tải
kết quả và báo hoàn thành. Chuyển sang "Chờ nghiệm thu" / "Hoàn thành" phải có ít nhất một file kết quả.
"""
import re
import shutil
import sqlite3
from datetime import date
from pathlib import Path

from fastapi import HTTPException

from . import access, auth, documents
from .db import row, rows

STATUS = {"new": "Mới", "in_progress": "Đang thực hiện", "review": "Chờ nghiệm thu",
          "done": "Hoàn thành", "dropped": "Không thực hiện"}
PRIORITY = {"high": "Cao", "normal": "Thường", "low": "Thấp"}
# Trạng thái được chuyển tới từ mỗi trạng thái (Ban TGĐ); người phụ trách chỉ dùng ASSIGNEE_MOVES
NEXT = {"new": {"in_progress", "dropped"},
        "in_progress": {"review", "done", "dropped"}, "review": {"done", "in_progress", "dropped"},
        "done": {"in_progress"}, "dropped": {"new"}}
ASSIGNEE_MOVES = {("in_progress", "review")}
NEED_RESULT = {"review", "done"}
FILE_KINDS = {"ref": "Tài liệu tham chiếu", "result": "Kết quả / bằng chứng"}
OPEN_STATUS = ("new", "in_progress", "review")
STALE_REVIEW_DAYS = 3  # chờ nghiệm thu quá số ngày này thì nhắc Ban TGĐ
# Thời điểm đề xuất được báo hoàn thành (lần chuyển sang "Chờ nghiệm thu" gần nhất)
REVIEW_SINCE = "(SELECT MAX(e.at) FROM proposal_events e WHERE e.proposal_id = p.id AND e.to_status = 'review')"


def is_boss(user: dict) -> bool:
    return user["role"] in auth.EDIT_ALL_ROLES


def _fail(msg: str, code: int = 400):
    raise HTTPException(code, msg)


def _event(conn, pid: int, user: dict, kind: str, from_status=None, to_status=None, note=None) -> None:
    conn.execute("INSERT INTO proposal_events (proposal_id, user_id, kind, from_status, to_status, note) VALUES (?,?,?,?,?,?)",
                 (pid, user["id"], kind, from_status, to_status, note))


def _get(conn, user: dict, pid: int) -> dict:
    """Đề xuất mà user được xem: Ban TGĐ xem tất cả, còn lại chỉ người tạo và người phụ trách."""
    p = row(conn, "SELECT * FROM proposals WHERE id = ?", (pid,))
    if not p or not (is_boss(user) or user["id"] in (p["created_by"], p["owner_user_id"])):
        _fail("Không tìm thấy đề xuất", 404)
    return p


def _can_move(user: dict, p: dict, to: str) -> bool:
    if is_boss(user):
        return to in NEXT[p["status"]]
    return p["owner_user_id"] == user["id"] and (p["status"], to) in ASSIGNEE_MOVES


def _result_count(conn, pid: int) -> int:
    return conn.execute("SELECT COUNT(*) FROM proposal_files WHERE proposal_id = ? AND kind = 'result'", (pid,)).fetchone()[0]


def _decorate(p: dict, user: dict, results: int) -> dict:
    today = date.today().isoformat()
    p["overdue"] = bool(p["due_date"] and p["due_date"] < today and p["status"] in OPEN_STATUS)
    p["result_files"] = results
    since = p.get("review_since")
    p["review_days"] = (date.today() - date.fromisoformat(since[:10])).days if p["status"] == "review" and since else None
    p["review_stale"] = p["review_days"] is not None and p["review_days"] >= STALE_REVIEW_DAYS
    p["moves"] = [s for s in STATUS if _can_move(user, p, s)]
    p["can_assign"] = is_boss(user)
    return p


def list_proposals(conn, user: dict, status: str | None = None, mine: bool = False) -> list[dict]:
    where, args = [], []
    if mine:  # "Việc được giao cho tôi"
        where.append("p.owner_user_id = ?")
        args.append(user["id"])
    elif not is_boss(user):
        where.append("(p.created_by = ? OR p.owner_user_id = ?)")
        args += [user["id"], user["id"]]
    if status in STATUS:
        where.append("p.status = ?")
        args.append(status)
    sql = (f"SELECT p.*, {REVIEW_SINCE} AS review_since, u.full_name AS author, o.full_name AS owner_name,"
           " (SELECT COUNT(*) FROM proposal_files f WHERE f.proposal_id = p.id) AS file_count,"
           " (SELECT COUNT(*) FROM proposal_files f WHERE f.proposal_id = p.id AND f.kind = 'result') AS result_count"
           " FROM proposals p LEFT JOIN users u ON u.id = p.created_by LEFT JOIN users o ON o.id = p.owner_user_id")
    sql += (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY p.id DESC LIMIT 500"
    out = rows(conn, sql, tuple(args))
    for p in out:
        _decorate(p, user, p["result_count"])
    return out


def detail(conn, user: dict, pid: int) -> dict:
    p = _get(conn, user, pid)
    p["review_since"] = conn.execute("SELECT " + REVIEW_SINCE.replace("p.id", "?"), (pid,)).fetchone()[0]
    p["author"] = (row(conn, "SELECT full_name FROM users WHERE id = ?", (p["created_by"],)) or {}).get("full_name")
    p["owner_name"] = (row(conn, "SELECT full_name FROM users WHERE id = ?", (p["owner_user_id"],)) or {}).get("full_name")
    p["events"] = rows(conn, "SELECT e.*, u.full_name AS by_name FROM proposal_events e LEFT JOIN users u ON u.id = e.user_id"
                             " WHERE e.proposal_id = ? ORDER BY e.id", (pid,))
    p["files"] = rows(conn, "SELECT f.id, f.kind, f.filename, f.size_bytes, f.uploaded_at, f.uploaded_by, f.doc_id, u.full_name AS by_name"
                            " FROM proposal_files f LEFT JOIN users u ON u.id = f.uploaded_by WHERE f.proposal_id = ? ORDER BY f.id", (pid,))
    p["files"] = [{**f, "archived": bool(f["doc_id"])} for f in p["files"]]
    p["can_archive"] = is_boss(user) and p["status"] == "done" and any(f["kind"] == "result" and not f["doc_id"] for f in p["files"])
    return _decorate(p, user, sum(f["kind"] == "result" for f in p["files"]))


def assignees(conn) -> list[dict]:
    """Tài khoản có thể được giao việc: đang hoạt động, đã được duyệt."""
    return rows(conn, "SELECT id, full_name, username, role FROM users WHERE active = 1 AND pending_approval = 0"
                      " ORDER BY COALESCE(full_name, username)")


def create(conn, user: dict, title: str, body: str = "") -> dict:
    title = title.strip()[:200]
    if not title:
        _fail("Thiếu tiêu đề đề xuất")
    pid = conn.execute("INSERT INTO proposals (title, body, created_by) VALUES (?, ?, ?)",
                       (title, body.strip()[:8000], user["id"])).lastrowid
    _event(conn, pid, user, "create", to_status="new")
    return row(conn, "SELECT * FROM proposals WHERE id = ?", (pid,))


def _valid_date(s: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        _fail("Hạn hoàn thành phải có dạng năm-tháng-ngày")
    try:
        date.fromisoformat(s)
    except ValueError:
        _fail("Hạn hoàn thành không hợp lệ")
    return s


def update(conn, user: dict, pid: int, fields: dict) -> dict:
    """fields: status, status_note, owner_user_id, due_date, priority, note. Trả về bản ghi sau cập nhật."""
    p = _get(conn, user, pid)
    sets: dict = {}
    status_note = (fields.get("status_note") or "").strip()[:1000] or None

    if "status" in fields and fields["status"] != p["status"]:
        to = fields["status"]
        if to not in STATUS:
            _fail("Trạng thái không hợp lệ")
        if not _can_move(user, p, to):
            _fail(f"Không thể chuyển từ “{STATUS[p['status']]}” sang “{STATUS.get(to, to)}”", 403 if not is_boss(user) else 400)
        if to == "dropped" and not status_note:
            _fail("Cần ghi lý do khi chọn Không thực hiện")
        if to in NEED_RESULT and not _result_count(conn, pid):
            _fail("Cần tải lên ít nhất một file kết quả / bằng chứng trước khi báo hoàn thành")
        if to == "in_progress" and p["status"] == "new" and not (p["owner_user_id"] or fields.get("owner_user_id")):
            _fail("Cần giao cho một người phụ trách trước khi bắt đầu thực hiện")
        sets["status"] = to

    if any(k in fields for k in ("owner_user_id", "due_date", "priority", "note")):
        if not is_boss(user):
            _fail("Chỉ Ban TGĐ / quản trị được giao việc và đặt hạn", 403)
        if "owner_user_id" in fields:
            oid = fields["owner_user_id"] or None
            if oid is not None:
                o = row(conn, "SELECT id, full_name, username FROM users WHERE id = ? AND active = 1", (oid,))
                if not o:
                    _fail("Người phụ trách không tồn tại hoặc đã bị khoá")
                sets["owner"] = o["full_name"] or o["username"]
            else:
                sets["owner"] = None
            sets["owner_user_id"] = oid
        if "due_date" in fields:
            sets["due_date"] = _valid_date(fields["due_date"]) if fields["due_date"] else None
        if "priority" in fields:
            if fields["priority"] not in PRIORITY:
                _fail("Mức ưu tiên không hợp lệ")
            sets["priority"] = fields["priority"]
        if "note" in fields:
            sets["note"] = (fields["note"] or "").strip()[:2000] or None

    if sets:
        conn.execute(f"UPDATE proposals SET {', '.join(f'{k} = ?' for k in sets)}, updated_at = datetime('now','localtime') WHERE id = ?",
                     (*sets.values(), pid))
        if "status" in sets:
            _event(conn, pid, user, "status", p["status"], sets["status"], status_note)
        if "owner_user_id" in sets and sets["owner_user_id"] != p["owner_user_id"]:
            _event(conn, pid, user, "assign", note=sets["owner"] or "Bỏ người phụ trách")
        if "note" in sets and sets["note"] != p["note"]:
            _event(conn, pid, user, "note", note=sets["note"])
    return row(conn, "SELECT * FROM proposals WHERE id = ?", (pid,))


def add_file(conn, user: dict, pid: int, kind: str, filename: str, data: bytes) -> int:
    p = _get(conn, user, pid)
    if kind not in FILE_KINDS:
        _fail("Loại file không hợp lệ")
    if kind == "result" and not (is_boss(user) or p["owner_user_id"] == user["id"]):
        _fail("Chỉ người phụ trách hoặc Ban TGĐ được tải file kết quả", 403)
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in documents.ALLOWED_EXT:
        _fail(f"Chỉ nhận các định dạng: {', '.join(sorted(documents.ALLOWED_EXT))}")
    if not data:
        _fail("File rỗng")
    if len(data) > documents.MAX_UPLOAD_BYTES:
        _fail("File vượt quá 50 MB")
    folder = documents.UPLOAD_DIR / "proposals"
    folder.mkdir(parents=True, exist_ok=True)
    fid = conn.execute("INSERT INTO proposal_files (proposal_id, kind, filename, stored_path, size_bytes, uploaded_by)"
                       " VALUES (?,?,?,'',?,?)", (pid, kind, filename[:200], len(data), user["id"])).lastrowid
    path = folder / f"{fid}_{documents.safe_filename(filename)}"
    path.write_bytes(data)
    conn.execute("UPDATE proposal_files SET stored_path = ? WHERE id = ?", (str(path), fid))
    conn.execute("UPDATE proposals SET updated_at = datetime('now','localtime') WHERE id = ?", (pid,))
    _event(conn, pid, user, "file", note=f"{FILE_KINDS[kind]}: {filename[:200]}")
    return fid


def get_file(conn, user: dict, pid: int, fid: int) -> dict:
    _get(conn, user, pid)
    f = row(conn, "SELECT * FROM proposal_files WHERE id = ? AND proposal_id = ?", (fid, pid))
    if not f:
        _fail("Không tìm thấy file", 404)
    return f


def delete_file(conn, user: dict, pid: int, fid: int) -> None:
    """Chỉ chuyển vào thùng rác, không xoá cứng. Ban TGĐ xoá được mọi file; người khác chỉ xoá file mình tải."""
    f = get_file(conn, user, pid, fid)
    if not (is_boss(user) or f["uploaded_by"] == user["id"]):
        _fail("Bạn chỉ xoá được file do mình tải lên", 403)
    p = row(conn, "SELECT status FROM proposals WHERE id = ?", (pid,))
    if f["kind"] == "result" and p["status"] in NEED_RESULT and _result_count(conn, pid) <= 1:
        _fail("Đề xuất đang ở trạng thái cần có file kết quả, hãy tải file thay thế trước khi xoá")
    conn.execute("DELETE FROM proposal_files WHERE id = ?", (fid,))
    _event(conn, pid, user, "file", note=f"Xoá file: {f['filename']}")
    src = Path(f["stored_path"])
    if src.is_file():
        trash = documents.UPLOAD_DIR / "_trash"
        trash.mkdir(exist_ok=True)
        shutil.move(str(src), str(trash / src.name))


def archive_results(conn, user: dict, pid: int, level: str = access.DEFAULT_LEVEL) -> list[int]:
    """Sau nghiệm thu: sao chép các file kết quả chưa lưu vào kho tài liệu (AI đọc được, lọc theo độ mật).
    File gốc vẫn giữ ở đề xuất. Trả về id tài liệu mới để chạy trích xuất nội dung nền."""
    if not is_boss(user):
        _fail("Chỉ Ban TGĐ / quản trị được lưu kết quả vào kho tài liệu", 403)
    p = _get(conn, user, pid)
    if p["status"] != "done":
        _fail("Chỉ lưu vào kho tài liệu sau khi đã nghiệm thu hoàn thành")
    access.check_level(user, level)
    files = rows(conn, "SELECT * FROM proposal_files WHERE proposal_id = ? AND kind = 'result' AND doc_id IS NULL ORDER BY id", (pid,))
    files = [f for f in files if Path(f["stored_path"]).is_file()]
    if not files:
        _fail("Không có file kết quả nào chưa được lưu vào kho")
    doc_ids = []
    for f in files:
        stem = f["filename"].rsplit(".", 1)[0]
        doc_id = conn.execute(
            "INSERT INTO documents (title, doc_type, filename, stored_path, size_bytes, uploaded_by, access_level)"
            " VALUES (?, 'khac', ?, '', ?, ?, ?)",
            (f"{p['title'][:120]} — {stem}"[:200], f["filename"], f["size_bytes"], user["id"], level)).lastrowid
        dest = documents.UPLOAD_DIR / f"{doc_id}_{documents.safe_filename(f['filename'])}"
        shutil.copy2(f["stored_path"], dest)
        conn.execute("UPDATE documents SET stored_path = ? WHERE id = ?", (str(dest), doc_id))
        conn.execute("UPDATE proposal_files SET doc_id = ? WHERE id = ?", (doc_id, f["id"]))
        doc_ids.append(doc_id)
    _event(conn, pid, user, "archive", note=f"Lưu {len(doc_ids)} file kết quả vào kho tài liệu ({access.LEVELS[level]})")
    return doc_ids


def stale_review_count(conn: sqlite3.Connection) -> int:
    """Số đề xuất chờ nghiệm thu từ STALE_REVIEW_DAYS ngày trở lên (nhắc Ban TGĐ)."""
    return conn.execute(
        f"SELECT COUNT(*) FROM proposals p WHERE p.status = 'review' AND date({REVIEW_SINCE}) <= date('now','localtime', ?)",
        (f"-{STALE_REVIEW_DAYS} days",)).fetchone()[0]


def pending_count(conn: sqlite3.Connection, user: dict) -> int:
    """Số đề xuất đang chờ chính user xử lý (hiện badge trên menu): Ban TGĐ chờ duyệt/nghiệm thu, người phụ trách chờ làm."""
    if is_boss(user):
        return conn.execute("SELECT COUNT(*) FROM proposals WHERE status IN ('new','review')").fetchone()[0]
    return open_assigned_count(conn, user["id"])


def open_assigned_count(conn: sqlite3.Connection, user_id: int) -> int:
    """Số đề xuất đang giao cho user mà chưa xong (hiện trên menu)."""
    return conn.execute("SELECT COUNT(*) FROM proposals WHERE owner_user_id = ? AND status = 'in_progress'",
                        (user_id,)).fetchone()[0]
