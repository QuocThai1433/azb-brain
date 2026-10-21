"""AZB Brain – API quản trị tri thức công ty.

Chạy: .venv\\Scripts\\python -X utf8 -m uvicorn backend.app:app --port 8000
"""
import json
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai, analytics, auth, contacts, documents, hr_import, webimport
from .db import connect, init_db, row, rows

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="AZB Brain")

# Các cột được phép ghi qua API, theo bảng
WRITABLE = {
    "units": ["code", "name", "full_name", "unit_type", "parent_id", "color_group", "functions", "notes", "verified",
              "sort_order"],
    "employees": ["employee_code", "full_name", "display_name", "email", "phone", "joined_date", "status", "notes", "verified",
                  "job_title", "grade", "labor_group", "unit_id", "hr_department", "hr_division"],
    "positions": ["unit_id", "title", "title_code", "employee_id", "is_head", "headcount", "notes", "sort_order"],
    "processes": ["unit_id", "code", "name", "version", "iso_clause", "owner", "related_units", "purpose", "content",
                  "status", "effective_date"],
    "targets": ["unit_id", "period", "metric", "metric_name", "target_value", "actual_value", "unit_label", "notes"],
}
TOUCH_UPDATED = {"processes", "targets"}
# Bảng chỉ admin/ceo được ghi; các bảng còn lại ghi theo phạm vi đơn vị (manager sửa được đơn vị mình)
EXEC_ONLY_TABLES = {"employees"}
PUBLIC_API = {"/api/auth/state", "/api/auth/login", "/api/auth/setup"}


@app.on_event("startup")
def _startup() -> None:
    init_db()
    documents.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        documents.sync_ai_index(conn)  # dựng sẵn chỉ mục tìm kiếm cho trợ lý AI (lần đầu ~2 giây, sau đó chỉ cập nhật phần đổi)
        empty = conn.execute("SELECT COUNT(*) FROM units").fetchone()[0] == 0
    if empty:
        from .seed import seed
        seed()


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    request.state.user = auth.user_from_token(request.cookies.get(auth.SESSION_COOKIE))
    path = request.url.path
    if path.startswith("/api/") and path not in PUBLIC_API and not request.state.user:
        return JSONResponse({"detail": "Chưa đăng nhập"}, status_code=401)
    response = await call_next(request)
    if not path.startswith("/api/"):  # giao diện: luôn hỏi lại server để nhận bản mới sau khi cập nhật code
        response.headers["Cache-Control"] = "no-cache"
    return response


def _log(conn, user: dict, action: str, entity: str, entity_id=None, detail=None) -> None:
    conn.execute("INSERT INTO audit_log (action, entity, entity_id, detail, user_id) VALUES (?,?,?,?,?)",
                 (action, entity, entity_id, detail, user["id"]))


# ---------- Đăng nhập ----------
_failed_logins: dict[str, list[float]] = {}
LOGIN_MAX_FAILS = 8       # số lần sai liên tiếp trước khi tạm khoá
LOGIN_LOCK_SECONDS = 120  # thời gian tạm khoá (giây)


def _recent_fails(username: str, now: float) -> list[float]:
    return [t for t in _failed_logins.get(username, []) if now - t < LOGIN_LOCK_SECONDS]


def _is_locked(username: str) -> bool:
    return len(_recent_fails(username, time.time())) >= LOGIN_MAX_FAILS


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupRequest(LoginRequest):
    full_name: str | None = None


def _login_response(user_id: int) -> JSONResponse:
    with connect() as conn:
        token = auth.create_session(conn, user_id)
        user = row(conn, "SELECT id, username, full_name, role, unit_id FROM users WHERE id = ?", (user_id,))
    resp = JSONResponse({"user": user})
    resp.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=auth.SESSION_DAYS * 86400)
    return resp


@app.get("/api/auth/state")
def auth_state(request: Request):
    with connect() as conn:
        needs_setup = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    user = request.state.user
    if user:
        user = {**user, "can_use_ai": user["role"] in auth.AI_ROLES, "edit_all": user["role"] in auth.EDIT_ALL_ROLES}
        with connect() as conn:
            if user["role"] == "admin":
                user["pending_requests"] = conn.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'").fetchone()[0]
            else:  # kết quả duyệt mới mà user chưa xem
                user["pending_requests"] = conn.execute(
                    "SELECT COUNT(*) FROM access_requests WHERE user_id = ? AND seen_by_user = 0", (user["id"],)).fetchone()[0]
    return {"needs_setup": needs_setup, "user": user, "roles": auth.ROLES}


