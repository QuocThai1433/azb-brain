"""Kho tài liệu: lưu file gốc, trích xuất văn bản, chia đoạn và đánh chỉ mục tìm kiếm.

Hỗ trợ: PDF (có lớp chữ), PDF scan (đọc bằng Claude), DOCX, XLSX/XLS, TXT/MD, âm thanh (gỡ băng bằng Gemini).
"""
import hashlib
import math
import os
import re
import sqlite3
import unicodedata
from pathlib import Path

from fastapi import HTTPException

from . import access, auth, guard
from .db import DB_PATH, connect, row, rows

UPLOAD_DIR = DB_PATH.parent / "uploads"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
AUDIO_MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".aac": "audio/aac",
              ".ogg": "audio/ogg", ".flac": "audio/flac"}
AUDIO_EXT = set(AUDIO_MIME)
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
IMAGE_EXT = set(IMAGE_MIME)
ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md"} | AUDIO_EXT | IMAGE_EXT
DOC_TYPES = {
    "quy_trinh": "Quy trình",
    "quy_dinh": "Quy định",
    "ram": "RAM phân nhiệm",
    "huong_dan": "Hướng dẫn công việc",
    "bieu_mau": "Biểu mẫu",
    "so_tay": "Sổ tay chất lượng",
    "website": "Website azb.vn",
    "khac": "Khác",
}
CHUNK_CHARS = 1500
CHUNK_OVERLAP = 200
MIN_CHARS_PER_PAGE = 40   # ít hơn mức này coi như trang scan, cần OCR
SCAN_PAGE_MAX_CHARS = 400  # trang có ảnh và ít chữ hơn mức này coi là trang scan
OCR_PAGES_PER_CALL = 20
OCR_PDF_PROMPT = (
    "Chép lại nguyên văn toàn bộ nội dung tài liệu này sang Markdown (tiếng Việt, giữ đúng dấu). "
    "Giữ cấu trúc tiêu đề, danh sách, bảng (dạng bảng Markdown), mã tài liệu, số hiệu phiên bản. "
    "Lưu đồ/sơ đồ: mô tả các bước và mũi tên dưới dạng danh sách đánh số. "
    "Đánh dấu đầu mỗi trang bằng dòng '--- Trang N ---'. Không tóm tắt, không bình luận."
)


def safe_filename(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE)[:120] or "file"


# ---------------- Trích xuất ----------------
def _pdf_pages(path: Path) -> tuple[list[str], int]:
    """Trả về (văn bản từng trang, số trang là ảnh scan: có ảnh nhưng ít chữ)."""
    import pymupdf
    with pymupdf.open(path) as doc:
        texts, scanned = [], 0
        for page in doc:
            text = page.get_text()
            texts.append(text)
            if len(text.strip()) < SCAN_PAGE_MAX_CHARS and page.get_images():
                scanned += 1
        return texts, scanned


def _docx_text(path: Path) -> str:
    import docx
    d = docx.Document(path)
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for t_i, table in enumerate(d.tables, 1):
        parts.append(f"\n[Bảng {t_i}]")
        for r in table.rows:
            cells = []
            for c in r.cells:  # ô gộp lặp lại – bỏ trùng liên tiếp
                if not cells or cells[-1] != c.text.strip():
                    cells.append(c.text.strip())
            parts.append(" | ".join(cells))
    return "\n".join(parts)


def _is_ole(path: Path) -> bool:
    """File Office đời cũ (.xls/.doc 97-2003) – có khi bị đổi đuôi thành .xlsx."""
    with open(path, "rb") as f:
        return f.read(8) == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _xls_text(path: Path) -> str:
    import xlrd
    try:
        wb = xlrd.open_workbook(path)
    except xlrd.biffh.XLRDError as e:
        raise RuntimeError(f"Không đọc được file Excel cũ (.xls) – có thể bị đặt mật khẩu. Hãy mở bằng Excel và "
                           f"lưu lại dạng .xlsx rồi tải lên lại. ({e})") from e
    parts = []
    for ws in wb.sheets():
        parts.append(f"\n[Sheet: {ws.name}]")
        for r in range(ws.nrows):
            vals = []
            for c in ws.row(r):
                v = c.value
                if c.ctype == xlrd.XL_CELL_NUMBER:
                    v = int(v) if v == int(v) else round(v, 4)
                elif c.ctype == xlrd.XL_CELL_DATE:
                    v = xlrd.xldate.xldate_as_datetime(v, wb.datemode).strftime("%d/%m/%Y")
                vals.append("" if v in (None, "") else str(v))
            if any(vals):
                parts.append(" | ".join(vals).rstrip(" |"))
    return "\n".join(parts)


def _xlsx_text(path: Path) -> str:
    import openpyxl
    if _is_ole(path):
        return _xls_text(path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"\n[Sheet: {ws.title}]")
        for r in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in r]
            if any(vals):
                parts.append(" | ".join(vals).rstrip(" |"))
    wb.close()
    return "\n".join(parts)


# ---------------- Xem trực tiếp trên web (Excel/Word -> HTML) ----------------
VIEW_MAX_ROWS = 5000
_VIEW_CSS = """body{font-family:system-ui,'Segoe UI',sans-serif;margin:0;color:#1d2433;background:#f5f7fb}
header{position:sticky;top:0;background:#0b3d7a;color:#fff;padding:12px 20px;z-index:2}
header h1{font-size:16px;margin:0 0 6px}header nav a{color:#cfe0ff;margin-right:14px;font-size:13px}
main{padding:16px 20px}section{margin-bottom:28px}h2{font-size:15px;color:#0b3d7a}
.wrap{overflow:auto;background:#fff;border:1px solid #dde3ee;border-radius:8px;max-height:80vh}
table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #e3e8f0;padding:4px 8px;white-space:nowrap;vertical-align:top}
th{background:#eef2f8;position:sticky;top:0;color:#56607a;font-weight:600}td.n{text-align:right}
.doc{background:#fff;border:1px solid #dde3ee;border-radius:8px;padding:24px 32px;max-width:900px;line-height:1.55}
.doc table td{white-space:normal}.note{color:#8a5a00;font-size:13px}pre{white-space:pre-wrap;font-family:inherit}"""


def _esc(v) -> str:
    import html
    return html.escape("" if v is None else str(v))


def _cell(v) -> tuple[str, bool]:
    import datetime
    if isinstance(v, datetime.datetime):
        return v.strftime("%d/%m/%Y" if not (v.hour or v.minute) else "%d/%m/%Y %H:%M"), False
    if isinstance(v, datetime.date):
        return v.strftime("%d/%m/%Y"), False
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return ("" if v is None else str(v)), isinstance(v, (int, float))


def _sheets_html(sheets: list[tuple[str, list[list]]]) -> tuple[str, str]:
    nav, body = [], []
    for i, (name, data) in enumerate(sheets):
        data = [r for r in data if any(c not in (None, "") for c in r)]
        width = max((len(r) for r in data), default=0)
        while width and all(len(r) < width or r[width - 1] in (None, "") for r in data):
            width -= 1
        note = f'<p class="note">Chỉ hiển thị {VIEW_MAX_ROWS} dòng đầu.</p>' if len(data) > VIEW_MAX_ROWS else ""
        trs = []
        for r_i, r in enumerate(data[:VIEW_MAX_ROWS], 1):
            tds = []
            for c in (list(r) + [None] * width)[:width]:
                text, num = _cell(c)
                tds.append(f'<td{" class=n" if num else ""}>{_esc(text)}</td>')
            trs.append(f"<tr><th>{r_i}</th>{''.join(tds)}</tr>")
        nav.append(f'<a href="#s{i}">{_esc(name)}</a>')
        body.append(f'<section id="s{i}"><h2>{_esc(name)}</h2>{note}<div class="wrap"><table>{"".join(trs) or "<tr><td>(trống)</td></tr>"}</table></div></section>')
    return "".join(nav) if len(sheets) > 1 else "", "".join(body)


