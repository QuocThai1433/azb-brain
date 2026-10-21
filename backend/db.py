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
"""

MIGRATIONS = [
    "ALTER TABLE audit_log ADD COLUMN user_id INTEGER",
    "ALTER TABLE employees ADD COLUMN employee_code TEXT",
    # Thông tin từ danh sách nhân sự HCNS (xem backend/hr_import.py)
    "ALTER TABLE employees ADD COLUMN job_title TEXT",       # chức danh theo HCNS
    "ALTER TABLE employees ADD COLUMN grade TEXT",           # ngạch lao động: Lãnh đạo, Trưởng Phòng Ban, Nhân viên...
    "ALTER TABLE employees ADD COLUMN labor_group TEXT",     # phân loại nhóm lao động
    "ALTER TABLE employees ADD COLUMN unit_id INTEGER REFERENCES units(id) ON DELETE SET NULL",  # đơn vị công tác
    "ALTER TABLE employees ADD COLUMN hr_department TEXT",   # phòng ban / công trình theo danh sách HCNS
    "ALTER TABLE employees ADD COLUMN hr_division TEXT",     # khối theo danh sách HCNS
    "ALTER TABLE employees ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE access_requests ADD COLUMN updated_at TEXT",  # lần user chỉnh sửa đơn gần nhất
    "ALTER TABLE access_requests ADD COLUMN seen_by_user INTEGER NOT NULL DEFAULT 1",  # 0 = có kết quả mới user chưa xem
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


def rows(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def row(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None