@app.post("/api/auth/setup")
def auth_setup(req: SetupRequest):
    """Tạo tài khoản quản trị đầu tiên – chỉ dùng được khi chưa có tài khoản nào."""
    if len(req.password) < 8:
        raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
    with connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            raise HTTPException(403, "Hệ thống đã có tài khoản quản trị")
        cur = conn.execute("INSERT INTO users (username, full_name, role, password_hash) VALUES (?,?, 'admin', ?)",
                           (req.username.strip().lower(), req.full_name, auth.hash_password(req.password)))
    return _login_response(cur.lastrowid)


@app.post("/api/auth/login")
def login(req: LoginRequest):
    username = req.username.strip().lower()
    now = time.time()
    recent = _recent_fails(username, now)
    if len(recent) >= LOGIN_MAX_FAILS:
        wait = max(1, int(LOGIN_LOCK_SECONDS - (now - recent[0])))
        raise HTTPException(429, f"Sai mật khẩu quá nhiều lần, thử lại sau {wait // 60 + (1 if wait % 60 else 0)} phút")
    with connect() as conn:
        u = row(conn, "SELECT * FROM users WHERE username = ? AND active = 1", (username,))
    if not u or not auth.verify_password(req.password, u["password_hash"]):
        _failed_logins[username] = recent + [now]
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    _failed_logins.pop(username, None)
    return _login_response(u["id"])


@app.post("/api/auth/logout")
def logout(request: Request):
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (request.cookies.get(auth.SESSION_COOKIE),))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


@app.post("/api/auth/password")
def change_password(req: PasswordChange, request: Request):
    user = auth.current_user(request)
    if len(req.new_password) < 8:
        raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
    with connect() as conn:
        u = row(conn, "SELECT password_hash FROM users WHERE id = ?", (user["id"],))
        if not auth.verify_password(req.old_password, u["password_hash"]):
            raise HTTPException(400, "Mật khẩu hiện tại không đúng")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (auth.hash_password(req.new_password), user["id"]))
    return {"ok": True}


# ---------- Quản lý tài khoản (admin) ----------
@app.get("/api/users")
def list_users(request: Request):
    auth.require_roles(request, {"admin"})
    with connect() as conn:
        out = rows(conn, "SELECT u.id, u.username, u.full_name, u.role, u.unit_id, x.name AS unit_name, u.active, u.created_at"
                         " FROM users u LEFT JOIN units x ON x.id = u.unit_id ORDER BY u.username")
        perms = {}
        for r in conn.execute("SELECT user_id, feature FROM user_permissions"):
            perms.setdefault(r[0], []).append(r[1])
    for u in out:
        u["locked"] = _is_locked(u["username"])
        u["granted"] = perms.get(u["id"], [])
    return out


@app.put("/api/users/{user_id}/permissions")
def set_user_permissions(user_id: int, data: dict, request: Request):
    """Admin cấp/thu hồi quyền tính năng. data = {"features": ["docs_view", ...]}"""
    admin = auth.require_roles(request, {"admin"})
    features = data.get("features") or []
    if not isinstance(features, list) or any(f not in auth.FEATURES for f in features):
        raise HTTPException(400, "Quyền không hợp lệ")
    with connect() as conn:
        if not row(conn, "SELECT id FROM users WHERE id = ?", (user_id,)):
            raise HTTPException(404, "Không tìm thấy tài khoản")
        conn.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
        conn.executemany("INSERT INTO user_permissions (user_id, feature) VALUES (?,?)", [(user_id, f) for f in set(features)])
        _log(conn, admin, "permissions", "users", user_id, ",".join(sorted(set(features))))
    return {"ok": True}


@app.post("/api/users/{user_id}/unlock")
def unlock_user(user_id: int, request: Request):
    admin = auth.require_roles(request, {"admin"})
    with connect() as conn:
        u = row(conn, "SELECT username FROM users WHERE id = ?", (user_id,))
        if not u:
            raise HTTPException(404, "Không tìm thấy tài khoản")
        _failed_logins.pop(u["username"], None)
        _log(conn, admin, "unlock", "users", user_id)
    return {"ok": True}


@app.post("/api/users")
def create_user(data: dict, request: Request):
    admin = auth.require_roles(request, {"admin"})
    if data.get("role") not in auth.ROLES:
        raise HTTPException(400, "Vai trò không hợp lệ")
    if len(data.get("password") or "") < 8:
        raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, full_name, role, unit_id, password_hash) VALUES (?,?,?,?,?)",
                (data["username"].strip().lower(), data.get("full_name"), data["role"], data.get("unit_id") or None,
                 auth.hash_password(data["password"])))
        except Exception as e:
            raise HTTPException(400, str(e))
        features = [f for f in (data.get("features") or []) if f in auth.FEATURES]
        conn.executemany("INSERT OR IGNORE INTO user_permissions (user_id, feature) VALUES (?,?)",
                         [(cur.lastrowid, f) for f in features])
        _log(conn, admin, "create", "users", cur.lastrowid)
    return {"id": cur.lastrowid}