def _docx_html(path: Path) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = docx.Document(path)
    out = []
    for el in d.element.body.iterchildren():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(el, d)
            if not p.text.strip():
                continue
            style = (p.style.name if p.style is not None else "") or ""
            m = re.match(r"(?:Heading|Title)\s*(\d?)", style)
            if m:
                lvl = min(int(m.group(1) or 1) + 1, 4)
                out.append(f"<h{lvl}>{_esc(p.text)}</h{lvl}>")
            else:
                runs = "".join(f"<b>{_esc(r.text)}</b>" if r.bold else _esc(r.text) for r in p.runs) or _esc(p.text)
                out.append(f"<p>{runs}</p>")
        elif tag == "tbl":
            trs = []
            for r in Table(el, d).rows:
                cells, prev = [], None
                for c in r.cells:
                    if c._tc is prev:  # ô gộp ngang
                        continue
                    prev = c._tc
                    cells.append(f"<td>{_esc(c.text).replace(chr(10), '<br>')}</td>")
                trs.append(f"<tr>{''.join(cells)}</tr>")
            out.append(f'<div class="wrap" style="max-height:none;margin:12px 0"><table>{"".join(trs)}</table></div>')
    return f'<div class="doc">{"".join(out) or "(Tài liệu trống)"}</div>'


def render_html(path: Path, title: str, fallback_text: str | None = None) -> str:
    """Trang HTML tĩnh (không script) để xem file Excel/Word ngay trên trình duyệt."""
    ext = path.suffix.lower()
    nav = ""
    try:
        if ext in (".xlsx", ".xlsm", ".xls") and _is_ole(path):
            import xlrd
            wb = xlrd.open_workbook(path)
            nav, body = _sheets_html([(ws.name, [ws.row_values(r) for r in range(ws.nrows)]) for ws in wb.sheets()])
        elif ext in (".xlsx", ".xlsm"):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            nav, body = _sheets_html([(ws.title, [list(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets])
            wb.close()
        elif ext == ".docx":
            body = _docx_html(path)
        else:
            raise ValueError
    except Exception:  # định dạng khác hoặc file lỗi -> hiện phần chữ đã trích
        body = f'<div class="doc"><pre>{_esc(fallback_text or "Không hiển thị được file này, hãy tải về.")}</pre></div>'
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{_esc(title)}</title><style>{_VIEW_CSS}</style></head><body>"
            f"<header><h1>{_esc(title)}</h1><nav>{nav}</nav></header><main>{body}</main></body></html>")


def _ocr_pdf_with_ai(path: Path) -> tuple[list[str], str]:
    """Đọc PDF scan bằng Claude theo từng cụm trang. Trả về (danh sách văn bản theo cụm, ghi chú)."""
    import base64

    import pymupdf

    from .ai import ANTHROPIC_MODEL, client, has_anthropic, log_usage, message_text

    if not has_anthropic():
        raise RuntimeError("PDF dạng scan – cần khoá Anthropic API để đọc chữ (OCR).")
    claude = client(timeout_s=600)
    prompt = OCR_PDF_PROMPT
    out, notes = [], []
    with pymupdf.open(path) as src:
        total = len(src)
        for start in range(0, total, OCR_PAGES_PER_CALL):
            end = min(start + OCR_PAGES_PER_CALL, total) - 1
            part = pymupdf.open()
            part.insert_pdf(src, from_page=start, to_page=end)
            data = base64.standard_b64encode(part.tobytes()).decode("ascii")
            part.close()
            with claude.messages.stream(
                model=ANTHROPIC_MODEL, max_tokens=64000, output_config={"effort": "low"},
                messages=[{"role": "user", "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
                    {"type": "text", "text": prompt + f" Cụm này bắt đầu từ trang {start + 1}."}]}],
            ) as stream:
                msg = stream.get_final_message()
            log_usage("ocr_pdf", ANTHROPIC_MODEL, getattr(msg, "usage", None), f"{path.name} (trang {start + 1}-{end + 1})")
            if msg.stop_reason == "refusal":
                raise RuntimeError(f"Mô hình từ chối đọc trang {start + 1}-{end + 1}.")
            if msg.stop_reason == "max_tokens":
                notes.append(f"Trang {start + 1}-{end + 1} có thể bị thiếu nội dung cuối.")
            out.append(message_text(msg))
    return out, " ".join(notes)


def _transcribe_audio(path: Path) -> tuple[str, str]:
    """Gỡ băng file âm thanh bằng Gemini (tải lên qua Files API). Trả về (văn bản, ghi chú)."""
    import time

    from google.genai import errors, types

    from .ai import gemini_client, has_gemini

    GEMINI_MODEL = os.environ.get("AZB_GEMINI_MODEL", "gemini-3.8-flash")  # Anthropic chưa nhận âm thanh nên gỡ băng vẫn dùng Gemini
    if not has_gemini():
        raise RuntimeError("File âm thanh – cần khoá Gemini API (GEMINI_API_KEY) để gỡ băng.")
    gemini = gemini_client(timeout_s=900)
    prompt = (
        "Gỡ băng nguyên văn file ghi âm này (chủ yếu tiếng Việt, giữ đúng dấu; từ tiếng Anh giữ nguyên). "
        "Mỗi đoạn bắt đầu bằng mốc thời gian [mm:ss]. Nếu nhận ra nhiều người nói thì ghi 'Người 1:', 'Người 2:'... "
        "Tên riêng, số liệu, mã tài liệu chép đúng như nghe được; chỗ nghe không rõ ghi [không rõ]. "
        "Không tóm tắt, không bình luận, không thêm nội dung không có trong ghi âm."
    )
    f = gemini.files.upload(file=path, config=types.UploadFileConfig(mime_type=AUDIO_MIME[path.suffix.lower()]))
    try:
        for _ in range(60):  # chờ Google xử lý file xong (tối đa ~2 phút)
            if getattr(f.state, "name", "") != "PROCESSING":
                break
            time.sleep(2)
            f = gemini.files.get(name=f.name)
        if getattr(f.state, "name", "") == "FAILED":
            raise RuntimeError("Google không xử lý được file âm thanh này.")
        for attempt in range(3):  # model hay báo 503 "quá tải" tạm thời
            try:
                msg = gemini.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[f, prompt],
                    config=types.GenerateContentConfig(
                        max_output_tokens=64000,
                        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                    ),
                )
                break
            except errors.ServerError:
                if attempt == 2:
                    raise
                time.sleep(10 * (attempt + 1))
    finally:
        try:
            gemini.files.delete(name=f.name)
        except Exception:
            pass
    reason = msg.candidates[0].finish_reason.name if msg.candidates and msg.candidates[0].finish_reason else ""
    if (msg.prompt_feedback and msg.prompt_feedback.block_reason) or reason in ("SAFETY", "PROHIBITED_CONTENT"):
        raise RuntimeError("Mô hình từ chối gỡ băng file này.")
    note = "Phần cuối ghi âm có thể bị thiếu." if reason == "MAX_TOKENS" else ""
    return msg.text or "", note


IMAGE_INLINE_MAX = 5 * 1024 * 1024  # Claude nhận ảnh tối đa 5 MB mỗi ảnh


