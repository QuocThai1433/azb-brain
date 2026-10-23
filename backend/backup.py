"""Sao lưu tự động database và file tài liệu gốc, chống mất dữ liệu.

- Database: dùng API backup của SQLite (an toàn khi server đang chạy), giữ AZB_BACKUP_KEEP bản gần nhất.
- File tải lên: sao chép sang thư mục backup/uploads, chỉ chép file mới hoặc đã đổi và KHÔNG bao giờ xoá bản sao
  (tài liệu lỡ xoá vẫn lấy lại được).
- Đặt AZB_BACKUP_DIR sang ổ đĩa/NAS khác máy: sao lưu cùng ổ với dữ liệu không cứu được khi hỏng ổ.
"""
import os
import shutil
import sqlite3
import threading
import time
from pathlib import Path

from . import db, documents

KEEP = int(os.environ.get("AZB_BACKUP_KEEP", "14"))
EVERY_HOURS = float(os.environ.get("AZB_BACKUP_HOURS", "24"))


def backup_dir() -> Path:
    return Path(os.environ.get("AZB_BACKUP_DIR") or db.DB_PATH.parent / "backups")


def list_backups() -> list[dict]:
    d = backup_dir()
    files = sorted(d.glob("azb-*.db"), reverse=True) if d.exists() else []
    return [{"name": f.name, "size_bytes": f.stat().st_size, "created": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))}
            for f in files]


def run_backup() -> dict:
    dest = backup_dir()
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"azb-{time.strftime('%Y%m%d-%H%M%S')}.db"
    src, dst = sqlite3.connect(db.DB_PATH), sqlite3.connect(target)
    try:
        src.backup(dst)
        if dst.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("Bản sao lưu database không hợp lệ")
    except Exception:
        dst.close()
        target.unlink(missing_ok=True)
        raise
    finally:
        src.close()
        dst.close()
    copied = 0
    mirror = dest / "uploads"
    upload_dir = Path(documents.UPLOAD_DIR)
    if upload_dir.exists():
        mirror.mkdir(exist_ok=True)
        for f in upload_dir.rglob("*"):
            if not f.is_file():
                continue
            out = mirror / f.relative_to(upload_dir)
            if not out.exists() or out.stat().st_size != f.stat().st_size or out.stat().st_mtime < f.stat().st_mtime:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, out)
                copied += 1
    for old in sorted(dest.glob("azb-*.db"), reverse=True)[KEEP:]:
        old.unlink(missing_ok=True)
    return {"database": target.name, "files_copied": copied, "keep": KEEP}


def _newest_age_hours() -> float:
    files = list(backup_dir().glob("azb-*.db")) if backup_dir().exists() else []
    return (time.time() - max(f.stat().st_mtime for f in files)) / 3600 if files else float("inf")


def _loop() -> None:
    while True:
        try:
            if _newest_age_hours() >= EVERY_HOURS:
                run_backup()
        except Exception as e:  # sao lưu lỗi không được làm sập server
            print(f"[backup] lỗi: {e}")
        time.sleep(3600)


def start_scheduler() -> None:
    if EVERY_HOURS > 0:
        threading.Thread(target=_loop, name="azb-backup", daemon=True).start()