@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: dict, request: Request):
    admin = auth.require_roles(request, {"admin"})
    fields = {k: data[k] for k in ("full_name", "role", "unit_id", "active") if k in data}
    if "role" in fields and fields["role"] not in auth.ROLES:
        raise HTTPException(400, "Vai trò không hợp lệ")
    if user_id == admin["id"] and (fields.get("role", "admin") != "admin" or fields.get("active", 1) in (0, "0")):
        raise HTTPException(400, "Không thể tự hạ quyền hoặc khoá tài khoản của chính mình")
    if data.get("password"):
        if len(data["password"]) < 8:
            raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
        fields["password_hash"] = auth.hash_password(data["password"])
        with connect() as conn:
            u = row(conn, "SELECT username FROM users WHERE id = ?", (user_id,))
        if u:
            _failed_logins.pop(u["username"], None)
    if "unit_id" in fields:
        fields["unit_id"] = fields["unit_id"] or None
    if not fields:
        raise HTTPException(400, "Không có dữ liệu hợp lệ")
    with connect() as conn:
        conn.execute(f"UPDATE users SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?", (*fields.values(), user_id))
        if fields.get("active") in (0, "0") or "password_hash" in fields:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        _log(conn, admin, "update", "users", user_id)
    return {"ok": True}


# ---------- Xin cấp quyền truy cập ----------
REQUEST_KEEP_DAYS = 30  # đơn đã xử lý chỉ hiện trong khoảng này; vẫn lưu trong database


@app.get("/api/access-requests")
def list_access_requests(request: Request, tab: str = "pending", q: str = "", month: str = ""):
    """Admin: tab=pending (chờ duyệt) hoặc tab=history (đã xử lý, lọc theo người q và tháng YYYY-MM).
    Người khác: đơn chờ duyệt + đơn đã xử lý trong REQUEST_KEEP_DAYS ngày gần nhất."""
    user = auth.current_user(request)
    sql = "SELECT r.*, u.username, u.full_name FROM access_requests r JOIN users u ON u.id = r.user_id WHERE "
    with connect() as conn:
        if user["role"] == "admin":
            if tab == "pending":
                out = rows(conn, sql + "r.status = 'pending' ORDER BY r.created_at")
            else:
                cond, args = ["r.status != 'pending'"], []
                if q.strip():
                    cond.append("(u.username LIKE ? OR u.full_name LIKE ?)")
                    args += [f"%{q.strip()}%"] * 2
                if month:
                    cond.append("substr(r.decided_at, 1, 7) = ?")
                    args.append(month)
                out = rows(conn, sql + " AND ".join(cond) + " ORDER BY r.decided_at DESC LIMIT 300", args)
        else:
            out = rows(conn, sql + "r.user_id = ? AND (r.status = 'pending' OR r.decided_at >= datetime('now','localtime', ?))"
                       " ORDER BY r.created_at DESC", (user["id"], f"-{REQUEST_KEEP_DAYS} days"))
    for r in out:
        r["features"] = [f for f in r["features"].split(",") if f]
    return out


@app.post("/api/access-requests/seen")
def mark_requests_seen(request: Request):
    user = auth.current_user(request)
    with connect() as conn:
        conn.execute("UPDATE access_requests SET seen_by_user = 1 WHERE user_id = ?", (user["id"],))
    return {"ok": True}


def _request_payload(user: dict, data: dict) -> tuple[str, str | None]:
    features = data.get("features") or []
    if not isinstance(features, list) or not features or any(f not in auth.FEATURES for f in features):
        raise HTTPException(400, "Hãy chọn ít nhất một quyền cần xin")
    features = [f for f in dict.fromkeys(features) if f not in user["permissions"]]
    if not features:
        raise HTTPException(400, "Bạn đã có các quyền này rồi")
    reason = (data.get("reason") or "").strip()[:500]
    if not reason:
        raise HTTPException(400, "Vui lòng nhập lý do xin quyền")
    return ",".join(features), reason