def _read_image(path: Path) -> str:
    """Đọc ảnh (ảnh chụp màn hình, biểu đồ, giấy tờ, bảng) bằng Claude: chép chữ + mô tả những gì thấy."""
    import base64

    from .ai import ANTHROPIC_MODEL, client, has_anthropic, log_usage, message_text

    if not has_anthropic():
        raise RuntimeError("File ảnh – cần khoá Anthropic API để đọc nội dung ảnh.")
    if path.stat().st_size > IMAGE_INLINE_MAX:
        raise RuntimeError("Ảnh quá lớn (trên 5 MB) – hãy giảm kích thước rồi tải lại.")
    prompt = (
        "Đọc bức ảnh này cho một trợ lý doanh nghiệp (tiếng Việt). (1) Chép lại nguyên văn mọi chữ nhìn thấy, giữ đúng dấu, "
        "bảng thì dựng lại dạng bảng Markdown, giữ nguyên số liệu. (2) Sau đó mô tả ngắn gọn phần không phải chữ "
        "(biểu đồ, sơ đồ, hình, giao diện phần mềm) và nêu số liệu/ý chính thấy được. Chữ mờ không đọc được ghi [không rõ]. "
        "Chỉ nêu những gì có trong ảnh, không suy đoán thêm."
    )
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    msg = client(timeout_s=300).messages.create(
        model=ANTHROPIC_MODEL, max_tokens=16000, output_config={"effort": "low"},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": IMAGE_MIME[path.suffix.lower()], "data": data}},
            {"type": "text", "text": prompt}]}])
    log_usage("ocr_image", ANTHROPIC_MODEL, getattr(msg, "usage", None), path.name)
    if msg.stop_reason == "refusal":
        raise RuntimeError("Mô hình từ chối đọc ảnh này.")
    return message_text(msg)


def extract(path: Path, use_ocr: bool = True) -> dict:
    """Trả về {status, content, pages: [(page_no|None, text)], page_count, note}."""
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        if not use_ocr:
            return {"status": "needs_ocr", "pages": [], "page_count": None, "note": "File ảnh, chưa đọc."}
        text = _read_image(path)
        if not text.strip():
            return {"status": "failed", "pages": [], "page_count": None, "note": "Không đọc được nội dung nào từ ảnh."}
        return {"status": "ok", "pages": [(None, text)], "page_count": None,
                "note": "Đọc bằng AI từ ảnh – số liệu quan trọng nên đối chiếu bản gốc."}
    if ext in AUDIO_EXT:
        if not use_ocr:
            return {"status": "needs_ocr", "pages": [], "page_count": None, "note": "File âm thanh, chưa gỡ băng."}
        text, note = _transcribe_audio(path)
        if not text.strip():
            return {"status": "failed", "pages": [], "page_count": None, "note": "Không nghe ra nội dung lời nói nào."}
        return {"status": "ok", "pages": [(None, text)], "page_count": None,
                "note": ("Gỡ băng bằng AI – tên riêng, số liệu nên nghe lại để đối chiếu. " + note).strip()}
    if ext == ".pdf":
        pages, scanned = _pdf_pages(path)
        text_chars = sum(len(p.strip()) for p in pages)
        # PDF scan đôi khi vẫn chứa vài dòng chữ lẻ (chữ ký, nhãn) → đủ ngưỡng nhưng thiếu nội dung chính
        if pages and text_chars / len(pages) >= MIN_CHARS_PER_PAGE and scanned * 2 <= len(pages):
            return {"status": "ok", "pages": [(i + 1, p) for i, p in enumerate(pages)], "page_count": len(pages), "note": None}
        if not use_ocr:
            return {"status": "needs_ocr", "pages": [], "page_count": len(pages),
                    "note": "PDF dạng ảnh scan, chưa có lớp chữ."}
        parts, note = _ocr_pdf_with_ai(path)
        return {"status": "ok", "pages": [(None, p) for p in parts], "page_count": len(pages),
                "note": ("Đọc bằng AI từ bản scan – nên đối chiếu bản gốc. " + note).strip()}
    if ext == ".docx":
        return {"status": "ok", "pages": [(None, _docx_text(path))], "page_count": None, "note": None}
    if ext in (".xlsx", ".xls"):
        return {"status": "ok", "pages": [(None, _xlsx_text(path))], "page_count": None, "note": None}
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"status": "ok", "pages": [(None, text)], "page_count": None, "note": None}


