"""AZB Brain – API quản trị tri thức công ty.

Chạy: .venv\\Scripts\\python -X utf8 -m uvicorn backend.app:app --port 8000
"""
import json
import os
import queue
import re
import shutil
import threading
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import access, ai, analytics, auditlog, auth, backup, budget, contacts, documents, export, guard, hr_import, memory, offboarding, privatefiles, selfinfo, semantic, webimport
from .db import connect, init_db, row, rows

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

# Tài liệu API nằm dưới /api để không trùng đường dẫn giao diện (/docs là trang Tài liệu của app)
app = FastAPI(title="AZB Brain", docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")

# Các cột được phép ghi qua API, theo bảng
WRITABLE = {
    "units": ["code", "name", "full_name", "unit_type", "parent_id", "color_group", "functions", "notes", "verified",
              "sort_order"],
    "employees": ["employee_code", "full_name", "display_name", "email", "phone", "joined_date", "status", "notes", "verified",
                  "job_title", "grade", "labor_group", "unit_id", "hr_department", "hr_division", "birth_date", "contract_term"],
    "positions": ["unit_id", "title", "title_code", "employee_id", "is_head", "headcount", "notes", "sort_order"],
    "processes": ["unit_id", "code", "name", "version", "iso_clause", "owner", "related_units", "purpose", "content",
                  "status", "effective_date"],
    "targets": ["unit_id", "period", "metric", "metric_name", "target_value", "actual_value", "unit_label", "notes"],
}
TOUCH_UPDATED = {"processes", "targets"}
# Bảng chỉ admin/ceo được ghi; các bảng còn lại ghi theo phạm vi đơn vị (manager sửa được đơn vị mình)
EXEC_ONLY_TABLES = {"employees"}
PUBLIC_API = {"/api/auth/state", "/api/auth/login", "/api/auth/setup", "/api/auth/register", "/api/auth/units"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",  # trang xem tài liệu nhúng cùng gốc; chặn trang ngoài nhúng AZB Brain
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # Không đặt script-src chặt vì giao diện còn dùng onclick="" nội tuyến; các chỉ thị dưới đây vẫn chặn nhúng/biểu mẫu ngoài.
    "Content-Security-Policy": "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
}


@app.on_event("startup")
def _startup() -> None:
    init_db()
    documents.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        documents.relink_uploads(conn)  # data chép từ máy khác: trỏ lại file trong data/uploads
        _backfill_history_labels(conn)
        documents.sync_ai_index(conn)  # dựng sẵn chỉ mục tìm kiếm cho trợ lý AI (lần đầu ~2 giây, sau đó chỉ cập nhật phần đổi)
        empty = conn.execute("SELECT COUNT(*) FROM units").fetchone()[0] == 0
    if empty:
        from .seed import seed
        seed()
    backup.start_scheduler()  # sao lưu database + file gốc định kỳ (xem backend/backup.py)
    memory.start_scheduler()  # trích ghi chú cá nhân từ các đoạn chat đã dừng (chỉ cho người dùng đã bật bộ nhớ)
    semantic.start_scheduler()  # vector tìm theo ý nghĩa cho tài liệu (chỉ khi có GEMINI_API_KEY)


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    request.state.user = auth.user_from_token(request.cookies.get(auth.SESSION_COOKIE))
    path = request.url.path
    if path.startswith("/api/") and path not in PUBLIC_API and not request.state.user:
        return JSONResponse({"detail": "Chưa đăng nhập"}, status_code=401)
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():  # setdefault: trang xem tài liệu tự đặt CSP chặt hơn thì giữ nguyên
        response.headers.setdefault(header, value)
    if not path.startswith("/api/"):  # giao diện: luôn hỏi lại server để nhận bản mới sau khi cập nhật code
        response.headers["Cache-Control"] = "no-cache"
    return response


def _log(conn, user: dict, action: str, entity: str, entity_id=None, detail=None, label=None, snapshot=None) -> int:
    cur = conn.execute("INSERT INTO audit_log (action, entity, entity_id, detail, user_id, label, snapshot) VALUES (?,?,?,?,?,?,?)",
                       (action, entity, entity_id, detail, user["id"], label,
                        json.dumps(snapshot, ensure_ascii=False, default=str) if snapshot is not None else None))
    return cur.lastrowid


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


def _cookie_secure(request: Request) -> bool:
    """Cookie phiên chỉ đi qua HTTPS khi site chạy HTTPS (kể cả sau tunnel/reverse proxy); đặt AZB_COOKIE_SECURE=1 để ép."""
    return (os.environ.get("AZB_COOKIE_SECURE") == "1" or request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https")


def _login_response(user_id: int, request: Request) -> JSONResponse:
    with connect() as conn:
        token = auth.create_session(conn, user_id)
        user = row(conn, "SELECT id, username, full_name, role, unit_id FROM users WHERE id = ?", (user_id,))
    resp = JSONResponse({"user": user})
    resp.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax", secure=_cookie_secure(request),
                    max_age=auth.SESSION_DAYS * 86400)
    return resp


@app.get("/api/auth/state")
def auth_state(request: Request):
    with connect() as conn:
        needs_setup = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    user = request.state.user
    if user:
        user = {**user, "can_use_ai": auth.can_use_ai(user), "edit_all": user["role"] in auth.EDIT_ALL_ROLES}
        with connect() as conn:
            if user["role"] == "admin":
                user["pending_requests"] = conn.execute("SELECT COUNT(*) FROM access_requests WHERE status = 'pending'").fetchone()[0]
                user["pending_links"] = conn.execute("SELECT COUNT(*) FROM link_requests WHERE status = 'pending'").fetchone()[0]
                user["pending_accounts"] = conn.execute("SELECT COUNT(*) FROM users WHERE pending_approval = 1").fetchone()[0]
            else:
                user["profile_notices"] = selfinfo.notice_count(conn, user["id"])  # kết quả duyệt mới mà user chưa xem
                user["pending_requests"] = conn.execute(
                    "SELECT COUNT(*) FROM access_requests WHERE user_id = ? AND seen_by_user = 0", (user["id"],)).fetchone()[0]
    return {"needs_setup": needs_setup, "user": user, "roles": auth.ROLES}


@app.post("/api/auth/setup")
def auth_setup(req: SetupRequest, request: Request):
    """Tạo tài khoản quản trị đầu tiên – chỉ dùng được khi chưa có tài khoản nào."""
    if len(req.password) < 8:
        raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
    with connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            raise HTTPException(403, "Hệ thống đã có tài khoản quản trị")
        cur = conn.execute("INSERT INTO users (username, full_name, role, password_hash) VALUES (?,?, 'admin', ?)",
                           (req.username.strip().lower(), req.full_name, auth.hash_password(req.password)))
    return _login_response(cur.lastrowid, request)


USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
REGISTER_MAX_PER_IP = 5      # số yêu cầu đăng ký tối đa của một địa chỉ trong REGISTER_WINDOW giây
REGISTER_WINDOW = 3600
REGISTER_MAX_PENDING = 100   # tổng tài khoản chờ duyệt tối đa, chặn gửi hàng loạt làm ngập danh sách của admin
_register_log: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()  # sau tunnel/reverse proxy
    return fwd or (request.client.host if request.client else "?")


class RegisterRequest(LoginRequest):
    full_name: str | None = None
    unit: str | None = None   # phòng ban / công trình: chọn từ gợi ý hoặc tự gõ nếu chưa có trong danh sách
    phone: str | None = None  # số máy lẻ nội bộ (không bắt buộc)


PHONE_RE = re.compile(r"^[0-9+][0-9 .-]{2,19}$")


@app.get("/api/auth/units")
def auth_units():
    """Tên đơn vị để gợi ý khi đăng ký: chỉ phòng / ban / công trình, chỉ trả tên và từ khoá tìm kiếm (mã, cách gọi thường ngày như HCNS, CNTT), không trả ID hay số liệu nội bộ."""
    with connect() as conn:
        return [{"name": r["name"], "full_name": r["full_name"] or None,
                 "keywords": f"{r['code']} {analytics.UNIT_ALIASES.get(r['code'], '')}".strip()} for r in conn.execute(
            "SELECT code, name, full_name FROM units WHERE unit_type IN ('department', 'committee', 'project') AND name != ''"
            " ORDER BY sort_order, id")]


@app.post("/api/auth/register")
def register(req: RegisterRequest, request: Request):
    """Người dùng tự đăng ký: tài khoản chờ admin duyệt (active = 0), vai trò viewer, chưa đăng nhập được."""
    username = req.username.strip().lower()
    full_name = (req.full_name or "").strip()
    unit = (req.unit or "").strip()
    phone = (req.phone or "").strip()
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "Tên đăng nhập gồm 3–32 ký tự: chữ không dấu, số, dấu chấm, gạch dưới hoặc gạch ngang")
    if not full_name:
        raise HTTPException(400, "Vui lòng nhập họ tên")
    if not unit:
        raise HTTPException(400, "Vui lòng chọn hoặc nhập phòng ban / công trình")
    if len(req.password) < 8:
        raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
    if len(full_name) > 100 or len(unit) > 100:
        raise HTTPException(400, "Họ tên và phòng ban tối đa 100 ký tự")
    if phone and not PHONE_RE.match(phone):
        raise HTTPException(400, "Số máy lẻ chỉ gồm chữ số, khoảng trắng, dấu cộng, chấm hoặc gạch ngang (3–20 ký tự)")
    now, ip = time.time(), _client_ip(request)
    recent = [t for t in _register_log.get(ip, []) if now - t < REGISTER_WINDOW]
    if len(recent) >= REGISTER_MAX_PER_IP:
        raise HTTPException(429, "Bạn đã gửi quá nhiều yêu cầu đăng ký, vui lòng thử lại sau")
    with connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            raise HTTPException(403, "Hệ thống chưa có quản trị viên, hãy tạo tài khoản quản trị trước")
        if conn.execute("SELECT COUNT(*) FROM users WHERE pending_approval = 1").fetchone()[0] >= REGISTER_MAX_PENDING:
            raise HTTPException(429, "Đang có quá nhiều yêu cầu chờ duyệt, vui lòng liên hệ quản trị viên")
        if row(conn, "SELECT id FROM users WHERE username = ?", (username,)):
            raise HTTPException(400, "Tên đăng nhập đã tồn tại")
        _register_log[ip] = recent + [now]
        conn.execute("INSERT INTO users (username, full_name, role, password_hash, active, pending_approval, register_unit, register_phone)"
                     " VALUES (?,?, 'viewer', ?, 0, 1, ?, ?)",
                     (username, full_name, auth.hash_password(req.password), unit, phone or None))
    return {"ok": True}