@app.post("/api/access-requests")
def create_access_request(data: dict, request: Request):
    user = auth.current_user(request)
    if user["role"] in auth.EDIT_ALL_ROLES:
        raise HTTPException(400, "Tài khoản này đã có đủ quyền")
    features, reason = _request_payload(user, data)
    with connect() as conn:
        if conn.execute("SELECT 1 FROM access_requests WHERE user_id = ? AND status = 'pending'", (user["id"],)).fetchone():
            raise HTTPException(400, "Bạn đang có yêu cầu chờ duyệt. Hãy chỉnh sửa yêu cầu đó nếu muốn xin thêm quyền.")
        cur = conn.execute("INSERT INTO access_requests (user_id, features, reason) VALUES (?,?,?)",
                           (user["id"], features, reason))
        _log(conn, user, "request", "access_requests", cur.lastrowid, features)
    return {"id": cur.lastrowid}


def _own_pending_request(conn, user: dict, req_id: int) -> dict:
    r = row(conn, "SELECT * FROM access_requests WHERE id = ? AND user_id = ?", (req_id, user["id"]))
    if not r:
        raise HTTPException(404, "Không tìm thấy yêu cầu")
    if r["status"] != "pending":
        raise HTTPException(400, "Yêu cầu này đã được xử lý nên không thể thay đổi")
    return r


@app.put("/api/access-requests/{req_id}")
def update_access_request(req_id: int, data: dict, request: Request):
    """User sửa đơn của mình khi còn chờ duyệt (nhập sai, hoặc muốn xin thêm quyền)."""
    user = auth.current_user(request)
    features, reason = _request_payload(user, data)
    with connect() as conn:
        _own_pending_request(conn, user, req_id)
        conn.execute("UPDATE access_requests SET features = ?, reason = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                     (features, reason, req_id))
        _log(conn, user, "request_update", "access_requests", req_id, features)
    return {"ok": True}


@app.delete("/api/access-requests/{req_id}")
def withdraw_access_request(req_id: int, request: Request):
    """User rút lại đơn đang chờ duyệt."""
    user = auth.current_user(request)
    with connect() as conn:
        _own_pending_request(conn, user, req_id)
        conn.execute("UPDATE access_requests SET status = 'cancelled', decided_at = datetime('now','localtime') WHERE id = ?", (req_id,))
        _log(conn, user, "request_withdraw", "access_requests", req_id)
    return {"ok": True}


@app.post("/api/access-requests/{req_id}/decide")
def decide_access_request(req_id: int, data: dict, request: Request):
    """Admin duyệt/từ chối. data = {"approve": bool, "note": str}. Duyệt thì cấp thêm quyền đã xin."""
    admin = auth.require_roles(request, {"admin"})
    approve = bool(data.get("approve"))
    note = (data.get("note") or "").strip()[:500]
    if not approve and not note:
        raise HTTPException(400, "Vui lòng nhập lý do từ chối")
    with connect() as conn:
        r = row(conn, "SELECT * FROM access_requests WHERE id = ?", (req_id,))
        if not r:
            raise HTTPException(404, "Không tìm thấy yêu cầu")
        if r["status"] != "pending":
            raise HTTPException(400, "Yêu cầu này đã được xử lý")
        if approve:
            feats = [f for f in r["features"].split(",") if f in auth.FEATURES]
            conn.executemany("INSERT OR IGNORE INTO user_permissions (user_id, feature) VALUES (?,?)",
                             [(r["user_id"], f) for f in feats])
        conn.execute("UPDATE access_requests SET status = ?, decided_by = ?, decided_at = datetime('now','localtime'),"
                     " admin_note = ?, seen_by_user = 0 WHERE id = ?",
                     ("approved" if approve else "rejected", admin["id"], note or None, req_id))
        _log(conn, admin, "approve" if approve else "reject", "access_requests", req_id)
    return {"ok": True}


# ---------- Đơn vị / sơ đồ tổ chức ----------
@app.get("/api/units")
def list_units():
    with connect() as conn:
        return analytics.units_flat(conn)


@app.get("/api/tree")
def get_tree():
    with connect() as conn:
        return analytics.org_tree(conn)


@app.get("/api/units/{unit_id}")
def get_unit(unit_id: int, request: Request):
    with connect() as conn:
        u = analytics.unit_detail(conn, unit_id)
        if not u:
            raise HTTPException(404, "Không tìm thấy đơn vị")
        allowed = auth.managed_unit_ids(conn, request.state.user)
        u["documents"] = [] if "docs_view" not in request.state.user["permissions"] else rows(conn, "SELECT id, title, code, version, doc_type, filename, extract_status, page_count,"
                                    " uploaded_at FROM documents WHERE unit_id = ? ORDER BY code, title", (unit_id,))
    u["can_edit"] = allowed is None or unit_id in allowed
    return u


# ---------- Nhân sự ----------
@app.get("/api/employees")
def list_employees(request: Request):
    """Email / số điện thoại: chỉ admin/ceo xem tất cả; quản lý đơn vị xem nhân sự thuộc đơn vị mình quản lý;
    các tài khoản khác không xem được."""
    user = auth.current_user(request)
    with connect() as conn:
        allowed = auth.managed_unit_ids(conn, user)  # None = xem tất cả
        if allowed is None:
            can_see = lambda e: True
        else:
            can_see = lambda e: e["unit_id"] is not None and e["unit_id"] in allowed
        return analytics.employee_roles(conn, can_see_contacts=can_see)


@app.post("/api/employees/import")
async def import_employees(request: Request, file: UploadFile = File(...)):
    """Nhập lại danh sách nhân sự HCNS (Excel) – cập nhật theo mã nhân viên."""
    auth.require_permission(request, "import_hr")
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Cần file Excel .xlsx")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(await file.read())
    try:
        return hr_import.import_hr(tmp.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        Path(tmp.name).unlink(missing_ok=True)


# ---------- Quy trình / mục tiêu ----------
@app.get("/api/processes")
def list_processes(unit_id: int | None = None):
    with connect() as conn:
        if unit_id:
            return rows(conn, "SELECT * FROM processes WHERE unit_id = ? ORDER BY code, name", (unit_id,))
        return rows(conn, "SELECT p.*, u.name AS unit_name FROM processes p JOIN units u ON u.id = p.unit_id"
                          " ORDER BY u.sort_order, p.code")


@app.get("/api/targets")
def list_targets(unit_id: int | None = None):
    with connect() as conn:
        if unit_id:
            return rows(conn, "SELECT * FROM targets WHERE unit_id = ? ORDER BY period DESC", (unit_id,))
        return rows(conn, "SELECT t.*, u.name AS unit_name FROM targets t LEFT JOIN units u ON u.id = t.unit_id"
                          " ORDER BY t.period DESC, u.sort_order")


# ---------- CRUD chung (có kiểm tra quyền) ----------
def _clean(table: str, data: dict) -> dict:
    allowed = WRITABLE[table]
    return {k: (None if v == "" else v) for k, v in data.items() if k in allowed}


def _check_write(conn, user: dict, table: str, existing: dict | None, data: dict) -> None:
    if user["role"] == "viewer":
        raise HTTPException(403, "Tài khoản chỉ xem không được chỉnh sửa")
    exec_only = table in EXEC_ONLY_TABLES or (table == "units" and (existing is None or "parent_id" in data))
    if exec_only:  # hồ sơ nhân sự, thêm đơn vị, đổi cấp trên của đơn vị
        if user["role"] not in auth.EDIT_ALL_ROLES:
            raise HTTPException(403, "Chỉ Ban TGĐ / quản trị được thay đổi mục này")
        return
    if table == "units":
        auth.check_unit_write(conn, user, existing["id"])
        return
    if existing:
        auth.check_unit_write(conn, user, existing["unit_id"])
    if data and "unit_id" in data:
        auth.check_unit_write(conn, user, data["unit_id"])


def _create(request: Request, table: str, data: dict) -> dict:
    user = auth.current_user(request)
    data = _clean(table, data)
    if not data:
        raise HTTPException(400, "Không có dữ liệu hợp lệ")
    with connect() as conn:
        _check_write(conn, user, table, None, data)
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        try:
            cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))
        except Exception as e:  # ràng buộc NOT NULL / UNIQUE
            raise HTTPException(400, str(e))
        _log(conn, user, "create", table, cur.lastrowid)
        return row(conn, f"SELECT * FROM {table} WHERE id = ?", (cur.lastrowid,))