def chunk(pages: list[tuple[int | None, str]]) -> list[tuple[int | None, str]]:
    chunks = []
    for page_no, text in pages:
        text = re.sub(r"[ \t]+", " ", text).strip()
        start = 0
        while start < len(text):
            end = min(start + CHUNK_CHARS, len(text))
            if end < len(text):  # cắt ở xuống dòng / dấu câu gần nhất cho tự nhiên
                cut = max(text.rfind("\n", start + CHUNK_CHARS // 2, end), text.rfind(". ", start + CHUNK_CHARS // 2, end))
                if cut > start:
                    end = cut + 1
            chunks.append((page_no, text[start:end].strip()))
            if end >= len(text):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    return [c for c in chunks if c[1]]


def _friendly_error(e: Exception) -> str:
    """Lỗi API thô (dài, tiếng Anh, có JSON) → câu ngắn dễ hiểu; giữ mã 429/503 để retry_ocr nhận ra."""
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code == 429 or "RESOURCE_EXHAUSTED" in str(e):
        return "AI đang hết hạn mức đọc ảnh/scan (429). Tài liệu chưa đọc được, hãy thử lại sau ít phút."
    if code in (500, 502, 503, 504, 529):
        return f"AI đang quá tải ({code}). Hãy thử lại sau ít phút."
    text = str(e)
    return text if len(text) <= 200 else text[:200] + "…"


def _file_hash(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def _reuse_twin(doc_id: int, doc: dict, digest: str) -> bool:
    """File này đã được đọc xong ở một tài liệu khác (cùng nội dung từng byte) thì chép kết quả sang, khỏi gọi AI lần nữa.
    Người tải đang giữ chính file đó nên không có thông tin nào lộ ra. True = đã dùng lại."""
    with connect() as conn:
        twin = None
        # tài liệu cũ chưa có hash: chỉ băm những file cùng dung lượng (ít) rồi lưu lại cho lần sau
        for c in rows(conn, "SELECT id, stored_path, content_hash FROM documents WHERE id != ? AND size_bytes = ?"
                            " AND extract_status = 'ok' AND content IS NOT NULL AND content != '' ORDER BY id",
                      (doc_id, doc["size_bytes"])):
            h = c["content_hash"]
            if not h and c["stored_path"]:
                h = _file_hash(Path(c["stored_path"]))
                if h:
                    conn.execute("UPDATE documents SET content_hash = ? WHERE id = ?", (h, c["id"]))
            if h == digest:
                twin = c
                break
        if not twin:
            return False
        src = row(conn, "SELECT content, page_count, char_count, extract_note FROM documents WHERE id = ?", (twin["id"],))
        conn.execute("DELETE FROM doc_page_review WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) SELECT text, ?, chunk_no, page FROM doc_chunks WHERE doc_id = ?",
                     (doc_id, twin["id"]))
        note = ((src["extract_note"] or "") + " (Dùng lại kết quả đã đọc của file trùng, không gọi AI lần nữa.)").strip()
        conn.execute("UPDATE documents SET extract_status = 'ok', extract_note = ?, content = ?, page_count = ?, char_count = ?"
                     " WHERE id = ?", (note, src["content"], src["page_count"], src["char_count"], doc_id))
    return True


def process_document(doc_id: int, use_ocr: bool = True) -> None:
    """Trích xuất + đánh chỉ mục một tài liệu (chạy nền sau khi tải lên)."""
    with connect() as conn:
        doc = row(conn, "SELECT * FROM documents WHERE id = ?", (doc_id,))
        if not doc:
            return
        conn.execute("UPDATE documents SET extract_status = 'processing', extract_note = NULL WHERE id = ?", (doc_id,))
    path = Path(doc["stored_path"])
    digest = _file_hash(path) if doc["stored_path"] else None
    if digest:
        with connect() as conn:
            conn.execute("UPDATE documents SET content_hash = ? WHERE id = ?", (digest, doc_id))
        # đọc lại một file đã 'ok' là người dùng chủ ý đọc lại (bản đọc cũ chưa ưng): không dùng lại bản của file trùng
        if doc["extract_status"] != "ok" and _reuse_twin(doc_id, doc, digest):
            return
    from .ai import usage_user  # tiền OCR/gỡ băng tính cho chủ file (hoặc người tải lên) để áp trần chi tiêu cá nhân
    token = usage_user.set(doc.get("owner_id") or doc.get("uploaded_by"))
    try:
        result = extract(path, use_ocr=use_ocr)
    except Exception as e:
        with connect() as conn:
            conn.execute("UPDATE documents SET extract_status = 'failed', extract_note = ? WHERE id = ?", (_friendly_error(e), doc_id))
        return
    finally:
        usage_user.reset(token)
    content = "\n\n".join(p for _, p in result["pages"])
    suspicious = guard.scan(content)
    if suspicious:  # giống chỉ dẫn ép AI: AI vẫn đọc được nhưng phần đó bị vô hiệu hoá; báo người quản lý kiểm tra file
        warn = f"⚠ Phát hiện {suspicious} đoạn giống chỉ dẫn ép AI làm sai; các đoạn này bị vô hiệu hoá khi AI đọc. Hãy kiểm tra file."
        result["note"] = f"{result['note']} {warn}" if result.get("note") else warn
    with connect() as conn:
        conn.execute("DELETE FROM doc_page_review WHERE doc_id = ?", (doc_id,))  # đọc lại → kết quả đối chiếu cũ hết hiệu lực
        conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        for i, (page_no, text) in enumerate(chunk(result["pages"])):
            conn.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) VALUES (?,?,?,?)",
                         (text, doc_id, i, page_no))
        conn.execute(
            "UPDATE documents SET extract_status = ?, extract_note = ?, content = ?, page_count = ?, char_count = ? WHERE id = ?",
            (result["status"], result["note"], content or None, result["page_count"], len(content), doc_id),
        )


QUOTA_MARKERS = ("429", "quá tải")  # lỗi hết hạn mức / Gemini quá tải: đọc tiếp cũng sẽ lỗi y hệt


def reprocess_candidates(conn: sqlite3.Connection, user: dict, include_ocr: bool = False) -> list[tuple[int, str]]:
    """Tài liệu user được phép đọc lại hàng loạt: file lỗi (failed), thêm file chưa đọc được bằng OCR nếu include_ocr.
    Trả về (id, trạng thái cũ) để khi dừng giữa chừng còn trả đúng trạng thái cho các file chưa đọc."""
    statuses = ("failed", "needs_ocr") if include_ocr else ("failed",)
    where, params = access.doc_scope(conn, user)
    found = rows(conn, "SELECT d.id, d.extract_status, d.unit_id, d.access_level FROM documents d"
                       f" WHERE {where} AND d.access_level != 'private' AND d.extract_status IN ({','.join('?' * len(statuses))})"
                       " ORDER BY d.id", [*params, *statuses])
    out = []
    for d in found:
        try:
            access.check_doc_write(conn, user, d["id"])
            auth.check_unit_write(conn, user, d["unit_id"])
        except HTTPException:
            continue  # không có quyền với file này: bỏ qua, không báo lỗi cả lô
        out.append((d["id"], d["extract_status"]))
    return out


def reprocess_many(queue: list[tuple[int, str]]) -> None:
    """Đọc lại nối tiếp (chạy nền). Gặp hết hạn mức AI thì dừng và trả các file còn lại về trạng thái cũ để đọc lại sau."""
    for i, (doc_id, old_status) in enumerate(queue):
        process_document(doc_id)
        with connect() as conn:
            cur = row(conn, "SELECT extract_status, extract_note FROM documents WHERE id = ?", (doc_id,)) or {}
            if cur.get("extract_status") == "failed" and any(m in (cur.get("extract_note") or "") for m in QUOTA_MARKERS):
                for rest_id, rest_status in queue[i + 1:]:
                    conn.execute("UPDATE documents SET extract_status = ? WHERE id = ? AND extract_status = 'pending'",
                                 (rest_status, rest_id))
                return


# ---------------- Đối chiếu từng trang với bản gốc ----------------
PAGE_MARKER = re.compile(r"^\s*-{2,}\s*Trang\s+(\d+)\s*-{2,}\s*$", re.M | re.I)


def split_pages(content: str, page_count: int | None) -> dict[int, str]:
    """Tách văn bản đã lưu theo dòng '--- Trang N ---'. PDF dài được đọc theo cụm 20 trang và AI hay đánh số lại từ 1
    ở mỗi cụm, nên khi số trang tụt xuống thì cộng dồn để ra số trang thật."""
    marks = list(PAGE_MARKER.finditer(content or ""))
    if not marks:
        return {1: (content or "").strip()} if page_count == 1 else {}
    pages, offset, prev = {}, 0, 0
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(content)
        n = int(m.group(1))
        if n < prev:
            offset += prev
        prev = n
        pages[n + offset] = content[m.end():end].strip()
    return pages


# PDF do AI đọc: chỉ nhánh OCR (_ocr_pdf_with_ai) mới đặt ghi chú cho PDF 'ok'; PDF có lớp chữ để note = NULL.
# Nhận diện theo cấu trúc này, không theo chữ trong ghi chú (ghi chú có thể viết khác nhau qua các phiên bản).
def relink_uploads(conn: sqlite3.Connection) -> int:
    """Đường dẫn file lưu tuyệt đối nên hỏng khi chép dữ liệu sang máy/thư mục khác: file không còn ở stored_path nhưng
    có trong UPLOAD_DIR cùng tên (`<id>_<tên>`) thì trỏ lại. Chạy lại nhiều lần vẫn an toàn. Trả về số bản ghi đã sửa."""
    fixed = 0
    for d in rows(conn, "SELECT id, stored_path FROM documents WHERE stored_path IS NOT NULL AND stored_path != ''"):
        old = d["stored_path"]
        if Path(old).is_file():
            continue
        name = re.split(r"[\\/]", old)[-1]  # đường dẫn Windows của máy khác vẫn tách được trên mọi hệ điều hành
        new = UPLOAD_DIR / name
        if name and new.is_file():
            conn.execute("UPDATE documents SET stored_path = ? WHERE id = ?", (str(new), d["id"]))
            fixed += 1
    return fixed


AI_READ_PDF_SQL = ("extract_status = 'ok' AND extract_note IS NOT NULL AND lower(stored_path) LIKE '%.pdf'"  # cùng tiêu chí đuôi file với API đối chiếu
                   " AND doc_type != 'website'")  # nội dung website đã chuẩn, không cần đối chiếu


def reviewable_ids(conn: sqlite3.Connection) -> set[int]:
    """PDF đọc bằng AI mà mở được màn đối chiếu: còn file PDF gốc. Văn bản thiếu đánh dấu trang vẫn đối chiếu được
    theo cả file (cùng điều kiện với API đối chiếu)."""
    out = set()
    for d in rows(conn, f"SELECT id, stored_path FROM documents WHERE {AI_READ_PDF_SQL} AND content IS NOT NULL"):
        path = Path(d["stored_path"] or "")
        if path.suffix.lower() == ".pdf" and path.is_file():
            out.add(d["id"])
    return out


def save_whole_review(conn: sqlite3.Connection, doc_id: int, user_id: int, text: str | None) -> str:
    """Đối chiếu cả file khi văn bản không có đánh dấu trang. text=None hoặc giống bản cũ → xác nhận đúng; khác → thay toàn bộ
    văn bản và đánh chỉ mục lại. Mọi trang của PDF được ghi là đã đối chiếu. Trả về 'verified' hoặc 'edited'."""
    d = row(conn, "SELECT content, page_count FROM documents WHERE id = ?", (doc_id,))
    status = "verified"
    if text is not None and text.strip() != (d["content"] or "").strip():
        status = "edited"
        content = text.strip()
        conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        for i, (pn, t) in enumerate(chunk([(None, content)])):
            conn.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) VALUES (?,?,?,?)", (t, doc_id, i, pn))
        conn.execute("UPDATE documents SET content = ?, char_count = ? WHERE id = ?", (content, len(content), doc_id))
    for n in range(1, (d["page_count"] or 1) + 1):
        conn.execute("INSERT INTO doc_page_review (doc_id, page_no, status, reviewed_by) VALUES (?,?,?,?) "
                     "ON CONFLICT(doc_id, page_no) DO UPDATE SET status = excluded.status, reviewed_by = excluded.reviewed_by,"
                     " reviewed_at = datetime('now','localtime')", (doc_id, n, status, user_id))
    return status