@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request):
    username = req.username.strip().lower()
    now = time.time()
    recent = _recent_fails(username, now)
    if len(recent) >= LOGIN_MAX_FAILS:
        wait = max(1, int(LOGIN_LOCK_SECONDS - (now - recent[0])))
        raise HTTPException(429, f"Sai mật khẩu quá nhiều lần, thử lại sau {wait // 60 + (1 if wait % 60 else 0)} phút")
    with connect() as conn:
        u = row(conn, "SELECT * FROM users WHERE username = ?", (username,))
    if not u or not auth.verify_password(req.password, u["password_hash"]):
        _failed_logins[username] = recent + [now]
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    if u["pending_approval"]:  # đúng mật khẩu mới báo, để không lộ tài khoản tồn tại
        raise HTTPException(403, "Tài khoản đang chờ quản trị viên duyệt")
    if not u["active"]:
        raise HTTPException(403, "Tài khoản đã bị khoá")
    _failed_logins.pop(username, None)
    return _login_response(u["id"], request)


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
    auth.require_roles(request, auth.EDIT_ALL_ROLES)
    with connect() as conn:
        out = rows(conn, "SELECT u.id, u.username, u.full_name, u.role, u.unit_id, x.name AS unit_name, u.active, u.created_at, u.pending_approval, u.register_note, u.register_unit, u.register_phone,"
                         " u.quota_mb, u.employee_id, e.full_name AS employee_name,"
                         " (SELECT COALESCE(SUM(size_bytes), 0) FROM documents d WHERE d.access_level = 'private'"
                         " AND d.owner_id = u.id) AS private_bytes"
                         " FROM users u LEFT JOIN units x ON x.id = u.unit_id LEFT JOIN employees e ON e.id = u.employee_id"
                         " ORDER BY u.username")
        perms = {}
        for r in conn.execute("SELECT user_id, feature FROM user_permissions"):
            perms.setdefault(r[0], []).append(r[1])
    for u in out:
        u["locked"] = _is_locked(u["username"])
        u["granted"] = perms.get(u["id"], [])
    return out


@app.get("/api/employee-links")
def employee_links(request: Request):
    """Admin: nhân sự để chọn khi gán cho tài khoản + gợi ý tự động theo họ tên (không kèm SĐT/email)."""
    auth.require_roles(request, {"admin"})
    with connect() as conn:
        return selfinfo.link_options(conn)


@app.put("/api/users/{user_id}/employee")
def set_user_employee(user_id: int, data: dict, request: Request):
    """Admin gán/gỡ hồ sơ nhân sự của tài khoản. data = {"employee_id": 12 | null}"""
    admin = auth.require_roles(request, {"admin"})
    try:
        employee_id = int(data["employee_id"]) if data.get("employee_id") else None
    except (TypeError, ValueError):
        raise HTTPException(400, "Mã nhân viên không hợp lệ") from None
    with connect() as conn:
        try:
            out = selfinfo.link(conn, user_id, employee_id)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        _log(conn, admin, "link_employee", "users", user_id, f"employee_id={employee_id}")
    return out


@app.get("/api/me/profile")
def my_profile(request: Request):
    """Hồ sơ nhân sự của chính tài khoản đăng nhập (kèm các yêu cầu sửa đã gửi)."""
    user = auth.current_user(request)
    with connect() as conn:
        return {"linked": bool(user.get("employee_id")), "profile": selfinfo.profile(conn, user.get("employee_id")),
                "fields": selfinfo.FIELDS, "requests": selfinfo.my_requests(conn, user["id"]),
                "link_request": None if user.get("employee_id") else selfinfo.my_link_request(conn, user["id"]),
                "link_notice": selfinfo.link_notice(conn, user["id"])}


@app.post("/api/me/profile/seen")
def my_profile_seen(request: Request):
    user = auth.current_user(request)
    with connect() as conn:
        selfinfo.mark_seen(conn, user["id"])
    return {"ok": True}


@app.get("/api/me/link-options")
def my_link_options(request: Request):
    """Danh sách nhân sự chưa gắn tài khoản để người dùng chọn hồ sơ của mình (chỉ tên/chức danh/đơn vị)."""
    user = auth.current_user(request)
    if user.get("employee_id"):
        return []
    with connect() as conn:
        return selfinfo.free_employees(conn)


@app.post("/api/me/link-request")
def submit_link_request(data: dict, request: Request):
    user = auth.current_user(request)
    with connect() as conn:
        try:
            out = selfinfo.submit_link(conn, user, data.get("employee_id"))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        _log(conn, user, "link_request", "users", user["id"], f"employee_id={data.get('employee_id')}")
    return out


@app.delete("/api/me/link-request/{req_id}")
def withdraw_link_request(req_id: int, request: Request):
    user = auth.current_user(request)
    with connect() as conn:
        try:
            selfinfo.withdraw_link(conn, user["id"], req_id)
        except ValueError as e:
            raise HTTPException(404, str(e)) from None
    return {"ok": True}


@app.get("/api/link-requests")
def link_requests(request: Request):
    auth.require_roles(request, {"admin"})
    with connect() as conn:
        return selfinfo.list_link_requests(conn)


@app.post("/api/link-requests/{req_id}/decide")
def decide_link_request(req_id: int, data: dict, request: Request):
    admin = auth.require_roles(request, {"admin"})
    with connect() as conn:
        try:
            out = selfinfo.decide_link(conn, admin, req_id, bool(data.get("approve")), str(data.get("note") or ""))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        _log(conn, admin, "link_request_decide", "link_requests", req_id, out["status"])
    return out


@app.post("/api/me/change-requests")
def submit_change_request(data: dict, request: Request):
    """Gửi yêu cầu sửa một thông tin trong hồ sơ của CHÍNH MÌNH; chưa ghi vào hồ sơ cho tới khi admin duyệt."""
    user = auth.current_user(request)
    with connect() as conn:
        try:
            out = selfinfo.submit(conn, user, str(data.get("field") or ""), data.get("value"), str(data.get("reason") or ""))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        _log(conn, user, "profile_change_request", "employees", user["employee_id"], str(data.get("field")))
    return out


@app.post("/api/me/profile/update")
def update_my_profile(data: dict, request: Request):
    """Cập nhật nhiều thông tin của chính mình một lần: SĐT/email/ngày sinh ghi thẳng, các trường khác chờ admin duyệt."""
    user = auth.current_user(request)
    with connect() as conn:
        try:
            out = selfinfo.submit_many(conn, user, data.get("values") or {}, str(data.get("reason") or ""))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        if out["pending"]:
            _log(conn, user, "profile_change_request", "employees", user["employee_id"], ",".join(out["pending"]))
    return out


@app.delete("/api/me/change-requests/{req_id}")
def withdraw_change_request(req_id: int, request: Request):
    user = auth.current_user(request)
    with connect() as conn:
        try:
            selfinfo.withdraw(conn, user["id"], req_id)
        except ValueError as e:
            raise HTTPException(404, str(e)) from None
    return {"ok": True}


@app.get("/api/employee-requests")
def employee_requests(request: Request, status: str = "pending"):
    auth.require_roles(request, {"admin"})
    with connect() as conn:
        return selfinfo.list_requests(conn, None if status == "all" else status)


@app.post("/api/employee-requests/{req_id}/decide")
def decide_employee_request(req_id: int, data: dict, request: Request):
    """Admin duyệt/từ chối yêu cầu sửa hồ sơ. data = {"approve": true, "note": "..."}"""
    admin = auth.require_roles(request, {"admin"})
    with connect() as conn:
        try:
            out = selfinfo.decide(conn, admin, req_id, bool(data.get("approve")), str(data.get("note") or ""))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        _log(conn, admin, "profile_change_decide", "employee_change_requests", req_id, out["status"])
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


@app.post("/api/users/{user_id}/approve")
def approve_user(user_id: int, data: dict, request: Request):
    """Admin duyệt tài khoản tự đăng ký: gán vai trò, đơn vị và quyền cấp thêm rồi mở khoá. Từ chối = xoá tài khoản."""
    admin = auth.require_roles(request, {"admin"})
    role = data.get("role")
    if role not in auth.ROLES:
        raise HTTPException(400, "Vai trò không hợp lệ")
    features = data.get("features") or []
    if not isinstance(features, list) or any(f not in auth.FEATURES for f in features):
        raise HTTPException(400, "Quyền không hợp lệ")
    unit_id = data.get("unit_id") or None
    with connect() as conn:
        u = row(conn, "SELECT id, username FROM users WHERE id = ? AND pending_approval = 1", (user_id,))
        if not u:
            raise HTTPException(400, "Tài khoản này không ở trạng thái chờ duyệt")
        conn.execute("UPDATE users SET role = ?, unit_id = ?, active = 1, pending_approval = 0, deactivated_at = NULL WHERE id = ?",
                     (role, unit_id, user_id))
        conn.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
        conn.executemany("INSERT INTO user_permissions (user_id, feature) VALUES (?,?)", [(user_id, f) for f in set(features)])
        _log(conn, admin, "approve", "users", user_id, f"{role}; {','.join(sorted(set(features)))}")
    return {"ok": True}


@app.post("/api/users")
def create_user(data: dict, request: Request):
    admin = auth.require_roles(request, {"admin"})
    if data.get("role") not in auth.ROLES:
        raise HTTPException(400, "Vai trò không hợp lệ")
    if len(data.get("password") or "") < 8:
        raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
    employee_id = data.get("employee_id") or None  # tuỳ chọn: bỏ qua thì người dùng tự xin liên kết sau
    with connect() as conn:
        if employee_id:
            if not row(conn, "SELECT id FROM employees WHERE id = ?", (employee_id,)):
                raise HTTPException(400, "Không tìm thấy nhân viên này trong danh sách nhân sự")
            other = row(conn, "SELECT username FROM users WHERE employee_id = ?", (employee_id,))
            if other:
                raise HTTPException(400, f"Hồ sơ này đã gắn với tài khoản {other['username']}")
        try:
            cur = conn.execute(
                "INSERT INTO users (username, full_name, role, unit_id, password_hash, employee_id) VALUES (?,?,?,?,?,?)",
                (data["username"].strip().lower(), data.get("full_name"), data["role"], data.get("unit_id") or None,
                 auth.hash_password(data["password"]), employee_id))
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
    fields = {k: data[k] for k in ("full_name", "role", "unit_id", "active", "quota_mb") if k in data}
    if "role" in fields and fields["role"] not in auth.ROLES:
        raise HTTPException(400, "Vai trò không hợp lệ")
    if "quota_mb" in fields:  # rỗng/0 = về hạn mức mặc định
        try:
            q = int(fields["quota_mb"] or 0)
        except (TypeError, ValueError):
            raise HTTPException(400, "Hạn mức phải là số MB") from None
        if not 0 <= q <= 100_000:
            raise HTTPException(400, "Hạn mức phải từ 1 đến 100000 MB")
        fields["quota_mb"] = q or None
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
        if "active" in fields:  # đồng hồ 90 ngày giữ dữ liệu khi nghỉ việc: bắt đầu lúc khoá, bỏ khi mở khoá lại
            conn.execute("UPDATE users SET deactivated_at = CASE WHEN active = 0 THEN COALESCE(deactivated_at, datetime('now','localtime'))"
                         " ELSE NULL END WHERE id = ?", (user_id,))
            if fields["active"] in (1, "1"):  # bật hoạt động cũng coi như duyệt tài khoản tự đăng ký
                conn.execute("UPDATE users SET pending_approval = 0 WHERE id = ?", (user_id,))
        _log(conn, admin, "update", "users", user_id)
    return {"ok": True}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, data: dict, request: Request):
    """Admin/ceo xoá hẳn một tài khoản đã khoá (gõ lại tên đăng nhập để xác nhận). Ghi nhật ký trước khi xoá."""
    actor = auth.require_roles(request, auth.EDIT_ALL_ROLES)
    with connect() as conn:
        result = offboarding.delete_account(conn, actor["id"], user_id, str(data.get("confirm") or ""))
        _log(conn, actor, "delete_user", "users", user_id, json.dumps(result, ensure_ascii=False))
    return {"ok": True, **result}


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