def _update(request: Request, table: str, item_id: int, data: dict) -> dict:
    user = auth.current_user(request)
    data = _clean(table, data)
    with connect() as conn:
        existing = row(conn, f"SELECT * FROM {table} WHERE id = ?", (item_id,))
        if not existing:
            raise HTTPException(404, "Không tìm thấy")
        if table == "units" and existing.get("parent_id") == data.get("parent_id"):
            data.pop("parent_id", None)  # không đổi cấp trên thì không cần quyền điều hành
        _check_write(conn, user, table, existing, data)
        sets = ", ".join(f"{k} = ?" for k in data)
        if table in TOUCH_UPDATED:
            sets = (sets + ", " if sets else "") + "updated_at = datetime('now','localtime')"
        if not sets:
            raise HTTPException(400, "Không có dữ liệu hợp lệ")
        try:
            conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*data.values(), item_id))
        except Exception as e:
            raise HTTPException(400, str(e))
        _log(conn, user, "update", table, item_id)
        return row(conn, f"SELECT * FROM {table} WHERE id = ?", (item_id,))


def _delete(request: Request, table: str, item_id: int) -> dict:
    user = auth.current_user(request)
    with connect() as conn:
        existing = row(conn, f"SELECT * FROM {table} WHERE id = ?", (item_id,))
        if not existing:
            raise HTTPException(404, "Không tìm thấy")
        if table == "units" and user["role"] not in auth.EDIT_ALL_ROLES:
            raise HTTPException(403, "Chỉ Ban TGĐ / quản trị được xoá đơn vị")
        _check_write(conn, user, table, existing, {})
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        _log(conn, user, "delete", table, item_id)
    return {"ok": True}