def save_page_review(conn: sqlite3.Connection, doc_id: int, page_no: int, user_id: int, text: str | None) -> str:
    """Ghi kết quả đối chiếu một trang. text=None → người duyệt xác nhận đúng; có text khác bản cũ → sửa trang đó.
    Văn bản tài liệu được ghi lại với số trang chuẩn và đánh chỉ mục lại. Trả về 'verified' hoặc 'edited'."""
    d = row(conn, "SELECT content, page_count FROM documents WHERE id = ?", (doc_id,))
    pages = split_pages(d["content"], d["page_count"])
    if page_no not in pages:
        raise ValueError("Không có trang này trong văn bản đã lưu")
    status = "verified"
    if text is not None and text.strip() != pages[page_no].strip():
        pages[page_no] = text.strip()
        status = "edited"
        content = "\n\n".join(f"--- Trang {n} ---\n\n{t}" for n, t in sorted(pages.items()))
        conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        for i, (pn, t) in enumerate(chunk(sorted(pages.items()))):
            conn.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) VALUES (?,?,?,?)", (t, doc_id, i, pn))
        conn.execute("UPDATE documents SET content = ?, char_count = ? WHERE id = ?", (content, len(content), doc_id))
    conn.execute("INSERT INTO doc_page_review (doc_id, page_no, status, reviewed_by) VALUES (?,?,?,?) "
                 "ON CONFLICT(doc_id, page_no) DO UPDATE SET status = excluded.status, reviewed_by = excluded.reviewed_by,"
                 " reviewed_at = datetime('now','localtime')", (doc_id, page_no, status, user_id))
    return status


# ---------------- Tìm kiếm ----------------
def _fold(s: str) -> str:
    """Bỏ dấu + hạ chữ thường để so khớp tên tài liệu không cần gõ dấu."""
    s = unicodedata.normalize("NFD", (s or "").lower().replace("đ", "d"))
    return "".join(c for c in s if not unicodedata.combining(c))


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", (s or "")).lower()


def _terms(q: str) -> list[tuple[str, bool]]:
    """Tách từ khoá. Từ gõ có dấu ("vẻ") phải khớp đúng dấu; từ gõ không dấu ("ve") khớp mọi dấu."""
    out = []
    for w in re.findall(r"\w+", unicodedata.normalize("NFC", q), flags=re.UNICODE):
        if len(w) > 1:
            raw = w.lower()
            out.append((raw, _fold(raw) != raw))
    return out


def _word_sets(text: str) -> tuple[set, set]:
    """(tập từ đã bỏ dấu, tập từ giữ nguyên dấu) của một đoạn văn bản."""
    return set(re.findall(r"\w+", _fold(text))), set(re.findall(r"\w+", _nfc(text)))


def _matches(terms: list[tuple[str, bool]], folded: set, raw: set) -> list[bool]:
    return [(w in raw) if strict else (_fold(w) in folded) for w, strict in terms]


def _make_snippet(content: str, terms: list[tuple[str, bool]], radius: int = 70) -> str:
    """Trích đoạn quanh chỗ khớp đầu tiên (đúng quy tắc dấu của từng từ khoá), trả về văn bản gốc."""
    content = unicodedata.normalize("NFC", content)
    flats = {}  # strict -> (ký tự, vị trí gốc)
    for strict, conv in ((False, _fold), (True, str.lower)):
        whole = conv(content)
        if len(whole) == len(content):  # đường nhanh: chuyển 1-1 theo ký tự, vị trí gốc = chỉ số
            flats[strict] = (whole, range(len(content)))
            continue
        chars, pos = [], []
        for i, c in enumerate(content):
            for ch in conv(c):
                chars.append(ch)
                pos.append(i)
        flats[strict] = ("".join(chars), pos)
    first = None
    if len(terms) > 1:  # ưu tiên chỗ khớp nguyên cụm ("vẻ đẹp") trước khi xét từng từ rời
        strict = any(s for _, s in terms)
        flat = flats[strict][0]
        phrase = r"\W+".join(re.escape(w if strict else _fold(w)) for w, _ in terms)
        m = re.search(rf"(?<!\w){phrase}(?!\w)", flat)
        if m:
            first = flats[strict][1][m.start()]
    for w, strict in terms:
        if first is not None:
            break
        flat = flats[strict][0]
        needle = w if strict else _fold(w)
        m = re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", flat)
        if m:
            pos = flats[strict][1][m.start()]
            first = pos if first is None else min(first, pos)
    if first is None:
        return ""
    start, end = max(0, first - radius), min(len(content), first + radius)
    text = " ".join(content[start:end].split())
    return ("… " if start > 0 else "") + text + (" …" if end < len(content) else "")


_WORDSET_CACHE: dict = {}


