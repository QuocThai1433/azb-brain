"""Tìm tài liệu theo ý nghĩa (embedding Gemini), bổ sung cho tìm từ khoá.

Từ khoá vẫn là nguồn chính (xem documents.ai_search). Khi từ khoá không đủ kết quả, tài liệu có đoạn gần nghĩa nhất
với câu hỏi được thêm vào cuối. Vector lưu trong SQLite (doc_vectors); tạo lại khi nội dung tài liệu đổi.

Cần GEMINI_API_KEY. Không có khoá thì module không làm gì và tìm kiếm từ khoá hoạt động như cũ.
Nội dung tài liệu được gửi tới Gemini để tạo vector. Đồng bộ tự động TẮT mặc định (AZB_EMBED_SYNC=1 mới bật).
Ngưỡng điểm AZB_EMBED_MIN (mặc định 0.6) chưa hiệu chỉnh trên dữ liệu thật: nên kiểm tra sau khi nạp tài liệu.
"""
import json
import math
import os
import threading
import time

from . import documents
from .db import rows

MODEL = os.environ.get("AZB_EMBED_MODEL", "gemini-embedding-001")
DIM = int(os.environ.get("AZB_EMBED_DIM", "256"))  # số chiều vector: nhỏ hơn thì nhanh và nhẹ hơn
BATCH = 50  # số đoạn mỗi lần gọi API
SYNC_EVERY_S = int(os.environ.get("AZB_EMBED_SYNC_S", "600"))
SYNC_BUDGET = int(os.environ.get("AZB_EMBED_BUDGET", "500"))  # số đoạn tối đa mỗi lần đồng bộ (tránh dồn quota)
MIN_SCORE = float(os.environ.get("AZB_EMBED_MIN", "0.6"))

_cache: dict = {"version": 0, "index": None, "built_at": -1}
_embed_override = None  # để kiểm thử: hàm (texts, task) -> list vector


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _embed(texts: list[str], task: str) -> list[list[float]]:
    if _embed_override is not None:
        return _embed_override(texts, task)
    from google.genai import types
    from . import ai
    resp = ai.client(60).models.embed_content(
        model=MODEL, contents=texts,
        config=types.EmbedContentConfig(task_type=task, output_dimensionality=DIM))
    return [_normalize(list(e.values)) for e in resp.embeddings]


def available() -> bool:
    from . import ai
    return ai.has_gemini()


def sync(conn, budget: int = SYNC_BUDGET) -> int:
    """Tạo vector cho các đoạn chưa có (hoặc của tài liệu đã đổi); xoá vector của tài liệu đã bị xoá.
    Trả về số đoạn vừa tạo. Dừng khi hết `budget` để lần sau tiếp tục."""
    docs = rows(conn, "SELECT id, title, code, filename, char_count, page_count, extract_status, uploaded_at FROM documents")
    stamps = {d["id"]: documents._doc_stamp(d) for d in docs}
    meta = {r[0]: r[1] for r in conn.execute("SELECT doc_id, stamp FROM doc_vector_meta")}
    stale = [i for i in meta if i not in stamps or meta[i] != stamps[i]]
    for doc_id in stale:
        conn.execute("DELETE FROM doc_vectors WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM doc_vector_meta WHERE doc_id = ?", (doc_id,))
    if stale:
        conn.commit()
        _cache["version"] += 1
    current = {i: s for i, s in meta.items() if i not in stale}
    todo = [i for i in stamps if current.get(i) != stamps[i]]  # tài liệu chưa có vector hoặc vừa đổi nội dung
    done = 0
    for doc_id in todo:
        if done >= budget:
            break
        conn.execute("DELETE FROM doc_vectors WHERE doc_id = ?", (doc_id,))
        chunks = [c for c in conn.execute(
            "SELECT rowid, chunk_no, page, text FROM doc_chunks WHERE CAST(doc_id AS INTEGER) = ? ORDER BY chunk_no",
            (doc_id,)).fetchall() if c[3] and c[3].strip()]
        for i in range(0, len(chunks), BATCH):
            part = chunks[i:i + BATCH]
            vectors = _embed([c[3] for c in part], "RETRIEVAL_DOCUMENT")
            conn.executemany(
                "INSERT OR REPLACE INTO doc_vectors (src, doc_id, chunk_no, page, vec) VALUES (?,?,?,?,?)",
                [(c[0], doc_id, c[1], c[2], json.dumps(v)) for c, v in zip(part, vectors)])
            conn.commit()
            done += len(part)
        conn.execute("INSERT OR REPLACE INTO doc_vector_meta (doc_id, stamp) VALUES (?, ?)", (doc_id, stamps[doc_id]))
        conn.commit()
        _cache["version"] += 1
    return done


def _index(conn) -> list[tuple]:
    if _cache["index"] is None or _cache["built_at"] != _cache["version"]:
        _cache["index"] = [(int(d), int(s), n, p, json.loads(v)) for d, s, n, p, v in conn.execute(
            "SELECT doc_id, src, chunk_no, page, vec FROM doc_vectors")]
        _cache["built_at"] = _cache["version"]
    return _cache["index"]


def search(conn, q: str, allowed_ids: set[int] | None = None, k: int = 5) -> list[tuple[float, int, int, int | None, int | None]]:
    """Trả về [(điểm, doc_id, src, chunk_no, page)] cho từng tài liệu (đoạn gần nhất), chỉ tài liệu trong allowed_ids."""
    index = _index(conn)
    if not index or not q.strip():
        return []
    qv = _embed([q], "RETRIEVAL_QUERY")[0]
    best: dict[int, tuple] = {}
    for doc_id, src, chunk_no, page, vec in index:
        if allowed_ids is not None and doc_id not in allowed_ids:
            continue
        score = sum(a * b for a, b in zip(qv, vec))
        if score >= MIN_SCORE and (doc_id not in best or score > best[doc_id][0]):
            best[doc_id] = (score, doc_id, src, chunk_no, page)
    return sorted(best.values(), reverse=True)[:k]


def start_scheduler() -> None:
    """Đồng bộ vector nền định kỳ. TẮT MẶC ĐỊNH: bật bằng AZB_EMBED_SYNC=1 khi đã chấp nhận gửi nội dung tài liệu
    cho Gemini để tạo vector. Không có khoá Gemini thì không chạy."""
    if os.environ.get("AZB_EMBED_SYNC") != "1" or not available():
        return

    def loop() -> None:
        from .db import connect
        while True:
            try:
                with connect() as conn:
                    sync(conn)
            except Exception:  # lỗi mạng/quota: thử lại lần sau, không làm sập máy chủ
                pass
            time.sleep(SYNC_EVERY_S)

    threading.Thread(target=loop, daemon=True, name="azb-embed-sync").start()