for _table in WRITABLE:
    def _make(table: str):
        @app.post(f"/api/{table}", name=f"create_{table}")
        def create(data: dict, request: Request):
            return _create(request, table, data)

        @app.put(f"/api/{table}/{{item_id}}", name=f"update_{table}")
        def update(item_id: int, data: dict, request: Request):
            return _update(request, table, item_id, data)

        @app.delete(f"/api/{table}/{{item_id}}", name=f"delete_{table}")
        def delete(item_id: int, request: Request):
            return _delete(request, table, item_id)

    _make(_table)


# ---------- Kho tài liệu ----------
@app.get("/api/documents")
def list_documents(request: Request, unit_id: int | None = None):
    auth.require_permission(request, "docs_view")
    sql = ("SELECT d.id, d.unit_id, u.name AS unit_name, d.process_id, d.title, d.doc_type, d.code, d.version, d.filename,"
           " d.size_bytes, d.page_count, d.char_count, d.extract_status, d.extract_note, d.uploaded_at"
           " FROM documents d LEFT JOIN units u ON u.id = d.unit_id")
    with connect() as conn:
        if unit_id:
            return rows(conn, sql + " WHERE d.unit_id = ? ORDER BY d.code, d.title", (unit_id,))
        return rows(conn, sql + " ORDER BY d.uploaded_at DESC")


@app.get("/api/documents/meta")
def documents_meta(request: Request):
    auth.require_permission(request, "docs_view")
    return {"types": documents.DOC_TYPES, "allowed_ext": sorted(documents.ALLOWED_EXT),
            "max_mb": documents.MAX_UPLOAD_BYTES // (1024 * 1024), "ocr_available": ai.has_gemini()}


@app.get("/api/documents/search")
def search_documents(request: Request, q: str, unit_id: int | None = None):
    auth.require_permission(request, "docs_view")
    with connect() as conn:
        return documents.search_docs(conn, q, limit=30, unit_id=unit_id)


@app.post("/api/documents")
async def upload_document(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    unit_id: int | None = Form(None),
    doc_type: str = Form("quy_trinh"),
    code: str = Form(""),
    version: str = Form(""),
):
    user = auth.require_permission(request, "docs_edit")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in documents.ALLOWED_EXT:
        raise HTTPException(400, f"Chỉ nhận các định dạng: {', '.join(sorted(documents.ALLOWED_EXT))}")
    data = await file.read()
    if len(data) > documents.MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File vượt quá 50 MB")
    with connect() as conn:
        if user["role"] == "viewer":
            raise HTTPException(403, "Tài khoản chỉ xem không được tải tài liệu")
        auth.check_unit_write(conn, user, unit_id)
        cur = conn.execute(
            "INSERT INTO documents (unit_id, title, doc_type, code, version, filename, stored_path, mime, size_bytes, uploaded_by)"
            " VALUES (?,?,?,?,?,?,'',?,?,?)",
            (unit_id, title.strip() or Path(file.filename).stem, doc_type if doc_type in documents.DOC_TYPES else "khac",
             code.strip() or None, version.strip() or None, file.filename, file.content_type, len(data), user["id"]))
        doc_id = cur.lastrowid
        path = documents.UPLOAD_DIR / f"{doc_id}_{documents.safe_filename(file.filename)}"
        path.write_bytes(data)
        conn.execute("UPDATE documents SET stored_path = ? WHERE id = ?", (str(path), doc_id))
        _log(conn, user, "upload", "documents", doc_id, file.filename)
    background.add_task(documents.process_document, doc_id)
    return {"id": doc_id, "status": "pending"}


class UrlRequest(BaseModel):
    url: str


class UrlCommit(BaseModel):
    draft_id: str
    title: str = ""
    unit_id: int | None = None


@app.post("/api/documents/from-url/preview")
def preview_url(req: UrlRequest, request: Request):
    """Bước 1: tải URL, trích nội dung, AI tóm tắt – chưa lưu vào kho."""
    user = auth.require_permission(request, "docs_edit")
    try:
        return webimport.preview(req.url)
    except webimport.ImportError_ as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/documents/from-url")
def commit_url(req: UrlCommit, request: Request):
    """Bước 2: người dùng đã duyệt bản xem trước → lưu và đánh chỉ mục."""
    user = auth.require_permission(request, "docs_edit")
    with connect() as conn:
        auth.check_unit_write(conn, user, req.unit_id)
        try:
            out = webimport.commit(conn, req.draft_id, req.title, req.unit_id, user["id"])
        except webimport.ImportError_ as e:
            raise HTTPException(400, str(e)) from None
        _log(conn, user, "learn_url", "documents", out["id"])
    return out


@app.delete("/api/documents/from-url/{draft_id}")
def discard_url(draft_id: str, request: Request):
    auth.require_permission(request, "docs_edit")
    webimport.discard(draft_id)
    return {"ok": True}


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: int, request: Request):
    auth.require_permission(request, "docs_view")
    with connect() as conn:
        d = row(conn, "SELECT d.*, u.name AS unit_name FROM documents d LEFT JOIN units u ON u.id = d.unit_id WHERE d.id = ?",
                (doc_id,))
    if not d:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    d.pop("stored_path")
    return d