MAX_QUOTA_MB = 100000


def _request_payload(user: dict, data: dict) -> tuple[str, str | None, int | None]:
    features = data.get("features") or []
    if not isinstance(features, list) or any(f not in auth.FEATURES for f in features):
        raise HTTPException(400, "Quyền xin không hợp lệ")
    try:
        extra_mb = int(data.get("extra_mb") or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "Dung lượng xin thêm phải là số MB") from None
    if not 0 <= extra_mb <= MAX_QUOTA_MB:
        raise HTTPException(400, f"Dung lượng xin thêm phải từ 1 đến {MAX_QUOTA_MB} MB")
    if not features and not extra_mb:
        raise HTTPException(400, "Hãy chọn ít nhất một quyền hoặc nhập dung lượng cần xin thêm")
    features = [f for f in dict.fromkeys(features) if f not in user["permissions"]]
    if not features and not extra_mb:
        raise HTTPException(400, "Bạn đã có các quyền này rồi")
    reason = (data.get("reason") or "").strip()[:500]
    if not reason:
        raise HTTPException(400, "Vui lòng nhập lý do xin quyền")
    return ",".join(features), reason, extra_mb or None


@app.post("/api/access-requests")
def create_access_request(data: dict, request: Request):
    user = auth.current_user(request)
    if user["role"] in auth.EDIT_ALL_ROLES:
        raise HTTPException(400, "Tài khoản này đã có đủ quyền")
    features, reason, extra_mb = _request_payload(user, data)
    with connect() as conn:
        if conn.execute("SELECT 1 FROM access_requests WHERE user_id = ? AND status = 'pending'", (user["id"],)).fetchone():
            raise HTTPException(400, "Bạn đang có yêu cầu chờ duyệt. Hãy chỉnh sửa yêu cầu đó nếu muốn xin thêm quyền.")
        cur = conn.execute("INSERT INTO access_requests (user_id, features, reason, extra_mb) VALUES (?,?,?,?)",
                           (user["id"], features, reason, extra_mb))
        _log(conn, user, "request", "access_requests", cur.lastrowid, features + (f" +{extra_mb}MB" if extra_mb else ""))
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
    features, reason, extra_mb = _request_payload(user, data)
    with connect() as conn:
        _own_pending_request(conn, user, req_id)
        conn.execute("UPDATE access_requests SET features = ?, reason = ?, extra_mb = ?, updated_at = datetime('now','localtime') WHERE id = ?",
                     (features, reason, extra_mb, req_id))
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
        granted = None
        if approve:
            feats = [f for f in r["features"].split(",") if f in auth.FEATURES]
            conn.executemany("INSERT OR IGNORE INTO user_permissions (user_id, feature) VALUES (?,?)",
                             [(r["user_id"], f) for f in feats])
            if r["extra_mb"]:  # admin có thể chỉnh số MB cấp; mặc định cấp đúng số đã xin
                try:
                    granted = int(data.get("grant_mb") if data.get("grant_mb") not in (None, "") else r["extra_mb"])
                except (TypeError, ValueError):
                    raise HTTPException(400, "Số MB cấp phải là số") from None
                if not 1 <= granted <= MAX_QUOTA_MB:
                    raise HTTPException(400, f"Số MB cấp phải từ 1 đến {MAX_QUOTA_MB}")
                owner = row(conn, "SELECT id, role FROM users WHERE id = ?", (r["user_id"],))
                current = privatefiles.quota_mb(conn, owner)
                if current is not None:  # admin/ceo không giới hạn nên không cần nâng
                    conn.execute("UPDATE users SET quota_mb = ? WHERE id = ?", (min(current + granted, MAX_QUOTA_MB), r["user_id"]))
        conn.execute("UPDATE access_requests SET status = ?, decided_by = ?, decided_at = datetime('now','localtime'),"
                     " admin_note = ?, granted_mb = ?, seen_by_user = 0 WHERE id = ?",
                     ("approved" if approve else "rejected", admin["id"], note or None, granted, req_id))
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
        user = request.state.user
        doc_where, doc_params = access.doc_scope(conn, user)
        u["documents"] = [] if "docs_view" not in user["permissions"] else rows(
            conn, "SELECT d.id, d.title, d.code, d.version, d.doc_type, d.filename, d.extract_status, d.page_count,"
                  f" d.uploaded_at, d.access_level FROM documents d WHERE d.unit_id = ? AND {doc_where} ORDER BY d.code, d.title",
            [unit_id, *doc_params])
        tgt_units = access.target_units(conn, user)  # mục tiêu doanh thu/lợi nhuận: chỉ đơn vị mình quản lý
        if tgt_units is not None and unit_id not in tgt_units:
            u["targets"] = []
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
def list_targets(request: Request, unit_id: int | None = None):
    with connect() as conn:
        allowed = access.target_units(conn, request.state.user)  # None = xem tất cả
        if unit_id:
            if allowed is not None and unit_id not in allowed:
                return []
            return rows(conn, "SELECT * FROM targets WHERE unit_id = ? ORDER BY period DESC", (unit_id,))
        sql = "SELECT t.*, u.name AS unit_name FROM targets t LEFT JOIN units u ON u.id = t.unit_id"
        if allowed is not None:
            if not allowed:
                return []
            return rows(conn, sql + f" WHERE t.unit_id IN ({','.join('?' * len(allowed))}) ORDER BY t.period DESC, u.sort_order",
                        sorted(allowed))
        return rows(conn, sql + " ORDER BY t.period DESC, u.sort_order")


PROPOSAL_STATUS = {"new": "Mới", "approved": "Đã duyệt", "in_progress": "Đang thực hiện", "done": "Hoàn thành", "dropped": "Không thực hiện"}


class ProposalIn(BaseModel):
    title: str
    body: str = ""


class ProposalUpdate(BaseModel):
    status: str | None = None
    owner: str | None = None
    note: str | None = None


@app.get("/api/proposals")
def list_proposals(request: Request, status: str | None = None):
    """Đề xuất cải tiến. Ban TGĐ / quản trị xem tất cả; người khác chỉ xem đề xuất do mình tạo."""
    user = auth.require_ai(request)
    where, args = [], []
    if user["role"] not in auth.EDIT_ALL_ROLES:
        where.append("p.created_by = ?")
        args.append(user["id"])
    if status in PROPOSAL_STATUS:
        where.append("p.status = ?")
        args.append(status)
    sql = "SELECT p.*, u.full_name AS author FROM proposals p LEFT JOIN users u ON u.id = p.created_by"
    sql += (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY p.id DESC LIMIT 500"
    with connect() as conn:
        return rows(conn, sql, tuple(args))


@app.post("/api/proposals")
def create_proposal(req: ProposalIn, request: Request):
    user = auth.require_ai(request)
    title = req.title.strip()[:200]
    if not title:
        raise HTTPException(400, "Thiếu tiêu đề đề xuất")
    with connect() as conn:
        pid = conn.execute("INSERT INTO proposals (title, body, created_by) VALUES (?, ?, ?)",
                           (title, req.body.strip()[:8000], user["id"])).lastrowid
        _log(conn, user, "create", "proposals", pid)
        return row(conn, "SELECT * FROM proposals WHERE id = ?", (pid,))


@app.put("/api/proposals/{pid}")
def update_proposal(pid: int, req: ProposalUpdate, request: Request):
    user = auth.require_roles(request, auth.EDIT_ALL_ROLES)  # chỉ Ban TGĐ / quản trị đổi tiến trình
    fields = req.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] not in PROPOSAL_STATUS:
        raise HTTPException(400, "Trạng thái không hợp lệ")
    with connect() as conn:
        if not row(conn, "SELECT id FROM proposals WHERE id = ?", (pid,)):
            raise HTTPException(404, "Không tìm thấy đề xuất")
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE proposals SET {sets}, updated_at = datetime('now','localtime') WHERE id = ?",
                         (*[(v or None) if isinstance(v, str) else v for v in fields.values()], pid))
        _log(conn, user, "update", "proposals", pid, ",".join(fields) or None)
        return row(conn, "SELECT * FROM proposals WHERE id = ?", (pid,))


HISTORY_NAME_COL = {"units": "name", "employees": "full_name", "positions": "title", "processes": "name",
                    "targets": "COALESCE(metric_name, metric) || ' ' || period"}  # biểu thức cố định trong mã, không lấy từ người dùng


# Tên trường hiển thị trong lịch sử (dùng chung cho giao diện và file xuất)
FIELD_LABELS = {
    "code": "Mã", "name": "Tên", "full_name": "Họ tên / tên đầy đủ", "unit_type": "Loại đơn vị", "parent_id": "Trực thuộc",
    "color_group": "Nhóm màu", "functions": "Chức năng", "notes": "Ghi chú", "verified": "Đã xác nhận", "sort_order": "Thứ tự",
    "employee_code": "Mã NV", "display_name": "Tên hiển thị", "email": "Email", "phone": "Số điện thoại",
    "joined_date": "Ngày vào", "status": "Trạng thái", "job_title": "Chức danh", "grade": "Ngạch", "labor_group": "Nhóm lao động",
    "unit_id": "Đơn vị", "hr_department": "Phòng ban (HCNS)", "hr_division": "Khối (HCNS)", "birth_date": "Ngày sinh",
    "contract_term": "Loại hợp đồng", "title": "Chức danh", "title_code": "Mã chức danh", "employee_id": "Nhân sự",
    "is_head": "Là trưởng đơn vị", "headcount": "Định biên", "version": "Phiên bản", "iso_clause": "Điều khoản ISO",
    "owner": "Người phụ trách", "related_units": "Đơn vị liên quan", "purpose": "Mục đích", "content": "Nội dung",
    "effective_date": "Ngày hiệu lực", "period": "Kỳ", "metric": "Chỉ tiêu (mã)", "metric_name": "Chỉ tiêu",
    "target_value": "Mục tiêu", "actual_value": "Thực tế", "unit_label": "Đơn vị tính",
}
HISTORY_MASK = "(đã ẩn)"
# Hoàn tác thêm/xoá chỉ cho các bảng không kéo theo dữ liệu con (xoá đơn vị/nhân sự có thể làm mất liên kết)
UNDO_STRUCTURAL = {"targets", "processes", "positions"}