def search_docs(conn: sqlite3.Connection, q: str, limit: int = 30, unit_id: int | None = None,
                allowed_ids: set[int] | None = None, in_content: bool = False) -> list[dict]:
    """Tìm tài liệu theo tên (mã + tiêu đề + tên file); `in_content=True` thì tìm thêm trong nội dung.
    Khớp tên xếp trước, nội dung sau; kèm `snippet` là đoạn trích quanh chỗ khớp.
    Từ gõ có dấu thì khớp đúng dấu, gõ không dấu thì khớp mọi dấu."""
    terms = _terms(q)
    if not terms:
        return []
    sql = ("SELECT d.id, d.unit_id, u.name AS unit_name, d.process_id, d.title, d.doc_type, d.code, d.version, d.filename,"
           " d.size_bytes, d.page_count, d.char_count, d.extract_status, d.extract_note, d.uploaded_at, d.access_level, d.content"
           " FROM documents d LEFT JOIN units u ON u.id = d.unit_id")
    params: list = []
    if unit_id:
        sql += f" WHERE {access.in_unit_sql()}"
        params += [unit_id, unit_id]
    by_name, by_content, by_related, seen = [], [], [], set()
    concepts = _concepts(q)  # khi quên tên file: tên khớp theo cách gọi tương đương ("sơ đồ tổ chức" ~ "sơ đồ điều hành")
    for d in rows(conn, sql + " ORDER BY d.uploaded_at DESC", params):
        content = d.pop("content", None) or ""
        if allowed_ids is not None and d["id"] not in allowed_ids:
            continue
        key = (_fold(d["title"]), d["unit_id"])  # cùng tên + cùng đơn vị = bản trùng, giữ bản mới nhất
        if key in seen:
            continue
        nk = ("n", d["id"], d["title"], d["code"], d["filename"])
        if nk not in _WORDSET_CACHE:
            _WORDSET_CACHE[nk] = _word_sets(f"{d['code'] or ''} {d['title']} {d['filename'] or ''}")
        n_fold, n_raw = _WORDSET_CACHE[nk]
        name_ok = _matches(terms, n_fold, n_raw)
        in_name = all(name_ok)
        hit_content = False
        if not in_name and concepts:
            padded = _title_padded(d)
            lv = [_level(c, padded) for c in concepts]
            if sum(1 for x in lv if x) * 2 >= len(concepts) and any(lv):
                seen.add(key)
                d["in_name"] = True
                d["_content"] = ""
                by_related.append((-sum(lv) / len(concepts), d))
                continue
        if in_content and not in_name and content:
            ck =(d["id"], len(content), d["uploaded_at"])
            if ck not in _WORDSET_CACHE:  # chuẩn hoá cả nội dung rất tốn: làm 1 lần, các lần gõ sau dùng lại
                _WORDSET_CACHE[ck] = _word_sets(content)
            c_fold, c_raw = _WORDSET_CACHE[ck]
            hit_content = all(a or b for a, b in zip(name_ok, _matches(terms, c_fold, c_raw)))
        if in_name or hit_content:
            seen.add(key)
            d["in_name"] = in_name
            d["_content"] = "" if in_name else content
            (by_name if in_name else by_content).append(d)  # hit_content chỉ có khi in_content=True
    by_related.sort(key=lambda t: t[0])
    out = (by_name + [d for _, d in by_related] + by_content)[:limit]
    for d in out:  # đoạn trích chỉ làm cho các kết quả được hiển thị
        c = d.pop("_content")
        d["snippet"] = _make_snippet(c, terms) if c else ""
    return out


# ---------------- Tìm kiếm cho trợ lý AI ----------------
# Mục tiêu: tìm ra tài liệu dù tên file / cách viết khác câu hỏi (có dấu - không dấu, "QĐ" - "QD", "QT01" - "quy trình",
# "ngân sách" - "dự toán"...), không để vài file lớn hoặc bản trùng chiếm hết kết quả, và cho AI biết mức độ khớp
# để không kết luận bừa.
_LETTER_DIGIT = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")


def fold_words(s: str) -> list[str]:
    """Bỏ hết dấu (kể cả đ), chữ thường, tách mã chữ-số: "QĐ01.BTC" -> ["qd", "01", "btc"]."""
    return re.findall(r"[a-z0-9]+", _LETTER_DIGIT.sub(" ", _fold(unicodedata.normalize("NFC", s or ""))))


# Nhóm cách gọi tương đương (đã bỏ dấu). Một từ khoá thuộc nhóm nào thì tìm cả các cách gọi còn lại trong nhóm.
# Thêm nhóm mới ở đây khi phát hiện công ty dùng tên gọi khác cho cùng một việc.
SYNONYM_GROUPS = [
    "quy trinh|qt|process|procedure",
    "quy dinh|qd|quyet dinh|quy che|chinh sach|policy",
    "huong dan|hdcv|huong dan cong viec|instruction",
    "bieu mau|bm|mau bieu|form|template",
    "ma tran phan cong|ma tran trach nhiem|phan nhiem|phan cong nhiem vu|ram|raci",
    "ngan sach|du toan|ke hoach chi|budget",
    "ke hoach|kh|plan",
    "thu chi|thu va chi",
    "chi phi|gia thanh|cost",
    "kiem soat|quan ly|giam sat|control",
    "thanh toan|quyet toan|giai ngan|tam ung|hoan ung|payment",
    "nha thau phu|thau phu|ntp|to doi|doi khoan|subcontractor",
    "nha cung cap|ncc|vendor|supplier",
    "mua hang|dat hang|mua sam|purchase",
    "vat tu|vat lieu|material",
    "an toan|hsse|hse|atld|an toan lao dong|safety",
    "chat luong|qaqc|qa qc|quality",
    "nhan su|hcns|nhan vien|hr",
    "tuyen dung|tuyen nhan su|recruitment",
    "ke toan|tckt|tai chinh ke toan|accounting",
    "hop dong|contract",
    "may moc thiet bi|mmtb|thiet bi|equipment",
    "doanh thu|doanh so|revenue",
    "muc tieu|chi tieu|kpi|kri|wig|okr|target",
    "thiet ke|tkkt|design",
    "dau thau|du thau|tender",
    "bao hanh|bao tri|warranty",
    "danh gia noi bo|kiem toan noi bo|audit",
    "dao tao|training",
    "tong giam doc|tgd|ceo",
    "hoa don|invoice",
    "cong no|qlcn",
    "bao cao|report",
    "phe duyet|duyet|ky duyet|approve",
    "ho so nang luc|hsnl|profile",
    "so do to chuc|so do dieu hanh|so do|co cau to chuc|bo may to chuc|org chart|orgchart",
]
_SYN_INDEX: dict[tuple, list[tuple]] = {}
for _g in SYNONYM_GROUPS:
    _alts = [tuple(p.split()) for p in _g.split("|")]
    for _p in _alts:
        _SYN_INDEX[_p] = _alts
_SYN_MAX = max(len(p) for p in _SYN_INDEX)

# Từ / cụm từ không mang nội dung tìm kiếm (đã bỏ dấu). Không đưa từ có nghĩa nghiệp vụ vào đây: từ đơn như "chi", "ke",
# "noi" có nghĩa riêng (thu chi, kế hoạch, nội bộ) nên chỉ bỏ khi nằm trong cụm vô nghĩa ("chi tiet", "liet ke"...).
_STOP = {"la", "gi", "cua", "nao", "cho", "toi", "biet", "ve", "va", "cac", "nhung", "nhu", "the", "thi", "hay", "co",
         "khong", "duoc", "o", "tai", "trong", "voi", "mot", "nay", "do", "de", "se", "da", "dang", "bi", "boi", "tu",
         "den", "theo", "ra", "vao", "hien", "hoi", "giup", "xin", "lam", "sao", "phong", "ban", "khoi", "cty", "azb",
         "can", "phai", "muon", "xem"}
_STOP_PHRASES = {tuple(p.split()) for p in (
    "chi tiet", "liet ke", "tom tat", "noi dung", "vui long", "bao nhieu", "tim kiem", "cong ty", "hien nay",
    "ton tai", "cu the", "nhu the nao", "the nao")}
_WEBSITE = "website"
MAX_CHUNKS_PER_DOC = 3


def _concepts(q: str) -> list[dict]:
    """Tách câu tìm kiếm thành các "ý": mỗi ý là một cụm từ cùng các cách gọi tương đương."""
    words, out, i = fold_words(q), [], 0
    while i < len(words):
        stop = next((n for n in (3, 2) if tuple(words[i:i + n]) in _STOP_PHRASES), 0)
        if stop:
            i += stop
            continue
        for n in range(min(_SYN_MAX, len(words) - i), 0, -1):
            phrase = tuple(words[i:i + n])
            if phrase in _SYN_INDEX:
                out.append({"orig": phrase, "alts": _SYN_INDEX[phrase]})
                i += n
                break
        else:
            w = words[i]
            if w not in _STOP and (len(w) > 1 or w.isdigit()):
                out.append({"orig": (w,), "alts": [(w,)]})
            i += 1
    seen, uniq = set(), []
    for c in out:
        key = tuple(sorted(c["alts"]))
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq


def _fts_expr(alts: list[tuple]) -> str:
    return "(" + " OR ".join('"' + " ".join(p) + '"' for p in alts) + ")"


def _level(c: dict, padded: str) -> float:
    """1 = có đúng từ khoá gốc, 0.7 = chỉ có cách gọi tương đương, 0 = không có."""
    if " " + " ".join(c["orig"]) + " " in padded:
        return 1.0
    return 0.7 if any(" " + " ".join(p) + " " in padded for p in c["alts"]) else 0.0


def _doc_stamp(d: dict) -> str:
    return "|".join(str(d[k]) for k in ("title", "code", "filename", "char_count", "page_count", "extract_status",
                                         "uploaded_at"))


_TITLE_CACHE: dict = {}


def _title_padded(d: dict) -> str:
    key = (d["id"], d["title"], d["code"], d["filename"])
    if key not in _TITLE_CACHE:
        stem = Path(d["filename"]).stem if d.get("filename") and not str(d["filename"]).startswith("http") else ""
        _TITLE_CACHE[key] = " " + " ".join(fold_words(f"{d['code'] or ''} {d['title'] or ''} {stem}")) + " "
    return _TITLE_CACHE[key]


def sync_ai_index(conn: sqlite3.Connection) -> None:
    """Đồng bộ doc_index với doc_chunks cho các tài liệu mới / đã đổi / đã xoá. Mọi nơi ghi doc_chunks đều cập nhật
    uploaded_at, char_count hoặc extract_status của tài liệu, nên so dấu (stamp) trên bảng documents là đủ, không phải
    quét lại toàn bộ nội dung mỗi lần tìm."""
    docs = rows(conn, "SELECT id, title, code, filename, char_count, page_count, extract_status, uploaded_at FROM documents")
    meta = {r[0]: r[1] for r in conn.execute("SELECT doc_id, stamp FROM doc_index_meta")}
    changed = {d["id"]: _doc_stamp(d) for d in docs if meta.get(d["id"]) != _doc_stamp(d)}
    gone = set(meta) - {d["id"] for d in docs}
    if not changed and not gone:
        return
    for doc_id in [*changed, *gone]:
        conn.execute("DELETE FROM doc_index WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM doc_index_meta WHERE doc_id = ?", (doc_id,))
    if changed:  # quét doc_chunks một lần cho mọi tài liệu cần đánh lại chỉ mục (doc_id không có chỉ mục riêng)
        batch = []
        for rowid, doc_id, chunk_no, page, text in conn.execute(
                "SELECT rowid, doc_id, chunk_no, page, text FROM doc_chunks"):
            if int(doc_id) in changed:
                batch.append((" ".join(fold_words(text)), int(doc_id), chunk_no, page, rowid))
        conn.executemany("INSERT INTO doc_index (text, doc_id, chunk_no, page, src) VALUES (?,?,?,?,?)", batch)
        conn.executemany("INSERT INTO doc_index_meta (doc_id, stamp) VALUES (?, ?)", changed.items())
    conn.commit()


def _semantic_extra(conn: sqlite3.Connection, q: str, unit_id: int | None, docs: dict, have: set[int], k: int) -> list[dict]:
    """Tài liệu có đoạn gần nghĩa với câu hỏi (xem backend/semantic.py), chưa có trong kết quả từ khoá.
    `docs` đã lọc theo quyền người hỏi nên không bao giờ trả tài liệu ngoài quyền. Lỗi (mạng, khoá) thì bỏ qua."""
    if k <= 0:
        return []
    from . import semantic
    try:
        hits = semantic.search(conn, q, allowed_ids=set(docs), k=k + len(have))
    except Exception:  # tìm theo ý nghĩa lỗi không được làm hỏng kết quả từ khoá
        return []
    out = []
    for score, doc_id, src, chunk_no, page in hits:
        if doc_id in have or doc_id not in docs:
            continue
        d = docs[doc_id]
        if unit_id and d["unit_id"] and unit_id not in d["unit_ids"]:
            continue
        item = {"doc_id": d["id"], "title": d["title"], "doc_type": DOC_TYPES.get(d["doc_type"], d["doc_type"]),
                "unit_name": ("Tài liệu riêng của người đang hỏi (đính kèm chat)" if d["access_level"] == "private"
                              else d["unit_name"] or "Toàn công ty / chưa gắn đơn vị"),
                "match": f"{round(score * 100)}%", "matched_in": "nội dung (theo ý nghĩa)"}
        if d["version"]:
            item["version"] = d["version"]
        if d["extract_status"] != "ok":
            item["status"] = "chưa đọc được nội dung (chỉ khớp theo tên)"
        item["_chunks"] = [(score, 0, chunk_no, page, src, [])]
        out.append(item)
        if len(out) >= k:
            break
    return out