@app.get("/api/documents/{doc_id}/file")
def download_document(doc_id: int, request: Request, inline: bool = False):
    auth.require_permission(request, "docs_view")
    with connect() as conn:
        d = row(conn, "SELECT filename, title, stored_path, mime, content FROM documents WHERE id = ?", (doc_id,))
    if not d or not Path(d["stored_path"]).exists():
        raise HTTPException(404, "Không tìm thấy file")
    path = Path(d["stored_path"])
    mime = d["mime"] or "application/octet-stream"
    if inline:
        # Chỉ cho xem trực tiếp các định dạng trình duyệt tự hiển thị an toàn (không chạy script)
        ext = path.suffix.lower()
        mime = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".txt": "text/plain; charset=utf-8"}.get(ext)
        if not mime:
            # Excel/Word/khác: dựng trang HTML tĩnh để xem ngay trên web
            from fastapi.responses import HTMLResponse
            page = documents.render_html(path, d["title"] or d["filename"], d["content"])
            return HTMLResponse(page, headers={"Content-Security-Policy": "sandbox allow-same-origin; script-src 'none'",
                                               "X-Content-Type-Options": "nosniff"})
        from urllib.parse import quote
        return FileResponse(path, media_type=mime, headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(d['filename'])}",
            "Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff"})
    return FileResponse(path, filename=d["filename"], media_type=mime)


@app.put("/api/documents/{doc_id}")
def update_document(doc_id: int, data: dict, request: Request):
    user = auth.require_permission(request, "docs_edit")
    fields = {k: (data[k] or None) for k in ("title", "doc_type", "code", "version", "unit_id", "process_id") if k in data}
    with connect() as conn:
        d = row(conn, "SELECT unit_id FROM documents WHERE id = ?", (doc_id,))
        if not d:
            raise HTTPException(404, "Không tìm thấy tài liệu")
        auth.check_unit_write(conn, user, d["unit_id"])
        if "unit_id" in fields:
            auth.check_unit_write(conn, user, fields["unit_id"])
        if not fields.get("title", "x"):
            raise HTTPException(400, "Tên tài liệu không được trống")
        if fields:
            conn.execute(f"UPDATE documents SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                         (*fields.values(), doc_id))
        _log(conn, user, "update", "documents", doc_id)
    return {"ok": True}


@app.post("/api/documents/{doc_id}/reprocess")
def reprocess_document(doc_id: int, request: Request, background: BackgroundTasks):
    user = auth.require_permission(request, "docs_edit")
    with connect() as conn:
        d = row(conn, "SELECT unit_id FROM documents WHERE id = ?", (doc_id,))
        if not d:
            raise HTTPException(404, "Không tìm thấy tài liệu")
        auth.check_unit_write(conn, user, d["unit_id"])
        conn.execute("UPDATE documents SET extract_status = 'pending' WHERE id = ?", (doc_id,))
    background.add_task(documents.process_document, doc_id)
    return {"ok": True}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, request: Request):
    user = auth.require_permission(request, "docs_edit")
    with connect() as conn:
        d = row(conn, "SELECT unit_id, stored_path FROM documents WHERE id = ?", (doc_id,))
        if not d:
            raise HTTPException(404, "Không tìm thấy tài liệu")
        auth.check_unit_write(conn, user, d["unit_id"])
        conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        _log(conn, user, "delete", "documents", doc_id)
    Path(d["stored_path"]).unlink(missing_ok=True)
    return {"ok": True}