def _history_filter(entity, action, user_id, q, date_from, date_to) -> tuple[str, list]:
    tables = [entity] if entity in WRITABLE else list(WRITABLE)
    actions = [action] if action in ("create", "update", "delete") else ["create", "update", "delete"]
    where = [f"l.action IN ({','.join('?' * len(actions))})", f"l.entity IN ({','.join('?' * len(tables))})"]
    params: list = [*actions, *tables]
    if user_id:
        where.append("l.user_id = ?")
        params.append(user_id)
    if q and q.strip():
        where.append("l.label LIKE ? ESCAPE '\\'")
        params.append("%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if date_from:
        where.append("date(l.ts) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(l.ts) <= date(?)")
        params.append(date_to)
    return " AND ".join(where), params


def _can_undo(log: dict) -> bool:
    if log["reverted_by"] or not log["has_snapshot"]:
        return False
    return log["action"] == "update" or log["entity"] in UNDO_STRUCTURAL


def _history_page(conn, where: str, params: list, limit: int, offset: int) -> dict:
    total = conn.execute(f"SELECT COUNT(*) FROM audit_log l WHERE {where}", params).fetchone()[0]
    logs = rows(conn, "SELECT l.id, l.ts, l.action, l.entity, l.entity_id, l.detail, l.label AS name, l.reverted_by,"
                       " l.snapshot IS NOT NULL AS has_snapshot, u.full_name AS user_name, u.username, l.user_id"
                       " FROM audit_log l LEFT JOIN users u ON u.id = l.user_id"
                       f" WHERE {where} ORDER BY l.id DESC LIMIT ? OFFSET ?", (*params, limit, max(0, offset)))
    ref_ids = {"units": set(), "employees": set()}
    for log in logs:
        detail = log.pop("detail")
        try:
            changes = json.loads(detail) if detail and detail.startswith("{") else None
        except ValueError:
            changes = None
        if changes is not None:  # bản ghi cũ có thể chứa trường "đổi" từ 22 sang '22': bỏ đi cho gọn
            changes = {k: v for k, v in changes.items() if v[0] == HISTORY_MASK or not _same(v[0], v[1])}
            for k, (old, new) in changes.items():
                bucket = "units" if k in ("unit_id", "parent_id") else "employees" if k == "employee_id" else None
                if bucket:
                    ref_ids[bucket].update(int(x) for x in (old, new) if str(x).isdigit())
        log["changes"] = changes
        log["note"] = None if changes is not None else detail
        log["can_undo"] = _can_undo(log)
        log["undone"] = bool(log["reverted_by"])
        log.pop("has_snapshot")
        log.pop("reverted_by")
    refs = {}
    for bucket, col in (("units", "name"), ("employees", "full_name")):
        ids = sorted(ref_ids[bucket])
        refs[bucket] = {r["id"]: r["n"] for r in rows(conn, f"SELECT id, {col} AS n FROM {bucket}"
                                                           f" WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
    return {"items": logs, "total": total, "refs": refs, "fields": FIELD_LABELS}


@app.get("/api/change-history")
def change_history(request: Request, limit: int = 200, entity: str | None = None):
    """Ai đã sửa/thêm/xoá gì trong sơ đồ, nhân sự, quy trình, mục tiêu; sửa từ giá trị nào sang giá trị nào (Ban TGĐ / quản trị)."""
    auth.require_roles(request, auth.EDIT_ALL_ROLES)
    where, params = _history_filter(entity, None, None, None, None, None)
    with connect() as conn:
        return _history_page(conn, where, params, max(1, min(limit, 1000)), 0)["items"]


@app.get("/api/change-history/page")
def change_history_page(request: Request, limit: int = 50, offset: int = 0, entity: str | None = None, action: str | None = None,
                        user_id: int | None = None, q: str | None = None, date_from: str | None = None, date_to: str | None = None):
    """Như /api/change-history nhưng có lọc (loại, thao tác, người, ngày, tên), phân trang và tổng số dòng."""
    auth.require_roles(request, auth.EDIT_ALL_ROLES)
    where, params = _history_filter(entity, action, user_id, q, date_from, date_to)
    with connect() as conn:
        out = _history_page(conn, where, params, max(1, min(limit, 200)), offset)
        out["users"] = rows(conn, "SELECT DISTINCT u.id, COALESCE(u.full_name, u.username) AS name FROM audit_log l"
                                  " JOIN users u ON u.id = l.user_id WHERE l.action IN ('create','update','delete')"
                                  f" AND l.entity IN ({','.join('?' * len(WRITABLE))}) ORDER BY name", list(WRITABLE))
    return out


@app.get("/api/change-history/export")
def change_history_export(request: Request, entity: str | None = None, action: str | None = None, user_id: int | None = None,
                          q: str | None = None, date_from: str | None = None, date_to: str | None = None):
    """File Excel của lịch sử theo đúng bộ lọc đang chọn, tối đa 20.000 dòng."""
    auth.require_roles(request, auth.EDIT_ALL_ROLES)
    where, params = _history_filter(entity, action, user_id, q, date_from, date_to)
    with connect() as conn:
        page = _history_page(conn, where, params, 20000, 0)
    ACT = {"create": "Thêm mới", "update": "Sửa", "delete": "Xoá"}
    TBL = {"units": "Đơn vị", "employees": "Nhân sự", "positions": "Chức danh", "processes": "Quy trình", "targets": "Mục tiêu"}

    def show(field, v):
        if v is None or v == "":
            return "—"
        if field in ("unit_id", "parent_id") and str(v).isdigit():
            return page["refs"]["units"].get(int(v), f"#{v}")
        if field == "employee_id" and str(v).isdigit():
            return page["refs"]["employees"].get(int(v), f"#{v}")
        return str(v)

    lines = []
    for l in page["items"]:
        diff = "; ".join(f"{FIELD_LABELS.get(k, k)}: {show(k, a)} → {show(k, b)}" for k, (a, b) in (l["changes"] or {}).items())
        lines.append([l["ts"], l["user_name"] or l["username"] or "", ACT.get(l["action"], l["action"]), TBL.get(l["entity"], l["entity"]),
                      l["name"] or f"#{l['entity_id']}", diff or (l["note"] or ""), "có" if l["undone"] else ""])
    name = f"AZB_lich_su_thay_doi_{time.strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(export.history_xlsx(lines), media_type=export.MIME["xlsx"],
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store",
                             "X-Content-Type-Options": "nosniff"})


class HistoryCleanup(BaseModel):
    snapshot_days: int = auditlog.DEFAULT_SNAPSHOT_DAYS
    archive_days: int = auditlog.DEFAULT_ARCHIVE_DAYS


@app.get("/api/change-history/cleanup-preview")
def change_history_cleanup_preview(request: Request, snapshot_days: int = auditlog.DEFAULT_SNAPSHOT_DAYS,
                                   archive_days: int = auditlog.DEFAULT_ARCHIVE_DAYS):
    """Xem trước việc dọn nhật ký: bao nhiêu ảnh chụp hoàn tác và dòng cũ sẽ bị ảnh hưởng (chỉ quản trị)."""
    auth.require_roles(request, {"admin"})
    try:
        with connect() as conn:
            return auditlog.preview(conn, snapshot_days, archive_days)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/change-history/cleanup")
def change_history_cleanup(body: HistoryCleanup, request: Request):
    """Dọn nhật ký theo tầng: bỏ ảnh chụp hoàn tác quá hạn; dòng quá hạn lưu trữ ra Excel rồi mới xoá (chỉ quản trị)."""
    user = auth.require_roles(request, {"admin"})
    try:
        return auditlog.cleanup(body.snapshot_days, body.archive_days, user["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/change-history/{log_id}/undo")
def change_history_undo(log_id: int, request: Request):
    """Hoàn tác một thay đổi (sửa → trả giá trị cũ; thêm → xoá; xoá → khôi phục). Việc hoàn tác được ghi thành một dòng mới."""
    import sqlite3
    user = auth.require_roles(request, auth.EDIT_ALL_ROLES)
    with connect() as conn:
        log = row(conn, "SELECT * FROM audit_log WHERE id = ?", (log_id,))
        if not log or log["action"] not in ("create", "update", "delete") or log["entity"] not in WRITABLE:
            raise HTTPException(404, "Không tìm thấy thay đổi")
        table, item_id = log["entity"], log["entity_id"]
        if log["reverted_by"]:
            raise HTTPException(409, "Thay đổi này đã được hoàn tác")
        if not log["snapshot"] or not (log["action"] == "update" or table in UNDO_STRUCTURAL):
            raise HTTPException(400, "Thay đổi này không hoàn tác được")
        snap = json.loads(log["snapshot"])
        current = row(conn, f"SELECT * FROM {table} WHERE id = ?", (item_id,))
        label = log["label"]
        try:
            if log["action"] == "update":
                if not current:
                    raise HTTPException(409, "Đối tượng không còn tồn tại")
                if any(not _same(current.get(k), v) for k, v in snap["new"].items()):
                    raise HTTPException(409, "Dữ liệu đã được sửa tiếp sau thay đổi này nên không thể hoàn tác an toàn")
                _check_write(conn, user, table, current, snap["old"])
                sets = ", ".join(f"{k} = ?" for k in snap["old"])
                if table in TOUCH_UPDATED:
                    sets += ", updated_at = datetime('now','localtime')"
                conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*snap["old"].values(), item_id))
                new_id = _log(conn, user, "update", table, item_id, _change_detail(current, snap["old"]),
                              label=_entity_label(conn, table, item_id), snapshot={"old": {k: current.get(k) for k in snap["old"]}, "new": snap["old"]})
            elif log["action"] == "create":
                if not current:
                    raise HTTPException(409, "Đối tượng không còn tồn tại")
                _check_write(conn, user, table, current, {})
                conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
                new_id = _log(conn, user, "delete", table, item_id, label=label, snapshot=current)
            else:  # delete → khôi phục đúng dòng cũ (giữ nguyên mã số)
                if current:
                    raise HTTPException(409, "Đối tượng đã tồn tại")
                columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                data = {k: v for k, v in snap.items() if k in columns}
                _check_write(conn, user, table, None, data)
                conn.execute(f"INSERT INTO {table} ({', '.join(data)}) VALUES ({', '.join('?' * len(data))})", tuple(data.values()))
                new_id = _log(conn, user, "create", table, item_id, label=_entity_label(conn, table, item_id) or label, snapshot=data)
        except sqlite3.IntegrityError as e:
            raise HTTPException(409, f"Không hoàn tác được vì dữ liệu liên quan đã thay đổi ({e})")
        conn.execute("UPDATE audit_log SET reverted_by = ? WHERE id = ?", (new_id, log_id))
    return {"ok": True, "log_id": new_id}


