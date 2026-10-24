"""Kết nối SQLite và schema dữ liệu công ty AZB.

Mô hình:
  units      – cây tổ chức: HĐQT, ban điều hành, khối, phòng/ban (parent_id = cấp quản lý trực tiếp)
  employees  – nhân sự
  positions  – chức danh trong từng đơn vị; employee_id NULL = đang trống (TBA).
               Một người có thể giữ nhiều chức danh (kiêm nhiệm).
  processes  – quy trình vận hành / ISO của từng đơn vị (có thể để trống)
  targets    – mục tiêu doanh thu, doanh số, chỉ tiêu khác theo kỳ (có thể để trống)
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "azb.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
    id          INTEGER PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    full_name   TEXT,              -- tên đầy đủ / giải nghĩa viết tắt
    unit_type   TEXT NOT NULL,     -- board | executive | division | department | committee | project
    parent_id   INTEGER REFERENCES units(id) ON DELETE SET NULL,
    color_group TEXT,              -- nhóm màu theo sơ đồ (hr, ops, finance, technical, construction, commercial, exec)
    functions   TEXT,              -- chức năng, nhiệm vụ
    notes       TEXT,
    verified    INTEGER NOT NULL DEFAULT 1,  -- 0 = thông tin cần xác nhận lại
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS employees (
    id          INTEGER PRIMARY KEY,
    employee_code TEXT,            -- mã nhân viên
    full_name   TEXT NOT NULL,
    display_name TEXT,             -- cách ghi trên sơ đồ (có thể viết tắt)
    email       TEXT,
    phone       TEXT,
    joined_date TEXT,
    status      TEXT NOT NULL DEFAULT 'active',  -- active | inactive
    notes       TEXT,
    verified    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY,
    unit_id     INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,     -- VD: Trưởng phòng, Phó phòng
    title_code  TEXT,              -- CT, TGĐ, PTGĐ, GĐ, GĐK, TB, TBP, TP, PP, PB, NV
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    is_head     INTEGER NOT NULL DEFAULT 0,      -- 1 = người phụ trách đơn vị
    headcount   INTEGER NOT NULL DEFAULT 1,      -- định biên cho dòng chức danh này
    notes       TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS processes (
    id             INTEGER PRIMARY KEY,
    unit_id        INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    code           TEXT,           -- VD: QT-HCNS-01
    name           TEXT NOT NULL,
    version        TEXT,
    iso_clause     TEXT,           -- điều khoản ISO liên quan
    owner          TEXT,           -- chức danh chủ trì
    related_units  TEXT,           -- các đơn vị phối hợp
    purpose        TEXT,
    content        TEXT,           -- nội dung các bước (markdown)
    status         TEXT NOT NULL DEFAULT 'draft',  -- draft | active | retired
    effective_date TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS targets (
    id           INTEGER PRIMARY KEY,
    unit_id      INTEGER REFERENCES units(id) ON DELETE CASCADE,  -- NULL = toàn công ty
    period       TEXT NOT NULL,    -- VD: 2026, 2026-Q4, 2026-10
    metric       TEXT NOT NULL,    -- doanh_thu | doanh_so | loi_nhuan | khac
    metric_name  TEXT,
    target_value REAL,
    actual_value REAL,
    unit_label   TEXT DEFAULT 'VNĐ',
    notes        TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY,
    ts        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    action    TEXT NOT NULL,
    entity    TEXT NOT NULL,
    entity_id INTEGER,
    detail    TEXT,
    user_id   INTEGER
);

-- Tài khoản: admin (toàn quyền + quản lý tài khoản), ceo (xem/sửa tất cả, dùng AI),
-- manager (xem tất cả, chỉ sửa đơn vị mình và đơn vị con), viewer (chỉ xem sơ đồ)
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL DEFAULT 'viewer',
    unit_id       INTEGER REFERENCES units(id) ON DELETE SET NULL,
    password_hash TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS user_permissions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    feature TEXT NOT NULL,
    PRIMARY KEY (user_id, feature)
);

-- Yêu cầu xin cấp quyền truy cập tính năng; admin duyệt
CREATE TABLE IF NOT EXISTS access_requests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    features   TEXT NOT NULL,                       -- danh sách tính năng, ngăn cách bằng dấu phẩy
    reason     TEXT,
    status     TEXT NOT NULL DEFAULT 'pending',     -- pending | approved | rejected
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    decided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    decided_at TEXT,
    admin_note TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

-- Tài liệu gốc (quy trình ISO, biểu mẫu, quy định...) và nội dung đã trích xuất
CREATE TABLE IF NOT EXISTS documents (
    id           INTEGER PRIMARY KEY,
    unit_id      INTEGER REFERENCES units(id) ON DELETE SET NULL,   -- NULL = tài liệu chung công ty
    process_id   INTEGER REFERENCES processes(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    doc_type     TEXT NOT NULL DEFAULT 'quy_trinh',  -- quy_trinh | quy_dinh | ram | huong_dan | bieu_mau | so_tay | website | khac
    code         TEXT,
    version      TEXT,
    filename     TEXT NOT NULL,
    stored_path  TEXT NOT NULL,
    mime         TEXT,
    size_bytes   INTEGER,
    page_count   INTEGER,
    char_count   INTEGER,
    extract_status TEXT NOT NULL DEFAULT 'pending', -- pending | ok | needs_ocr | failed
    extract_note TEXT,
    content      TEXT,              -- toàn văn đã trích xuất
    uploaded_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Lịch sử trò chuyện với trợ lý AI, riêng theo từng tài khoản
-- Người duyệt đã đối chiếu từng trang văn bản AI đọc với bản gốc: verified = đúng, edited = đã sửa
CREATE TABLE IF NOT EXISTS doc_page_review (
    doc_id      INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no     INTEGER NOT NULL,
    status      TEXT NOT NULL,
    reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (doc_id, page_no)
);
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,   -- user | assistant
    content         TEXT NOT NULL,
    tools_used      TEXT,            -- JSON danh sách công cụ AI đã gọi
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_conv ON chat_messages(conversation_id, id);

-- Nhật ký mọi câu hỏi gửi trợ lý AI: ai hỏi, AI tra cứu gì, đọc tài liệu nào, có phát hiện nội dung đáng ngờ không
CREATE TABLE IF NOT EXISTS ai_query_log (
    id              INTEGER PRIMARY KEY,
    ts              TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    user_id         INTEGER,
    conversation_id INTEGER,
    question        TEXT,
    tools           TEXT,            -- JSON danh sách công cụ đã gọi
    docs_read       TEXT,            -- JSON id tài liệu AI đã đọc nội dung
    flags           TEXT,            -- JSON các lần phát hiện nội dung giống chỉ dẫn ép AI
    model           TEXT,
    error           TEXT
);

-- Chỉ mục tìm kiếm toàn văn, không phân biệt dấu tiếng Việt
CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks USING fts5(
    text, doc_id UNINDEXED, chunk_no UNINDEXED, page UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- Chỉ mục riêng cho trợ lý AI: văn bản đã bỏ hết dấu (kể cả đ -> d, unicode61 không tự làm) và tách mã chữ-số
-- (QT01 -> qt 01). src = rowid của đoạn gốc trong doc_chunks. Tự đồng bộ từ doc_chunks theo dấu thời gian/trạng thái
-- trong bảng documents (documents.sync_ai_index), không cần ghi tay.
CREATE VIRTUAL TABLE IF NOT EXISTS doc_index USING fts5(
    text, doc_id UNINDEXED, chunk_no UNINDEXED, page UNINDEXED, src UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS doc_index_meta (
    doc_id INTEGER PRIMARY KEY,
    stamp  TEXT NOT NULL
);

-- Bộ nhớ cá nhân: ghi chú ngắn về từng người dùng (chỉ khi họ tự bật users.memory_on), xem backend/memory.py
CREATE TABLE IF NOT EXISTS user_memories (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    active      INTEGER NOT NULL DEFAULT 1,   -- 0 = mới suy ra từ một lần chat, chờ lặp lại/xác nhận mới được AI dùng
    source      TEXT NOT NULL DEFAULT 'ai',   -- ai | user
    hits        INTEGER NOT NULL DEFAULT 1,
    conv_id     INTEGER,                      -- đoạn chat gần nhất củng cố ghi chú này
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_user_memories_user ON user_memories(user_id, active);

-- Yêu cầu chỉnh sửa hồ sơ nhân sự do chính người đó gửi (users.employee_id); admin duyệt mới ghi vào employees, xem backend/selfinfo.py
CREATE TABLE IF NOT EXISTS employee_change_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    field       TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT NOT NULL,
    reason      TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    decided_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    decided_at  TEXT,
    admin_note  TEXT,
    seen_by_user INTEGER NOT NULL DEFAULT 1            -- 0 = admin vừa xử lý, user chưa xem
);
CREATE INDEX IF NOT EXISTS idx_emp_change_status ON employee_change_requests(status, id);

-- Người dùng tự chọn hồ sơ nhân sự của mình để liên kết với tài khoản; admin duyệt mới ghi users.employee_id (backend/selfinfo.py)
CREATE TABLE IF NOT EXISTS link_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    decided_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    decided_at  TEXT,
    admin_note  TEXT,
    seen_by_user INTEGER NOT NULL DEFAULT 1            -- 0 = admin vừa xử lý, user chưa xem
);

-- Số lần đọc ảnh/scan/ghi âm bằng AI của mỗi người mỗi ngày (trần chung để một người không dùng hết hạn mức Gemini)
CREATE TABLE IF NOT EXISTS ocr_usage (
    user_id INTEGER NOT NULL,
    day     TEXT NOT NULL,
    n       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

-- Vector ngữ nghĩa của từng đoạn tài liệu (xem backend/semantic.py). src = rowid trong doc_chunks, vec = JSON đã chuẩn hoá
CREATE TABLE IF NOT EXISTS doc_vectors (
    src      INTEGER PRIMARY KEY,
    doc_id   INTEGER NOT NULL,
    chunk_no INTEGER,
    page     INTEGER,
    vec      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_doc_vectors_doc ON doc_vectors (doc_id);
-- Dấu nội dung mà vector của tài liệu đó được tạo từ (đổi nội dung thì tạo lại)
CREATE TABLE IF NOT EXISTS doc_vector_meta (
    doc_id INTEGER PRIMARY KEY,
    stamp  TEXT NOT NULL
);

-- Đề xuất cải tiến (lưu từ câu trả lời của trợ lý AI hoặc nhập tay) và tiến trình xử lý
CREATE TABLE IF NOT EXISTS proposals (
    id          INTEGER PRIMARY KEY,
    title       TEXT NOT NULL,
    body        TEXT,
    status      TEXT NOT NULL DEFAULT 'new',  -- new | approved | in_progress | done | dropped
    owner       TEXT,                         -- người/bộ phận phụ trách thực hiện
    note        TEXT,                         -- ghi chú của Ban TGĐ
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

MIGRATIONS = [
    "ALTER TABLE audit_log ADD COLUMN user_id INTEGER",
    # Lịch sử thay đổi: tên đối tượng tại lúc ghi (đối tượng đã xoá vẫn có tên), ảnh chụp để hoàn tác, bản ghi hoàn tác nó
    "ALTER TABLE audit_log ADD COLUMN label TEXT",
    "ALTER TABLE audit_log ADD COLUMN snapshot TEXT",
    "ALTER TABLE audit_log ADD COLUMN reverted_by INTEGER",
    # Chỉ mục cho trang Lịch sử (lọc theo ngày, người, loại) để nhật ký dài ra vẫn nhanh
    "CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts)",
    "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, ts)",
    "CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity, entity_id)",
    "ALTER TABLE employees ADD COLUMN employee_code TEXT",
    # Thông tin từ danh sách nhân sự HCNS (xem backend/hr_import.py)
    "ALTER TABLE employees ADD COLUMN job_title TEXT",       # chức danh theo HCNS
    "ALTER TABLE employees ADD COLUMN grade TEXT",           # ngạch lao động: Lãnh đạo, Trưởng Phòng Ban, Nhân viên...
    "ALTER TABLE employees ADD COLUMN labor_group TEXT",     # phân loại nhóm lao động
    "ALTER TABLE employees ADD COLUMN unit_id INTEGER REFERENCES units(id) ON DELETE SET NULL",  # đơn vị công tác
    "ALTER TABLE employees ADD COLUMN hr_department TEXT",   # phòng ban / công trình theo danh sách HCNS
    "ALTER TABLE employees ADD COLUMN hr_division TEXT",     # khối theo danh sách HCNS
    "ALTER TABLE employees ADD COLUMN birth_date TEXT",       # ngày sinh (YYYY-MM-DD)
    "ALTER TABLE employees ADD COLUMN contract_term TEXT",    # loại hợp đồng lao động theo HCNS
    "ALTER TABLE employees ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE access_requests ADD COLUMN updated_at TEXT",  # lần user chỉnh sửa đơn gần nhất
    "ALTER TABLE access_requests ADD COLUMN seen_by_user INTEGER NOT NULL DEFAULT 1",  # 0 = có kết quả mới user chưa xem
    "ALTER TABLE access_requests ADD COLUMN extra_mb INTEGER",    # xin thêm dung lượng kho riêng (MB); NULL = không xin
    "ALTER TABLE access_requests ADD COLUMN granted_mb INTEGER",   # số MB admin thực cấp khi duyệt
    "ALTER TABLE link_requests ADD COLUMN seen_by_user INTEGER NOT NULL DEFAULT 1",  # 0 = admin vừa xử lý, user chưa xem
    "ALTER TABLE employee_change_requests ADD COLUMN seen_by_user INTEGER NOT NULL DEFAULT 1",
    # Kho riêng theo tài khoản: file đính kèm chat có access_level = 'private' và owner_id = người gửi (xem backend/access.py)
    "ALTER TABLE documents ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE users ADD COLUMN quota_mb INTEGER",  # NULL = hạn mức mặc định (privatefiles.DEFAULT_QUOTA_MB)
    "ALTER TABLE users ADD COLUMN memory_on INTEGER NOT NULL DEFAULT 0",  # người dùng tự bật bộ nhớ cá nhân
    "ALTER TABLE conversations ADD COLUMN memory_at TEXT",  # lần cuối đã trích ghi chú từ đoạn chat này
    # Nghỉ việc: tài khoản bị khoá giữ dữ liệu riêng 90 ngày, sau đó admin duyệt xoá (backend/offboarding.py)
    "ALTER TABLE users ADD COLUMN deactivated_at TEXT",
    "ALTER TABLE users ADD COLUMN data_purged_at TEXT",
    # Tài khoản này là nhân viên nào trong danh sách nhân sự (admin gán; mỗi hồ sơ chỉ gán cho một tài khoản)
    "ALTER TABLE users ADD COLUMN employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL",
    # Tự đăng ký (xem /api/auth/register): tài khoản chờ admin duyệt, khác với tài khoản bị khoá
    "ALTER TABLE users ADD COLUMN pending_approval INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN register_note TEXT",  # bản ghi cũ: người đăng ký tự ghi phòng ban/SĐT trong một ô; không đưa cho AI
    "ALTER TABLE users ADD COLUMN register_unit TEXT",   # phòng ban / công trình người đăng ký chọn hoặc nhập, để admin xác minh; không đưa cho AI
    "ALTER TABLE users ADD COLUMN register_phone TEXT",  # số máy lẻ nội bộ (không bắt buộc); không đưa cho AI
]


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        for sql in MIGRATIONS:  # nâng cấp database tạo từ phiên bản trước
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
        # Độ mật tài liệu: mặc định 'internal'; tài liệu website (nội dung công khai) chuyển sang 'public' đúng một lần
        # lúc thêm cột, để admin đổi sau đó không bị ghi đè.
        if "access_level" not in {r[1] for r in conn.execute("PRAGMA table_info(documents)")}:
            conn.execute("ALTER TABLE documents ADD COLUMN access_level TEXT NOT NULL DEFAULT 'internal'")
            conn.execute("UPDATE documents SET access_level = 'public' WHERE doc_type = 'website'")
        # Tách quyền xoá và tải file gốc khỏi docs_edit/docs_view: đúng một lần, giữ nguyên quyền người dùng đang có
        # (sau đó admin thu hồi từng quyền thì không bị cấp lại).
        if conn.execute("PRAGMA user_version").fetchone()[0] < 1:
            conn.execute("INSERT OR IGNORE INTO user_permissions (user_id, feature)"
                         " SELECT user_id, 'docs_delete' FROM user_permissions WHERE feature = 'docs_edit'")
            conn.execute("INSERT OR IGNORE INTO user_permissions (user_id, feature)"
                         " SELECT user_id, 'docs_download' FROM user_permissions WHERE feature IN ('docs_view', 'docs_edit')")
            conn.execute("PRAGMA user_version = 1")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id)")
        # mỗi hồ sơ nhân sự chỉ gắn với một tài khoản (tránh hai tài khoản cùng xem được thông tin cá nhân của một người)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_employee ON users(employee_id) WHERE employee_id IS NOT NULL")
        # tài khoản đã khoá từ trước khi có cột này: bắt đầu tính 90 ngày từ lúc nâng cấp
        conn.execute("UPDATE users SET deactivated_at = datetime('now','localtime') WHERE active = 0 AND deactivated_at IS NULL")
        # Ảnh dán từ chat từng bị lưu vào thư viện chung: chuyển về kho riêng của người đã tải (không rõ người tải thì
        # owner NULL = "chờ xử lý", chỉ admin/ceo thấy). Chạy lại nhiều lần vẫn an toàn.
        conn.execute("UPDATE documents SET access_level = 'private', owner_id = uploaded_by, unit_id = NULL, process_id = NULL"
                     " WHERE filename LIKE 'anh-dan-%' AND access_level != 'private'")


def rows(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def row(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None
