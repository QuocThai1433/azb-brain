"""Dọn nhật ký thay đổi (audit_log) theo tầng để database không phình mãi:
  - quá `snapshot_days` ngày: xoá riêng ảnh chụp dùng để Hoàn tác (phần nặng nhất), giữ dòng chữ (ai, khi nào, đổi gì);
  - quá `archive_days` ngày: lưu ra file Excel trong thư mục archive cạnh database rồi mới xoá khỏi database.
"""
import time
from pathlib import Path

from . import db, export

DEFAULT_SNAPSHOT_DAYS = 90
DEFAULT_ARCHIVE_DAYS = 730
MIN_SNAPSHOT_DAYS = 30
MIN_ARCHIVE_DAYS = 365
ACT = {"create": "Thêm mới", "update": "Sửa", "delete": "Xoá", "import": "Nhập", "seed": "Nạp mẫu"}


def check_days(snapshot_days: int, archive_days: int) -> None:
    if snapshot_days < MIN_SNAPSHOT_DAYS:
        raise ValueError(f"Giữ khả năng Hoàn tác tối thiểu {MIN_SNAPSHOT_DAYS} ngày")
    if archive_days < MIN_ARCHIVE_DAYS:
        raise ValueError(f"Giữ nhật ký trong hệ thống tối thiểu {MIN_ARCHIVE_DAYS} ngày")
    if archive_days <= snapshot_days:
        raise ValueError("Thời hạn lưu trữ phải dài hơn thời hạn Hoàn tác")


def archive_dir() -> Path:
    return db.DB_PATH.parent / "archive"


def _cut(days: int) -> str:
    return f"datetime('now','localtime','-{int(days)} days')"


def preview(conn, snapshot_days: int = DEFAULT_SNAPSHOT_DAYS, archive_days: int = DEFAULT_ARCHIVE_DAYS) -> dict:
    check_days(snapshot_days, archive_days)
    total, oldest = conn.execute("SELECT COUNT(*), MIN(ts) FROM audit_log").fetchone()
    snaps, snap_bytes = conn.execute(
        f"SELECT COUNT(*), COALESCE(SUM(LENGTH(snapshot)),0) FROM audit_log WHERE snapshot IS NOT NULL AND ts < {_cut(snapshot_days)}").fetchone()
    old = conn.execute(f"SELECT COUNT(*) FROM audit_log WHERE ts < {_cut(archive_days)}").fetchone()[0]
    return {"total": total, "oldest": oldest, "snapshot_days": snapshot_days, "archive_days": archive_days,
            "snapshots_to_drop": snaps, "snapshot_bytes": snap_bytes, "rows_to_archive": old,
            "db_bytes": db.DB_PATH.stat().st_size if db.DB_PATH.exists() else 0}


def cleanup(snapshot_days: int = DEFAULT_SNAPSHOT_DAYS, archive_days: int = DEFAULT_ARCHIVE_DAYS, user_id: int | None = None) -> dict:
    check_days(snapshot_days, archive_days)
    archived, archive_file = 0, None
    with db.connect() as conn:
        old = conn.execute(
            "SELECT l.id, l.ts, l.action, l.entity, l.entity_id, l.label, l.detail, l.reverted_by, COALESCE(u.full_name, u.username, '') AS who"
            f" FROM audit_log l LEFT JOIN users u ON u.id = l.user_id WHERE l.ts < {_cut(archive_days)} ORDER BY l.id").fetchall()
        if old:  # lưu file TRƯỚC, chỉ xoá khi file đã ghi xong
            lines = [[r["ts"], r["who"], ACT.get(r["action"], r["action"]), r["entity"], r["label"] or f"#{r['entity_id']}",
                      r["detail"] or "", "có" if r["reverted_by"] else ""] for r in old]
            archive_dir().mkdir(parents=True, exist_ok=True)
            archive_file = archive_dir() / f"AZB_nhat_ky_den_{old[-1]['ts'][:10]}_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
            archive_file.write_bytes(export.history_xlsx(lines))
            conn.execute(f"DELETE FROM audit_log WHERE ts < {_cut(archive_days)}")
            archived = len(old)
        dropped = conn.execute(f"UPDATE audit_log SET snapshot = NULL WHERE snapshot IS NOT NULL AND ts < {_cut(snapshot_days)}").rowcount
        conn.execute("INSERT INTO audit_log (action, entity, detail, user_id) VALUES ('cleanup','audit_log',?,?)",
                     (f"Dọn nhật ký: bỏ {dropped} ảnh chụp hoàn tác (quá {snapshot_days} ngày), lưu trữ và xoá {archived} dòng (quá {archive_days} ngày)", user_id))
    if dropped or archived:
        with db.connect() as conn:  # VACUUM không chạy được trong giao dịch: mở kết nối riêng để file thật sự nhỏ lại
            conn.execute("VACUUM")
    return {"snapshots_dropped": dropped, "rows_archived": archived, "archive_file": archive_file.name if archive_file else None}