# ---------- Phân tích & AI ----------
@app.get("/api/insights")
def get_insights(request: Request):
    auth.require_permission(request, "insights")
    with connect() as conn:
        return analytics.insights(conn)


class ChatRequest(BaseModel):
    content: str
    conversation_id: int | None = None  # bỏ trống = bắt đầu đoạn chat mới


def _own_conversation(conn, user: dict, conv_id: int) -> dict:
    conv = row(conn, "SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user["id"]))
    if not conv:
        raise HTTPException(404, "Không tìm thấy đoạn chat")
    return conv


def _conv_title(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 60 else text[:57].rstrip() + "..."


@app.get("/api/conversations")
def list_conversations(request: Request):
    user = auth.require_roles(request, auth.AI_ROLES)
    with connect() as conn:
        return rows(conn, "SELECT id, title, created_at, updated_at FROM conversations WHERE user_id = ?"
                          " ORDER BY updated_at DESC, id DESC", (user["id"],))


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: int, request: Request):
    user = auth.require_roles(request, auth.AI_ROLES)
    with connect() as conn:
        conv = _own_conversation(conn, user, conv_id)
        msgs = rows(conn, "SELECT role, content, tools_used, created_at FROM chat_messages WHERE conversation_id = ?"
                          " ORDER BY id", (conv_id,))
        # lịch sử lưu dấu [[LH:id]] (không lưu số): điền liên hệ hiện tại khi hiển thị
        emps = contacts.load(conn, set().union(*(contacts.marker_ids(m["content"]) for m in msgs)))
        can_see = user["role"] in auth.EDIT_ALL_ROLES
        for m in msgs:
            m["content"] = contacts.render(m["content"], emps, can_see)
    for m in msgs:
        m["tools"] = json.loads(m.pop("tools_used") or "[]")
    return {**conv, "messages": msgs}


@app.put("/api/conversations/{conv_id}")
def rename_conversation(conv_id: int, data: dict, request: Request):
    user = auth.require_roles(request, auth.AI_ROLES)
    title = _conv_title(str(data.get("title") or ""))
    if not title:
        raise HTTPException(400, "Tên đoạn chat không được trống")
    with connect() as conn:
        _own_conversation(conn, user, conv_id)
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))
    return {"ok": True}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, request: Request):
    user = auth.require_roles(request, auth.AI_ROLES)
    with connect() as conn:
        _own_conversation(conn, user, conv_id)
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    return {"ok": True}


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    user = auth.require_roles(request, auth.AI_ROLES)
    # SĐT/email trong câu hỏi không được gửi cho nhà cung cấp AI hay lưu vào lịch sử
    content = contacts.scrub(req.content.strip())
    if not content:
        raise HTTPException(400, "Câu hỏi trống")
    with connect() as conn:
        history = []
        if req.conversation_id:
            _own_conversation(conn, user, req.conversation_id)
            history = rows(conn, "SELECT role, content, tools_used FROM chat_messages WHERE conversation_id = ? ORDER BY id",
                           (req.conversation_id,))
    # đoạn chat cũ có thể còn số điện thoại thô: che trước khi gửi lại cho AI
    history = [{**m, "content": contacts.scrub(m["content"])} for m in history]
    res = ai.answer(history + [{"role": "user", "content": content}])
    if res.get("error"):  # không lưu lượt lỗi để lần hỏi lại không gửi kèm câu trả lời lỗi cho AI
        return {**res, "conversation_id": req.conversation_id}
    # câu trả lời AI viết: che số lạ; dấu [[LH:id]] được giữ lại trong lịch sử, số chỉ điền khi hiển thị
    answer = contacts.scrub(res["answer"])
    can_see = user["role"] in auth.EDIT_ALL_ROLES
    with connect() as conn:
        conv_id = req.conversation_id
        if not conv_id:
            conv_id = conn.execute("INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                                   (user["id"], _conv_title(content))).lastrowid
        conn.executemany(
            "INSERT INTO chat_messages (conversation_id, role, content, tools_used) VALUES (?, ?, ?, ?)",
            [(conv_id, "user", content, None),
             (conv_id, "assistant", answer, json.dumps(res.get("tools_used") or [], ensure_ascii=False))])
        conn.execute("UPDATE conversations SET updated_at = datetime('now','localtime') WHERE id = ?", (conv_id,))
        title = conn.execute("SELECT title FROM conversations WHERE id = ?", (conv_id,)).fetchone()[0]
        shown = contacts.render_for_viewer(conn, answer, can_see)
    return {**res, "answer": shown, "conversation_id": conv_id, "title": title}


@app.get("/api/ai/status")
def ai_status():
    return ai.status()


# ---------- Giao diện ----------
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