def ai_search(conn: sqlite3.Connection, q: str, unit_id: int | None = None, limit: int = 8,
              allowed_ids: set[int] | None = None) -> dict:
    """Tìm tài liệu cho trợ lý AI: khớp cả tiêu đề / mã / tên file lẫn nội dung, không phân biệt dấu, mở rộng theo
    cách gọi tương đương, mỗi tài liệu một kết quả (gộp bản trùng), kèm mức độ khớp và các ý còn thiếu."""
    try:
        sync_ai_index(conn)
    except sqlite3.OperationalError:  # đang có tác vụ khác ghi database: tìm trên chỉ mục hiện có
        pass
    concepts = _concepts(q)
    if not concepts:
        return {"results": [], "note": "Từ khoá rỗng hoặc chỉ gồm từ chung chung. Hãy dùng từ khoá nghiệp vụ cụ thể."}
    total_rows = conn.execute("SELECT COUNT(*) FROM doc_index").fetchone()[0] or 1
    for c in concepts:  # ý càng hiếm (ít đoạn chứa) càng quan trọng
        c["df"] = conn.execute("SELECT COUNT(*) FROM doc_index WHERE doc_index MATCH ?", (_fts_expr(c["alts"]),)).fetchone()[0]
        c["w"] = math.log(1 + total_rows / (1 + c["df"]))
    weight = sum(c["w"] for c in concepts)
    docs = {d["id"]: d for d in rows(conn, "SELECT d.id, d.title, d.code, d.filename, d.doc_type, d.version, d.unit_id,"
                                           " d.extract_status, d.uploaded_at, d.char_count, d.access_level, u.name AS unit_name"
                                           " FROM documents d LEFT JOIN units u ON u.id = d.unit_id")
            if allowed_ids is None or d["id"] in allowed_ids}  # tài liệu ngoài quyền người hỏi không bao giờ vào kết quả
    for d in docs.values():  # đơn vị chủ quản + các đơn vị dùng chung: lọc theo đơn vị khớp cả hai
        d["unit_ids"] = {d["unit_id"]} if d["unit_id"] else set()
    for did, uid in conn.execute("SELECT doc_id, unit_id FROM document_units"):
        if did in docs:
            docs[did]["unit_ids"].add(uid)
    internal_intent = any(c["alts"][0] in (("quy", "trinh"), ("quy", "dinh"), ("huong", "dan"), ("bieu", "mau"),
                                           ("ma", "tran", "phan", "cong")) for c in concepts)

    def run(unit_filter: int | None) -> list[dict]:
        allowed = {i for i, d in docs.items() if not unit_filter or not d["unit_id"] or unit_filter in d["unit_ids"]}
        # 1) đoạn nội dung khớp: tối đa vài đoạn tốt nhất mỗi tài liệu để file lớn không chiếm hết chỗ
        hits: dict[int, list] = {}
        expr = " OR ".join(_fts_expr(c["alts"]) for c in concepts if c["df"])
        if expr:
            for rowid, doc_id, chunk_no, page, src, text, rank in conn.execute(
                    "SELECT id, doc_id, chunk_no, page, src, text, rk FROM ("
                    " SELECT *, row_number() OVER (PARTITION BY doc_id ORDER BY rk) AS rn FROM ("
                    "  SELECT rowid AS id, doc_id, chunk_no, page, src, text, bm25(doc_index) AS rk"
                    "  FROM doc_index WHERE doc_index MATCH ?)) WHERE rn <= ? ORDER BY rk LIMIT 400",
                    (expr, MAX_CHUNKS_PER_DOC)):
                if int(doc_id) in allowed:
                    hits.setdefault(int(doc_id), []).append((chunk_no, page, src, " " + text + " ", rank))
        # 2) chấm điểm từng tài liệu: ý khớp ở tiêu đề hoặc ở đoạn nội dung tốt nhất
        scored, chunk_scores = [], {}
        for doc_id in allowed:
            d, title = docs[doc_id], _title_padded(docs[doc_id])
            t_lv = [_level(c, title) for c in concepts]
            title_score = sum(c["w"] * lv for c, lv in zip(concepts, t_lv)) / weight
            best = None
            for chunk_no, page, src, padded, rank in hits.get(doc_id, []):
                lv = [max(a, _level(c, padded)) for c, a in zip(concepts, t_lv)]
                sc = sum(c["w"] * x for c, x in zip(concepts, lv)) / weight
                if best is None or sc > best[0] or (sc == best[0] and rank < best[1]):
                    best = (sc, rank, lv)
                chunk_scores.setdefault(doc_id, []).append((sc, rank, chunk_no, page, src, lv))
            if best is None and title_score == 0:
                continue
            cover, rank, lv = best if best else (title_score, 0.0, t_lv)
            final = cover + 0.25 * title_score + (0.05 if unit_filter and unit_filter in d["unit_ids"] else 0)
            if internal_intent and d["doc_type"] == _WEBSITE:
                final *= 0.8
            scored.append((final, cover, -rank, d, lv, title_score > 0))
        scored.sort(key=lambda t: (t[0], t[2], t[3]["id"]), reverse=True)
        # 3) gộp bản trùng (cùng tên và cùng độ dài nội dung, kể cả khi tải lên ở hai đơn vị): giữ bản xếp trên
        out, seen = [], {}
        for final, cover, _, d, lv, in_title in scored:
            key = (" ".join(fold_words(d["title"])), d["char_count"])
            if key in seen:
                first = seen[key]
                first["duplicates"] = first.get("duplicates", 1) + 1
                other = d["unit_name"] or "Toàn công ty / chưa gắn đơn vị"
                if other != first["unit_name"] and other not in first.setdefault("also_in_units", []):
                    first["also_in_units"].append(other)
                continue
            item = {"doc_id": d["id"], "title": d["title"], "doc_type": DOC_TYPES.get(d["doc_type"], d["doc_type"]),
                    "unit_name": ("Tài liệu riêng của người đang hỏi (đính kèm chat)" if d["access_level"] == "private"
                                  else d["unit_name"] or "Toàn công ty / chưa gắn đơn vị"), "match": f"{round(cover * 100)}%",
                    "matched_in": "tiêu đề + nội dung" if in_title and hits.get(d["id"]) else (
                        "tiêu đề" if in_title else "nội dung")}
            if d["version"]:
                item["version"] = d["version"]
            if d["extract_status"] != "ok":
                item["status"] = "chưa đọc được nội dung (chỉ khớp theo tên)"
            missing = [" ".join(c["orig"]) for c, x in zip(concepts, lv) if not x]
            if missing:
                item["missing"] = missing
            chunks = sorted(chunk_scores.get(d["id"], []), key=lambda t: (-t[0], t[1]))[:2]
            item["_chunks"] = chunks
            seen[key] = item
            out.append(item)
            if len(out) >= limit:
                break
        return out

    results = run(unit_id)
    note = None
    if unit_id and not results:
        results = run(None)
        if results:
            note = "Không có tài liệu khớp trong đơn vị đã chọn; kết quả dưới đây thuộc các đơn vị khác."
    if len(results) < limit:  # từ khoá chưa đủ: bổ sung tài liệu gần nghĩa (nếu đã bật tìm theo ý nghĩa)
        results += _semantic_extra(conn, q, unit_id, docs, {r["doc_id"] for r in results}, limit - len(results))
    # đoạn trích quanh ý hiếm nhất đã khớp, lấy từ văn bản gốc (còn dấu)
    srcs = {src for it in results for *_, src, _ in it["_chunks"]}
    originals = {}
    if srcs:
        marks = ",".join("?" * len(srcs))
        originals = {r[0]: r[1] for r in conn.execute(f"SELECT rowid, text FROM doc_chunks WHERE rowid IN ({marks})",
                                                      list(srcs))}
    for it in results:
        snippets = []
        for sc, _, chunk_no, page, src, lv in it.pop("_chunks"):
            matched = sorted((c for c, x in zip(concepts, lv) if x), key=lambda c: -c["w"])
            text = originals.get(src, "")
            snip = ""
            for c in matched:
                for p in [c["orig"], *c["alts"]]:
                    snip = _make_snippet(text, [(w, False) for w in p], radius=160)
                    if snip:
                        break
                if snip:
                    break
            snippets.append({"chunk_no": chunk_no, "page": page, "snippet": snip or " ".join(text[:320].split())})
        if snippets:
            it["chunks"] = snippets
    best = max((int(r["match"].rstrip("%")) for r in results), default=0)
    if not results:
        note = ("Không tìm thấy tài liệu nào. Trước khi kết luận là chưa có: thử từ khoá khác (tên đầy đủ, viết tắt, "
                "cách gọi khác) và xem danh sách tài liệu của đơn vị liên quan.")
    elif best < 60:
        note = ((note + " ") if note else "") + (
            "Không tài liệu nào chứa đủ các ý của câu tìm (xem 'missing'). Kết quả chỉ khớp một phần: đọc kỹ trước khi "
            "dùng, thử thêm cách diễn đạt khác hoặc xem danh sách tài liệu theo tên trước khi kết luận.")
    labels = [" / ".join(" ".join(p) for p in c["alts"][:4]) for c in concepts]
    return {"searched_for": labels, "results": results, **({"note": note} if note else {})}


def read_chunks(conn: sqlite3.Connection, doc_id: int, start: int = 0, count: int = 6) -> dict:
    doc = row(conn, "SELECT d.id, d.title, d.code, d.version, d.doc_type, d.unit_id, u.name AS unit_name, d.extract_status,"
                    " d.extract_note, d.uploaded_at FROM documents d LEFT JOIN units u ON u.id = d.unit_id WHERE d.id = ?",
              (doc_id,))
    if not doc:
        return {"error": "Không tìm thấy tài liệu"}
    total = conn.execute("SELECT COUNT(*) FROM doc_chunks WHERE doc_id = ?", (doc_id,)).fetchone()[0]
    parts = rows(conn, "SELECT chunk_no, page, text FROM doc_chunks WHERE doc_id = ? AND chunk_no >= ? AND chunk_no < ?"
                       " ORDER BY chunk_no", (doc_id, start, start + count))
    return {**doc, "total_chunks": total, "from_chunk": start, "chunks": parts,
            "has_more": start + count < total}