@app.get("/api/targets/progress")
def targets_progress(request: Request, period: str | None = None):
    """Tiến độ mục tiêu một kỳ (mặc định kỳ mới nhất). Chỉ gồm mục tiêu người xem được phép thấy."""
    return analytics.target_progress(list_targets(request), period)


@app.get("/api/targets/export")
def targets_export(request: Request, period: str | None = None):
    """File Excel tiến độ mục tiêu một kỳ, cùng phạm vi quyền xem với trang Mục tiêu doanh thu."""
    data = analytics.target_progress(list_targets(request), period)
    name = f"AZB_muc_tieu_{export._slug(data['period'] or 'trong')}.xlsx"
    return Response(export.targets_xlsx(data), media_type=export.MIME["xlsx"],
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store",
                             "X-Content-Type-Options": "nosniff"})


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
        created = row(conn, f"SELECT * FROM {table} WHERE id = ?", (cur.lastrowid,))
        _log(conn, user, "create", table, cur.lastrowid, label=_entity_label(conn, table, cur.lastrowid), snapshot=created)
        return created


# Trường thông tin cá nhân: lịch sử chỉ ghi TÊN trường đã đổi, không ghi giá trị cũ/mới
SENSITIVE_FIELDS = {"birth_date", "email", "phone", "contract_term", "notes", "employee_code"}


def _same(a, b) -> bool:
    """Hai giá trị coi như nhau: '' = rỗng, 22 = '22', 5 = 5.0 (form gửi chuỗi, DB lưu số)."""
    if a in (None, "") and b in (None, ""):
        return True
    if a == b:
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def _changed_fields(before: dict, after: dict) -> dict:
    return {k: new for k, new in after.items() if not _same(before.get(k), new)}


def _change_detail(before: dict, after: dict) -> str | None:
    """Chuỗi JSON {trường: [cũ, mới]} cho các trường thực sự đổi; None nếu không đổi gì."""
    changes = {k: ["(đã ẩn)", "(đã ẩn)"] if k in SENSITIVE_FIELDS else [before.get(k), new]
               for k, new in _changed_fields(before, after).items()}
    return json.dumps(changes, ensure_ascii=False, default=str) if changes else None


def _entity_label(conn, table: str, item_id) -> str | None:
    col = HISTORY_NAME_COL.get(table)
    r = row(conn, f"SELECT {col} AS n FROM {table} WHERE id = ?", (item_id,)) if col and item_id is not None else None
    return r["n"] if r else None


def _backfill_history_labels(conn) -> None:
    """Bản ghi cũ chưa có tên: điền tên hiện tại của đối tượng nếu nó còn tồn tại."""
    for table in WRITABLE:
        col = HISTORY_NAME_COL[table]
        conn.execute(f"UPDATE audit_log SET label = (SELECT {col} FROM {table} t WHERE t.id = audit_log.entity_id)"
                     " WHERE label IS NULL AND entity = ? AND entity_id IS NOT NULL", (table,))


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
        changed = _changed_fields(existing, data)
        if changed:  # không đổi gì thì không ghi lịch sử
            _log(conn, user, "update", table, item_id, _change_detail(existing, data), label=_entity_label(conn, table, item_id),
                 snapshot={"old": {k: existing.get(k) for k in changed}, "new": changed})
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
        label = _entity_label(conn, table, item_id)
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        _log(conn, user, "delete", table, item_id, label=label, snapshot=existing)
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
    user = auth.current_user(request)
    sql = ("SELECT d.id, d.unit_id, u.name AS unit_name, d.process_id, d.title, d.doc_type, d.code, d.version, d.filename,"
           " d.size_bytes, d.page_count, d.char_count, d.extract_status, d.extract_note, d.uploaded_at, d.access_level,"
           " (SELECT COUNT(*) FROM doc_page_review r WHERE r.doc_id = d.id) AS reviewed_pages,"
           " (d.extract_status = 'ok' AND d.extract_note IS NOT NULL AND LOWER(d.stored_path) LIKE '%.pdf' AND d.doc_type != 'website') AS ai_read,"
           # Người tải lên chỉ trả về cho file chưa đọc. Tên và đơn vị lấy từ hồ sơ nhân sự đã liên kết (nếu có) để phân biệt người trùng tên.
           " CASE WHEN d.extract_status IN ('failed', 'needs_ocr') THEN COALESCE(ue.full_name, uu.full_name, uu.username, '—') END AS uploader_name,"
           " CASE WHEN d.extract_status IN ('failed', 'needs_ocr') THEN ue.id END AS uploader_employee_id,"
           " CASE WHEN d.extract_status IN ('failed', 'needs_ocr') THEN uun.name END AS uploader_unit"
           " FROM documents d LEFT JOIN units u ON u.id = d.unit_id LEFT JOIN users uu ON uu.id = d.uploaded_by"
           " LEFT JOIN employees ue ON ue.id = uu.employee_id LEFT JOIN units uun ON uun.id = ue.unit_id")
    with connect() as conn:
        where, params = access.doc_scope(conn, user)
        where += " AND d.access_level != 'private'"  # file đính kèm chat nằm ở kho riêng, không lẫn vào thư viện
        if unit_id:
            docs = rows(conn, sql + f" WHERE {where} AND d.unit_id = ? ORDER BY d.code, d.title", [*params, unit_id])
        else:
            docs = rows(conn, sql + f" WHERE {where} ORDER BY d.uploaded_at DESC", params)
        can_review = documents.reviewable_ids(conn)
        for d in docs:
            d["can_review"] = d["id"] in can_review
        return docs


@app.get("/api/documents/meta")
def documents_meta(request: Request):
    user = auth.require_permission(request, "docs_view")
    return {"types": documents.DOC_TYPES, "allowed_ext": sorted(documents.ALLOWED_EXT),
            "max_mb": documents.MAX_UPLOAD_BYTES // (1024 * 1024), "ocr_available": ai.has_anthropic(),
            "levels": [[k, access.LEVELS[k]] for k in access.settable_levels(user)], "default_level": access.DEFAULT_LEVEL}


@app.get("/api/documents/search")
def search_documents(request: Request, q: str, unit_id: int | None = None, content: bool = False):
    user = auth.require_permission(request, "docs_view")
    with connect() as conn:
        return documents.search_docs(conn, q, limit=30, unit_id=unit_id, in_content=content,
                                     allowed_ids=access.visible_doc_ids(conn, user, include_private=False))


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
    access_level: str = Form(access.DEFAULT_LEVEL),
):
    user = auth.require_permission(request, "docs_edit")
    access.check_level(user, access_level)
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
            "INSERT INTO documents (unit_id, title, doc_type, code, version, filename, stored_path, mime, size_bytes, uploaded_by,"
            " access_level) VALUES (?,?,?,?,?,?,'',?,?,?,?)",
            (unit_id, title.strip() or Path(file.filename).stem, doc_type if doc_type in documents.DOC_TYPES else "khac",
             code.strip() or None, version.strip() or None, file.filename, file.content_type, len(data), user["id"],
             access_level))
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
    user = auth.require_permission(request, "docs_view")
    with connect() as conn:
        d = row(conn, "SELECT d.*, u.name AS unit_name FROM documents d LEFT JOIN units u ON u.id = d.unit_id WHERE d.id = ?",
                (doc_id,))
        if d and not access.can_view_doc(conn, user, doc_id):
            d = None  # không thấy = báo không tìm thấy (không lộ tài liệu có tồn tại hay không)
        if d and "docs_edit" in user["permissions"] and d["uploaded_by"]:
            # Người đăng chỉ trả về cho người sửa được tài liệu (form Sửa); tên và đơn vị lấy từ hồ sơ nhân sự như danh sách
            d.update(row(conn, "SELECT uu.employee_id AS uploader_employee_id, COALESCE(ue.full_name, uu.full_name, uu.username) AS uploader_name,"
                               " uun.name AS uploader_unit FROM users uu LEFT JOIN employees ue ON ue.id = uu.employee_id"
                               " LEFT JOIN units uun ON uun.id = ue.unit_id WHERE uu.id = ?", (d["uploaded_by"],)) or {})
    if not d:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    d.pop("stored_path")
    return d


@app.get("/api/documents/{doc_id}/file")
def download_document(doc_id: int, request: Request, inline: bool = False):
    user = auth.require_permission(request, "docs_view")
    if not inline:  # xem trực tiếp trên web chỉ cần docs_view; tải file về máy cần quyền riêng
        auth.require_permission(request, "docs_download")
    with connect() as conn:
        d = row(conn, "SELECT filename, title, stored_path, mime, content FROM documents WHERE id = ?", (doc_id,))
        if d and not access.can_view_doc(conn, user, doc_id):
            d = None
    if not d or not Path(d["stored_path"]).exists():
        raise HTTPException(404, "Không tìm thấy file")
    path = Path(d["stored_path"])
    mime = d["mime"] or "application/octet-stream"
    if inline:
        # Chỉ cho xem trực tiếp các định dạng trình duyệt tự hiển thị an toàn (không chạy script)
        ext = path.suffix.lower()
        mime = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".txt": "text/plain; charset=utf-8", **documents.AUDIO_MIME, **documents.IMAGE_MIME}.get(ext)
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


# ---------- Đối chiếu văn bản AI đọc với bản gốc (từng trang) ----------
def _review_pdf(conn, user, doc_id: int, write: bool = False) -> tuple[dict, Path]:
    d = access.check_doc_write(conn, user, doc_id) if write else None
    if d is None:
        if not access.can_view_doc(conn, user, doc_id):
            raise HTTPException(404, "Không tìm thấy tài liệu")
    d = row(conn, "SELECT id, title, stored_path, filename, content, page_count, extract_status, unit_id FROM documents WHERE id = ?",
            (doc_id,))
    path = Path(d["stored_path"] or "")
    if not d["content"] or not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(400, "Chỉ đối chiếu được PDF đã đọc xong và còn file gốc")
    return d, path


@app.get("/api/documents/{doc_id}/review")
def review_pages(doc_id: int, request: Request):
    user = auth.require_permission(request, "docs_view")
    import pymupdf
    from . import verify_scan
    with connect() as conn:
        d, path = _review_pdf(conn, user, doc_id)
        pages = documents.split_pages(d["content"], d["page_count"])
        done = {r["page_no"]: r["status"] for r in rows(conn, "SELECT page_no, status FROM doc_page_review WHERE doc_id = ?", (doc_id,))}
    if not pages:  # văn bản thiếu đánh dấu trang: đối chiếu cả file, một ô chữ duy nhất
        with pymupdf.open(path) as pdf:
            total = len(pdf)
        return {"id": doc_id, "title": d["title"], "total": total, "reviewed": len(done), "whole": True,
                "text": d["content"], "status": ("edited" if "edited" in done.values() else "verified") if len(done) >= total else None}
    with pymupdf.open(path) as pdf:
        total = len(pdf)
        try:
            flags = verify_scan.free_checks({"lang_vi": True}, pdf, pages)
        except Exception:
            flags = {}
    return {"id": doc_id, "title": d["title"], "total": total, "reviewed": len(done),
            "pages": [{"page": n, "text": pages.get(n, ""), "status": done.get(n), "flags": flags.get(n, [])}
                      for n in range(1, total + 1)]}


@app.get("/api/documents/{doc_id}/page/{page_no}.png")
def review_page_image(doc_id: int, page_no: int, request: Request):
    user = auth.require_permission(request, "docs_view")
    import pymupdf
    with connect() as conn:
        d, path = _review_pdf(conn, user, doc_id)
    with pymupdf.open(path) as pdf:
        if not 1 <= page_no <= len(pdf):
            raise HTTPException(404, "Không có trang này")
        png = pdf[page_no - 1].get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8)).tobytes("png")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


@app.put("/api/documents/{doc_id}/review")
def review_save_whole(doc_id: int, data: dict, request: Request):
    """Đối chiếu cả file (văn bản không có đánh dấu trang): xác nhận đúng (không gửi text) hoặc gửi bản đã sửa."""
    user = auth.require_permission(request, "docs_edit")
    text = data.get("text")
    if text is not None and not isinstance(text, str):
        raise HTTPException(400, "Nội dung không hợp lệ")
    with connect() as conn:
        d, _ = _review_pdf(conn, user, doc_id, write=True)
        auth.check_unit_write(conn, user, d["unit_id"])
        if documents.split_pages(d["content"], d["page_count"]):
            raise HTTPException(400, "Tài liệu này đã có đánh dấu trang, hãy đối chiếu từng trang")
        status = documents.save_whole_review(conn, doc_id, user["id"], text)
        _log(conn, user, "review", "documents", doc_id, f"cả file: {status}")
    return {"ok": True, "status": status}


@app.delete("/api/documents/{doc_id}/review")
def review_undo_whole(doc_id: int, request: Request):
    """Bỏ dấu đã đối chiếu của cả file. Chữ đã sửa trước đó vẫn giữ nguyên."""
    user = auth.require_permission(request, "docs_edit")
    with connect() as conn:
        d, _ = _review_pdf(conn, user, doc_id, write=True)
        auth.check_unit_write(conn, user, d["unit_id"])
        conn.execute("DELETE FROM doc_page_review WHERE doc_id = ?", (doc_id,))
        _log(conn, user, "review_undo", "documents", doc_id, "cả file")
    return {"ok": True}


@app.put("/api/documents/{doc_id}/review/{page_no}")
def review_save(doc_id: int, page_no: int, data: dict, request: Request):
    """Người duyệt xác nhận trang đúng (không gửi text) hoặc gửi bản đã sửa."""
    user = auth.require_permission(request, "docs_edit")
    text = data.get("text")
    if text is not None and not isinstance(text, str):
        raise HTTPException(400, "Nội dung không hợp lệ")
    with connect() as conn:
        d, _ = _review_pdf(conn, user, doc_id, write=True)
        auth.check_unit_write(conn, user, d["unit_id"])
        try:
            status = documents.save_page_review(conn, doc_id, page_no, user["id"], text)
        except ValueError as e:
            raise HTTPException(400, str(e))
        _log(conn, user, "review", "documents", doc_id, f"trang {page_no}: {status}")
    return {"ok": True, "status": status}


@app.delete("/api/documents/{doc_id}/review/{page_no}")
def review_undo(doc_id: int, page_no: int, request: Request):
    """Bỏ dấu đã đối chiếu của một trang (về 'chưa xem'). Chữ đã sửa trước đó vẫn giữ nguyên."""
    user = auth.require_permission(request, "docs_edit")
    with connect() as conn:
        d, _ = _review_pdf(conn, user, doc_id, write=True)
        auth.check_unit_write(conn, user, d["unit_id"])
        conn.execute("DELETE FROM doc_page_review WHERE doc_id = ? AND page_no = ?", (doc_id, page_no))
        _log(conn, user, "review_undo", "documents", doc_id, f"trang {page_no}")
    return {"ok": True}


@app.put("/api/documents/{doc_id}")
def update_document(doc_id: int, data: dict, request: Request):
    user = auth.require_permission(request, "docs_edit")
    fields = {k: (data[k] or None) for k in ("title", "doc_type", "code", "version", "unit_id", "process_id") if k in data}
    if "access_level" in data:
        fields["access_level"] = access.check_level(user, str(data["access_level"]))
    with connect() as conn:
        d = access.check_doc_write(conn, user, doc_id)
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
        d = access.check_doc_write(conn, user, doc_id)
        auth.check_unit_write(conn, user, d["unit_id"])
        conn.execute("UPDATE documents SET extract_status = 'pending' WHERE id = ?", (doc_id,))
    background.add_task(documents.process_document, doc_id)
    return {"ok": True}


@app.post("/api/documents/reprocess-unread")
def reprocess_unread(request: Request, background: BackgroundTasks, include_ocr: bool = False):
    user = auth.require_permission(request, "docs_edit")
    with connect() as conn:
        queue = documents.reprocess_candidates(conn, user, include_ocr)
        conn.executemany("UPDATE documents SET extract_status = 'pending' WHERE id = ?", [(doc_id,) for doc_id, _ in queue])
    if queue:
        background.add_task(documents.reprocess_many, queue)
    return {"queued": len(queue)}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, request: Request):
    user = auth.require_permission(request, "docs_delete")
    with connect() as conn:
        d = access.check_doc_write(conn, user, doc_id)
        auth.check_unit_write(conn, user, d["unit_id"])
        conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        _log(conn, user, "delete", "documents", doc_id, d["stored_path"])
    src = Path(d["stored_path"])
    if src.exists():  # không xoá hẳn: chuyển vào thùng rác để lấy lại được nếu lỡ tay
        trash = documents.UPLOAD_DIR / "_trash"
        trash.mkdir(exist_ok=True)
        shutil.move(str(src), str(trash / src.name))
    return {"ok": True}


# ---------- Kho riêng theo tài khoản (file đính kèm chat) ----------
def _private_row(conn, user: dict, doc_id: int) -> dict:
    """File riêng của user (hoặc của người khác nếu user là admin/ceo – ghi nhật ký ẩn để truy vết)."""
    d = privatefiles.get_file(conn, user, doc_id)
    if d["owner_id"] != user["id"]:
        _log(conn, user, "view_private", "documents", doc_id, f"chủ file: {d['owner_username'] or d['owner_id']}")
    return d


@app.get("/api/my-files/meta")
def my_files_meta(request: Request):
    user = auth.require_ai(request)
    with connect() as conn:
        return {"allowed_ext": sorted(documents.ALLOWED_EXT), "max_mb": documents.MAX_UPLOAD_BYTES // (1024 * 1024),
                "ocr_available": ai.has_anthropic(), "ocr_daily_limit": privatefiles.OCR_DAILY_LIMIT,
                "usage": privatefiles.usage(conn, user)}


@app.get("/api/my-files")
def list_my_files(request: Request):
    user = auth.require_ai(request)
    with connect() as conn:
        files = rows(conn, "SELECT id, title, filename, size_bytes, page_count, char_count, extract_status, extract_note, uploaded_at"
                           " FROM documents WHERE access_level = 'private' AND owner_id = ? ORDER BY uploaded_at DESC, id DESC",
                     (user["id"],))
        return {"files": files, "usage": privatefiles.usage(conn, user)}


@app.post("/api/my-files")
async def upload_my_file(request: Request, background: BackgroundTasks, file: UploadFile = File(...)):
    user = auth.require_ai(request)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in documents.ALLOWED_EXT:
        raise HTTPException(400, f"Chỉ nhận các định dạng: {', '.join(sorted(documents.ALLOWED_EXT))}")
    data = await file.read()
    if len(data) > documents.MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File vượt quá 50 MB")
    with connect() as conn:
        privatefiles.check_quota(conn, user, len(data))
        cur = conn.execute(
            "INSERT INTO documents (unit_id, title, doc_type, filename, stored_path, mime, size_bytes, uploaded_by, access_level,"
            " owner_id) VALUES (NULL,?,'khac',?,'',?,?,?,'private',?)",
            (Path(file.filename).stem, file.filename, file.content_type, len(data), user["id"], user["id"]))
        doc_id = cur.lastrowid
        path = documents.UPLOAD_DIR / f"{doc_id}_{documents.safe_filename(file.filename)}"
        path.write_bytes(data)
        conn.execute("UPDATE documents SET stored_path = ? WHERE id = ?", (str(path), doc_id))
        _log(conn, user, "upload_private", "documents", doc_id, file.filename)
    # Ảnh/scan/ghi âm chỉ được đọc bằng AI khi người dùng gửi câu hỏi hoặc bấm "Đọc"; file có sẵn chữ thì đọc ngay (miễn phí)
    background.add_task(documents.process_document, doc_id, False)
    return {"id": doc_id, "status": "pending"}


@app.get("/api/my-files/{doc_id}")
def get_my_file(doc_id: int, request: Request):
    user = auth.current_user(request)
    with connect() as conn:
        d = _private_row(conn, user, doc_id)
    d.pop("stored_path", None)
    return d


@app.get("/api/my-files/{doc_id}/file")
def download_my_file(doc_id: int, request: Request, inline: bool = False):
    user = auth.current_user(request)
    with connect() as conn:
        d = _private_row(conn, user, doc_id)
    path = Path(d["stored_path"])
    if not path.is_file():
        raise HTTPException(404, "Không tìm thấy file")
    if inline and path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".pdf", ".txt"):
        mime = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8", **documents.IMAGE_MIME}[path.suffix.lower()]
        return FileResponse(path, media_type=mime, headers={"Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff"})
    return FileResponse(path, filename=d["filename"], media_type=d["mime"] or "application/octet-stream")


@app.post("/api/my-files/{doc_id}/read")
def read_my_file(doc_id: int, request: Request):
    """Đọc (OCR/gỡ băng) hoặc đọc lại một file riêng của mình, tính vào trần lượt đọc mỗi ngày."""
    user = auth.require_ai(request)
    with connect() as conn:
        d = privatefiles.get_file(conn, user, doc_id)
        if d["owner_id"] != user["id"]:
            raise HTTPException(403, "Chỉ chủ file mới đọc lại được")
        if over := budget.check(conn, user):  # tiền đọc scan/ảnh tính vào trần chi tiêu AI của người này
            raise HTTPException(429, over)
        if not privatefiles.ocr_take(conn, user["id"]):
            raise HTTPException(429, f"Hôm nay bạn đã dùng hết {privatefiles.OCR_DAILY_LIMIT} lượt đọc ảnh/scan. Mai thử lại nhé.")
    documents.process_document(doc_id, use_ocr=True)
    with connect() as conn:
        return row(conn, "SELECT id, extract_status, extract_note FROM documents WHERE id = ?", (doc_id,))


@app.delete("/api/my-files/{doc_id}")
def delete_my_file(doc_id: int, request: Request):
    user = auth.current_user(request)
    with connect() as conn:
        d = _private_row(conn, user, doc_id)
        if d["owner_id"] != user["id"] and not access.is_exec(user):
            raise HTTPException(404, "Không tìm thấy file")
        privatefiles.remove(conn, doc_id)
        _log(conn, user, "delete_private", "documents", doc_id, d["stored_path"])
    return {"ok": True}


@app.post("/api/my-files/{doc_id}/publish")
def publish_my_file(doc_id: int, data: dict, request: Request):
    """Đưa một bản sao lên thư viện chung (cần quyền sửa tài liệu và đơn vị phụ trách); file riêng vẫn giữ nguyên."""
    user = auth.require_permission(request, "docs_edit")
    unit_id = data.get("unit_id") or None
    level = access.check_level(user, str(data.get("access_level") or access.DEFAULT_LEVEL))
    with connect() as conn:
        auth.check_unit_write(conn, user, unit_id)
        new_id = privatefiles.publish_copy(conn, user, doc_id, unit_id, level, str(data.get("title") or ""))
        _log(conn, user, "publish_private", "documents", new_id, f"từ file riêng {doc_id}")
    return {"id": new_id}


@app.get("/api/admin/private-files")
def admin_private_files(request: Request, user_id: int | None = None):
    """Admin/ceo: tổng quan kho riêng của từng tài khoản (dung lượng đã dùng) hoặc danh sách file của một người.
    user_id = 0 → file chưa rõ chủ ("chờ xử lý")."""
    user = auth.require_roles(request, auth.EDIT_ALL_ROLES)
    with connect() as conn:
        if user_id is None:
            return rows(conn, "SELECT u.id AS user_id, u.username, u.full_name, u.role, u.active, u.quota_mb,"
                              " COUNT(d.id) AS files, COALESCE(SUM(d.size_bytes), 0) AS used_bytes FROM users u"
                              " LEFT JOIN documents d ON d.owner_id = u.id AND d.access_level = 'private'"
                              " GROUP BY u.id ORDER BY used_bytes DESC, u.username")
        _log(conn, user, "list_private", "users", user_id)
        return rows(conn, "SELECT id, title, filename, size_bytes, extract_status, uploaded_at FROM documents"
                          " WHERE access_level = 'private' AND " + ("owner_id IS NULL" if user_id == 0 else "owner_id = ?")
                          + " ORDER BY uploaded_at DESC", () if user_id == 0 else (user_id,))


# ---------- Bộ nhớ cá nhân (AI nhớ gì về tôi) ----------
def _note(conn, user_id: int, note_id: int) -> dict:
    n = row(conn, "SELECT * FROM user_memories WHERE id = ? AND user_id = ?", (note_id, user_id))
    if not n:
        raise HTTPException(404, "Không tìm thấy ghi chú")
    return n


def _memory_state(conn, user_id: int) -> dict:
    return {"enabled": bool(conn.execute("SELECT memory_on FROM users WHERE id = ?", (user_id,)).fetchone()[0]),
            "max_notes": memory.MAX_NOTES, "idle_minutes": memory.IDLE_MINUTES,
            "notes": rows(conn, "SELECT id, text, active, source, hits, created_at, updated_at FROM user_memories"
                                " WHERE user_id = ? ORDER BY active DESC, updated_at DESC, id DESC", (user_id,))}


@app.get("/api/memory")
def get_memory(request: Request):
    user = auth.require_ai(request)
    with connect() as conn:
        return _memory_state(conn, user["id"])


@app.put("/api/memory/enabled")
def set_memory_enabled(data: dict, request: Request):
    user = auth.require_ai(request)
    with connect() as conn:
        memory.set_enabled(conn, user["id"], bool(data.get("enabled")))
        _log(conn, user, "memory_on" if data.get("enabled") else "memory_off", "users", user["id"])
        return _memory_state(conn, user["id"])


@app.post("/api/memory")
def add_memory_note(data: dict, request: Request):
    """Người dùng tự viết một ghi chú cho AI (dùng được ngay)."""
    user = auth.require_ai(request)
    with connect() as conn:
        result = memory.add_note(conn, user["id"], str(data.get("text") or ""), source="user")
    if result == "rejected":
        raise HTTPException(400, "Ghi chú không hợp lệ: cần 8–160 ký tự và không chứa thông tin nhạy cảm (lương, sức khoẻ, "
                                 "giấy tờ, mật khẩu, số điện thoại/email...).")
    if result == "full":
        raise HTTPException(400, f"Đã đủ {memory.MAX_NOTES} ghi chú. Hãy xoá bớt ghi chú cũ.")
    with connect() as conn:
        return _memory_state(conn, user["id"])


@app.put("/api/memory/{note_id}")
def edit_memory_note(note_id: int, data: dict, request: Request):
    user = auth.require_ai(request)
    text = memory.clean(str(data.get("text") or ""))
    if not text:
        raise HTTPException(400, "Ghi chú không hợp lệ: cần 8–160 ký tự và không chứa thông tin nhạy cảm.")
    with connect() as conn:
        _note(conn, user["id"], note_id)
        # người dùng đã sửa/xác nhận = điều họ tự khẳng định, dùng được ngay
        conn.execute("UPDATE user_memories SET text = ?, active = 1, source = 'user', updated_at = datetime('now','localtime')"
                     " WHERE id = ?", (text, note_id))
        return _memory_state(conn, user["id"])


@app.delete("/api/memory/{note_id}")
def delete_memory_note(note_id: int, request: Request):
    user = auth.require_ai(request)
    with connect() as conn:
        _note(conn, user["id"], note_id)
        conn.execute("DELETE FROM user_memories WHERE id = ?", (note_id,))
        return _memory_state(conn, user["id"])


@app.delete("/api/memory")
def clear_memory(request: Request):
    user = auth.require_ai(request)
    with connect() as conn:
        conn.execute("DELETE FROM user_memories WHERE user_id = ?", (user["id"],))
        _log(conn, user, "memory_clear", "users", user["id"])
        return _memory_state(conn, user["id"])


@app.post("/api/memory/refresh")
def refresh_memory(request: Request):
    """Trích ghi chú ngay từ các đoạn chat chưa xử lý (không chờ đoạn chat dừng)."""
    user = auth.require_ai(request)
    guard.check_ai_rate(user["id"])
    with connect() as conn:
        if not conn.execute("SELECT memory_on FROM users WHERE id = ?", (user["id"],)).fetchone()[0]:
            raise HTTPException(400, "Hãy bật bộ nhớ cá nhân trước.")
    processed = memory.sweep(user["id"], idle=False)
    with connect() as conn:
        return {**_memory_state(conn, user["id"]), "processed": processed}


@app.get("/api/admin/offboarding")
def admin_offboarding(request: Request):
    """Tài khoản đã khoá còn dữ liệu riêng: số ngày giữ còn lại và nút duyệt xoá khi đến hạn."""
    auth.require_roles(request, {"admin"})
    with connect() as conn:
        return {"retention_days": offboarding.RETENTION_DAYS, "accounts": offboarding.overview(conn)}


@app.post("/api/admin/offboarding/{user_id}/purge")
def admin_offboarding_purge(user_id: int, data: dict, request: Request):
    """Admin duyệt xoá vĩnh viễn dữ liệu riêng của tài khoản đã khoá quá hạn (gõ lại tên đăng nhập để xác nhận)."""
    admin = auth.require_roles(request, {"admin"})
    with connect() as conn:
        result = offboarding.purge(conn, user_id, str(data.get("confirm") or ""))
        _log(conn, admin, "purge_user_data", "users", user_id, json.dumps(result))
    return result


@app.get("/api/admin/memory")
def admin_memory(request: Request, user_id: int):
    """Admin/ceo: ghi chú AI đang nhớ về một tài khoản (để quản lý; có ghi nhật ký)."""
    user = auth.require_roles(request, auth.EDIT_ALL_ROLES)
    with connect() as conn:
        target = row(conn, "SELECT id, username, full_name FROM users WHERE id = ?", (user_id,))
        if not target:
            raise HTTPException(404, "Không tìm thấy tài khoản")
        if target["id"] != user["id"]:
            _log(conn, user, "view_memory", "users", user_id)
        return {"user": target, **_memory_state(conn, user_id)}


# ---------- Phân tích & AI ----------
@app.get("/api/insights")
def get_insights(request: Request):
    auth.require_permission(request, "insights")
    with connect() as conn:
        return analytics.insights(conn)


class ChatRequest(BaseModel):
    content: str
    conversation_id: int | None = None  # bỏ trống = bắt đầu đoạn chat mới
    model: str | None = None  # model Claude chọn trong khung chat; bỏ trống = mặc định của máy chủ


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
    user = auth.require_ai(request)
    with connect() as conn:
        return rows(conn, "SELECT id, title, created_at, updated_at FROM conversations WHERE user_id = ?"
                          " ORDER BY updated_at DESC, id DESC", (user["id"],))


@app.get("/api/conversations/{conv_id}")
def get_conversation(conv_id: int, request: Request):
    user = auth.require_ai(request)
    with connect() as conn:
        conv = _own_conversation(conn, user, conv_id)
        msgs = rows(conn, "SELECT role, content, tools_used, created_at FROM chat_messages WHERE conversation_id = ?"
                          " ORDER BY id", (conv_id,))
        # lịch sử lưu dấu [[LH:id]] (không lưu số): điền liên hệ hiện tại khi hiển thị
        emps = contacts.load(conn, set().union(*(contacts.marker_ids(m["content"]) for m in msgs)))
        can_see = user["role"] in auth.EDIT_ALL_ROLES
        for m in msgs:
            m["content"] = selfinfo.apply_marker(
                conn, user, contacts.render(m["content"], emps, can_see, user.get("employee_id")))
        last = row(conn, "SELECT model FROM ai_query_log WHERE conversation_id = ? AND model IS NOT NULL"
                         " ORDER BY id DESC LIMIT 1", (conv_id,))
    for m in msgs:
        m["tools"] = json.loads(m.pop("tools_used") or "[]")
    return {**conv, "messages": msgs, "model": conv.get("model") or (last["model"] if last else None)}


@app.put("/api/conversations/{conv_id}")
def rename_conversation(conv_id: int, data: dict, request: Request):
    user = auth.require_ai(request)
    title = _conv_title(str(data.get("title") or ""))
    if not title:
        raise HTTPException(400, "Tên đoạn chat không được trống")
    with connect() as conn:
        _own_conversation(conn, user, conv_id)
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))
    return {"ok": True}


@app.get("/api/conversations/{conv_id}/files")
def conversation_files(conv_id: int, request: Request):
    """File đính kèm của đoạn chat: để hỏi người dùng có xoá luôn khi xoá đoạn chat không."""
    user = auth.require_ai(request)
    with connect() as conn:
        _own_conversation(conn, user, conv_id)
        return privatefiles.conversation_files(conn, user["id"], conv_id)


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, request: Request, delete_files: bool = False):
    """Xoá đoạn chat. delete_files=true: xoá luôn các file đính kèm chỉ dùng trong đoạn chat này (file còn đoạn chat khác dùng được giữ lại)."""
    user = auth.require_ai(request)
    removed = 0
    with connect() as conn:
        _own_conversation(conn, user, conv_id)
        if delete_files:
            for f in privatefiles.conversation_files(conn, user["id"], conv_id)["files"]:
                privatefiles.remove(conn, f["id"])
                _log(conn, user, "delete_private", "documents", f["id"], f"cùng đoạn chat {conv_id}")
                removed += 1
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    return {"ok": True, "files_removed": removed}


@app.post("/api/chat")
def chat(req: ChatRequest, request: Request, background: BackgroundTasks):
    user = auth.require_ai(request)
    return _run_chat(req, user, background)


STREAM_PING_SECONDS = 15


class PrecheckRequest(BaseModel):
    content: str


@app.post("/api/chat/precheck")
def chat_precheck(req: PrecheckRequest, request: Request):
    """Câu hỏi có cần suy luận không: trả đề nghị nâng model (Sonnet/Opus) để giao diện hỏi người dùng trước khi gửi.
    Chỉ so từ khoá trong máy chủ, không gọi AI nên không tốn tiền."""
    auth.require_ai(request)
    return {"offer": ai.upgrade_offer(req.content[:guard.MAX_QUESTION_CHARS])}


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest, request: Request):
    """Như /api/chat nhưng trả theo luồng SSE: mỗi công cụ AI gọi được báo ngay ("tool"), cuối cùng là "done" hoặc "error".
    Giữ cách trả lời cuối nguyên vẹn; chỉ thêm tiến trình để người hỏi không phải nhìn khung chờ suốt 1–2 phút."""
    user = auth.require_ai(request)
    events: queue.Queue = queue.Queue()
    background = BackgroundTasks()  # tác vụ nền (trích bộ nhớ) chạy sau khi luồng kết thúc

    def worker() -> None:
        try:
            out = _run_chat(req, user, background, progress=lambda tool: events.put(("tool", tool)),
                            on_text=lambda text: events.put(("text", text)))
            events.put(("done", out))
        except HTTPException as e:
            events.put(("error", e.detail if isinstance(e.detail, str) else "Yêu cầu không hợp lệ"))
        except Exception:
            events.put(("error", "Lỗi máy chủ khi trả lời, hãy thử lại."))

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            try:
                kind, data = events.get(timeout=STREAM_PING_SECONDS)
            except queue.Empty:
                yield ": ping\n\n"  # giữ kết nối: tunnel/mạng di động cắt luồng im lặng quá lâu; frontend bỏ qua dòng này
                continue
            if kind == "tool":
                payload = {"type": "tool", "tool": data}
            elif kind == "text":
                payload = {"type": "text", "text": data}
            elif kind == "done":
                payload = {"type": "done", **data}
            else:
                payload = {"type": "error", "detail": data}
            yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
            if kind not in ("tool", "text"):
                return

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers, background=background)


def _run_chat(req: ChatRequest, user: dict, background: BackgroundTasks, progress=None, on_text=None) -> dict:
    # SĐT/email trong câu hỏi không được gửi cho nhà cung cấp AI hay lưu vào lịch sử
    content = contacts.scrub(req.content.strip())
    if not content:
        raise HTTPException(400, "Câu hỏi trống")
    if len(content) > guard.MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Câu hỏi quá dài (tối đa {guard.MAX_QUESTION_CHARS} ký tự)")
    guard.check_ai_rate(user["id"])
    with connect() as conn:
        if over := budget.check(conn, user):
            raise HTTPException(429, over)
        history = []
        if req.conversation_id:
            _own_conversation(conn, user, req.conversation_id)
            history = rows(conn, "SELECT role, content, tools_used FROM chat_messages WHERE conversation_id = ? ORDER BY id",
                           (req.conversation_id,))
    # đoạn chat cũ có thể còn số điện thoại thô: che trước khi gửi lại cho AI
    history = [{**m, "content": contacts.scrub(m["content"])} for m in history]
    # Ảnh/scan đính kèm chỉ được đọc bằng AI lúc gửi câu hỏi; file chưa đọc được thì báo AI để nói thật với người dùng
    ai_content = content
    if notes := privatefiles.prepare_attachments(user, content):
        ai_content += "\n\n[Hệ thống: " + " ".join(notes) + " Hãy báo người dùng điều này, đừng đoán nội dung file.]"
    with connect() as conn:
        mem = memory.context(conn, user["id"])  # '' nếu người dùng chưa bật bộ nhớ cá nhân
    res = ai.answer(history + [{"role": "user", "content": ai_content}], user, audit=ai.new_audit(progress, on_text), memory=mem, model=req.model)
    trail = res.pop("audit", {"flags": [], "docs_read": []})
    usage = trail.get("usage") or {}
    with connect() as conn:  # nhật ký mọi câu hỏi AI (kể cả lượt lỗi): ai hỏi gì, AI đọc tài liệu nào, có nội dung đáng ngờ không
        conn.execute(
            "INSERT INTO ai_query_log (user_id, conversation_id, question, tools, docs_read, flags, model, error,"
            " input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user["id"], req.conversation_id, content[:2000], json.dumps(res.get("tools_used") or []),
             json.dumps(trail["docs_read"]), json.dumps(trail["flags"], ensure_ascii=False), res.get("model"), res.get("error"),
             usage.get("input"), usage.get("output"), usage.get("cache_read"), usage.get("cache_write"), usage.get("cost_usd")))
    if res.get("error"):  # không lưu lượt lỗi để lần hỏi lại không gửi kèm câu trả lời lỗi cho AI
        return {**res, "conversation_id": req.conversation_id}
    # câu trả lời AI viết: che số lạ; dấu [[LH:id]] được giữ lại trong lịch sử, số chỉ điền khi hiển thị
    answer = contacts.scrub(res["answer"])
    if trail.get("exports"):  # link tải do máy chủ gắn (AI không được tự viết link; guard.clean_answer đã bỏ link lạ)
        answer += "\n\n" + "\n".join(f"📎 [{e['filename']}](/api/exports/{e['token']})" for e in trail["exports"])
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
        conn.execute("UPDATE conversations SET updated_at = datetime('now','localtime'), model = COALESCE(?, model)"
                     " WHERE id = ?", (res.get("model"), conv_id))
        title = conn.execute("SELECT title FROM conversations WHERE id = ?", (conv_id,)).fetchone()[0]
        shown = selfinfo.apply_marker(conn, user, contacts.render_for_viewer(conn, answer, can_see, user.get("employee_id")))
    with connect() as conn:
        if conn.execute("SELECT memory_on FROM users WHERE id = ?", (user["id"],)).fetchone()[0]:
            background.add_task(memory.sweep, user["id"])  # trích ghi chú từ các đoạn chat trước đã dừng
    return {**res, "answer": shown, "conversation_id": conv_id, "title": title}


@app.get("/api/exports/{token}")
def download_export(token: str, request: Request):
    """Tải file Word/Excel/PowerPoint do trợ lý AI tạo; chỉ người đã yêu cầu mới tải được, giữ 7 ngày."""
    user = auth.require_ai(request)
    path = export.find(user["id"], token)
    if not path:
        raise HTTPException(404, "File không còn (chỉ lưu 7 ngày) hoặc không thuộc tài khoản của bạn. Hãy nhờ trợ lý tạo lại.")
    name = export.display_name(path)
    with connect() as conn:
        _log(conn, user, "export_download", "ai_export", None, name)
    return FileResponse(path, filename=name, media_type=export.MIME.get(path.suffix.lstrip("."), "application/octet-stream"))


@app.get("/api/ai/status")
def ai_status():
    return ai.status()


@app.get("/api/ai/audit")
def ai_audit(request: Request, limit: int = 200, flagged_only: bool = False):
    """Nhật ký câu hỏi AI (chỉ admin): ai hỏi gì, AI tra cứu/đọc tài liệu nào, có cảnh báo nội dung ép AI không."""
    auth.require_roles(request, {"admin"})
    with connect() as conn:
        out = rows(conn, "SELECT l.*, u.username, u.full_name FROM ai_query_log l LEFT JOIN users u ON u.id = l.user_id"
                         + (" WHERE l.flags != '[]'" if flagged_only else "") + " ORDER BY l.id DESC LIMIT ?",
                   (max(1, min(limit, 1000)),))
    return out


@app.get("/api/ai/usage")
def ai_usage(request: Request, days: int = 7):
    """Chi phí AI ngoài khung chat (OCR, đối chiếu scan, tóm tắt web, bộ nhớ) và tổng theo loại việc (chỉ admin)."""
    auth.require_roles(request, {"admin"})
    since = f"-{max(1, min(days, 365))} days"
    with connect() as conn:
        recent = rows(conn, "SELECT * FROM ai_usage_log WHERE ts >= datetime('now','localtime',?) ORDER BY id DESC LIMIT 200", (since,))
        totals = rows(conn, "SELECT kind, model, COUNT(*) AS calls, SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens,"
                            " ROUND(SUM(cost_usd), 4) AS cost_usd FROM ai_usage_log WHERE ts >= datetime('now','localtime',?)"
                            " GROUP BY kind, model ORDER BY cost_usd DESC", (since,))
    return {"totals": totals, "recent": recent}


@app.get("/api/admin/backups")
def list_backups(request: Request):
    auth.require_roles(request, {"admin"})
    return {"dir": str(backup.backup_dir()), "keep": backup.KEEP, "backups": backup.list_backups()}


@app.post("/api/admin/backups")
def create_backup(request: Request):
    user = auth.require_roles(request, {"admin"})
    result = backup.run_backup()
    with connect() as conn:
        _log(conn, user, "backup", "system", None, result["database"])
    return result


# ---------- Giao diện ----------
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


# Đường dẫn giao diện (/units/5/org, /people/12...) do JS xử lý: mọi đường dẫn không phải API/tệp đều trả index.html
@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str):
    if path.split("/")[0] in ("api", "static") or "." in path.rsplit("/", 1)[-1]:
        return JSONResponse({"detail": "Không tìm thấy"}, status_code=404)  # không để lỗi API/tệp thiếu biến thành trang HTML
    return FileResponse(FRONTEND / "index.html")
