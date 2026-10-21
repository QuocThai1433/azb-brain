"""Kho tài liệu: lưu file gốc, trích xuất văn bản, chia đoạn và đánh chỉ mục tìm kiếm.

Hỗ trợ: PDF (có lớp chữ), PDF scan (đọc bằng Gemini), DOCX, XLSX/XLS, TXT/MD.
"""
import math
import re
import sqlite3
import unicodedata
from pathlib import Path

from .db import DB_PATH, connect, row, rows

UPLOAD_DIR = DB_PATH.parent / "uploads"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md"}
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
    """Đọc PDF scan bằng Gemini theo từng cụm trang. Trả về (danh sách văn bản theo cụm, ghi chú)."""
    import pymupdf
    from google.genai import types

    from .ai import GEMINI_MODEL, client, has_gemini

    if not has_gemini():
        raise RuntimeError("PDF dạng scan – cần khoá Gemini API để đọc chữ (OCR).")
    gemini = client(timeout_s=600)
    prompt = (
        "Chép lại nguyên văn toàn bộ nội dung tài liệu này sang Markdown (tiếng Việt, giữ đúng dấu). "
        "Giữ cấu trúc tiêu đề, danh sách, bảng (dạng bảng Markdown), mã tài liệu, số hiệu phiên bản. "
        "Lưu đồ/sơ đồ: mô tả các bước và mũi tên dưới dạng danh sách đánh số. "
        "Đánh dấu đầu mỗi trang bằng dòng '--- Trang N ---'. Không tóm tắt, không bình luận."
    )
    out, notes = [], []
    with pymupdf.open(path) as src:
        total = len(src)
        for start in range(0, total, OCR_PAGES_PER_CALL):
            end = min(start + OCR_PAGES_PER_CALL, total) - 1
            part = pymupdf.open()
            part.insert_pdf(src, from_page=start, to_page=end)
            data = part.tobytes()
            part.close()
            msg = gemini.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=data, mime_type="application/pdf"),
                    prompt + f" Cụm này bắt đầu từ trang {start + 1}.",
                ],
                config=types.GenerateContentConfig(
                    max_output_tokens=64000,
                    thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                ),
            )
            reason = msg.candidates[0].finish_reason.name if msg.candidates and msg.candidates[0].finish_reason else ""
            if (msg.prompt_feedback and msg.prompt_feedback.block_reason) or reason in ("SAFETY", "PROHIBITED_CONTENT"):
                raise RuntimeError(f"Mô hình từ chối đọc trang {start + 1}-{end + 1}.")
            if reason == "MAX_TOKENS":
                notes.append(f"Trang {start + 1}-{end + 1} có thể bị thiếu nội dung cuối.")
            out.append(msg.text or "")
    return out, " ".join(notes)


def extract(path: Path, use_ocr: bool = True) -> dict:
    """Trả về {status, content, pages: [(page_no|None, text)], page_count, note}."""
    ext = path.suffix.lower()
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


def process_document(doc_id: int, use_ocr: bool = True) -> None:
    """Trích xuất + đánh chỉ mục một tài liệu (chạy nền sau khi tải lên)."""
    with connect() as conn:
        doc = row(conn, "SELECT * FROM documents WHERE id = ?", (doc_id,))
        if not doc:
            return
        conn.execute("UPDATE documents SET extract_status = 'processing', extract_note = NULL WHERE id = ?", (doc_id,))
    try:
        result = extract(Path(doc["stored_path"]), use_ocr=use_ocr)
    except Exception as e:
        with connect() as conn:
            conn.execute("UPDATE documents SET extract_status = 'failed', extract_note = ? WHERE id = ?", (str(e), doc_id))
        return
    content = "\n\n".join(p for _, p in result["pages"])
    with connect() as conn:
        conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        for i, (page_no, text) in enumerate(chunk(result["pages"])):
            conn.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) VALUES (?,?,?,?)",
                         (text, doc_id, i, page_no))
        conn.execute(
            "UPDATE documents SET extract_status = ?, extract_note = ?, content = ?, page_count = ?, char_count = ? WHERE id = ?",
            (result["status"], result["note"], content or None, result["page_count"], len(content), doc_id),
        )


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


def search_docs(conn: sqlite3.Connection, q: str, limit: int = 30, unit_id: int | None = None) -> list[dict]:
    """Tìm tài liệu theo tên (mã + tiêu đề + tên file) và nội dung. Khớp tên xếp trước, nội dung sau;
    kèm `snippet` là đoạn trích quanh chỗ khớp. Từ gõ có dấu thì khớp đúng dấu, gõ không dấu thì khớp mọi dấu."""
    terms = _terms(q)
    if not terms:
        return []
    sql = ("SELECT d.id, d.unit_id, u.name AS unit_name, d.process_id, d.title, d.doc_type, d.code, d.version, d.filename,"
           " d.size_bytes, d.page_count, d.char_count, d.extract_status, d.extract_note, d.uploaded_at, d.content"
           " FROM documents d LEFT JOIN units u ON u.id = d.unit_id")
    params: list = []
    if unit_id:
        sql += " WHERE d.unit_id = ?"
        params.append(unit_id)
    by_name, by_content, seen = [], [], set()
    for d in rows(conn, sql + " ORDER BY d.uploaded_at DESC", params):
        content = d.pop("content", None) or ""
        key = (_fold(d["title"]), d["unit_id"])  # cùng tên + cùng đơn vị = bản trùng, giữ bản mới nhất
        if key in seen:
            continue
        nk = ("n", d["id"], d["title"], d["code"], d["filename"])
        if nk not in _WORDSET_CACHE:
            _WORDSET_CACHE[nk] = _word_sets(f"{d['code'] or ''} {d['title']} {d['filename'] or ''}")
        n_fold, n_raw = _WORDSET_CACHE[nk]
        name_ok = _matches(terms, n_fold, n_raw)
        in_name = all(name_ok)
        in_content = False
        if not in_name and content:
            ck = (d["id"], len(content), d["uploaded_at"])
            if ck not in _WORDSET_CACHE:  # chuẩn hoá cả nội dung rất tốn: làm 1 lần, các lần gõ sau dùng lại
                _WORDSET_CACHE[ck] = _word_sets(content)
            c_fold, c_raw = _WORDSET_CACHE[ck]
            in_content = all(a or b for a, b in zip(name_ok, _matches(terms, c_fold, c_raw)))
        if in_name or in_content:
            seen.add(key)
            d["in_name"] = in_name
            d["_content"] = "" if in_name else content
            (by_name if in_name else by_content).append(d)
    out = (by_name + by_content)[:limit]
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


def ai_search(conn: sqlite3.Connection, q: str, unit_id: int | None = None, limit: int = 8) -> dict:
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
                                           " d.extract_status, d.uploaded_at, d.char_count, u.name AS unit_name"
                                           " FROM documents d LEFT JOIN units u ON u.id = d.unit_id")}
    internal_intent = any(c["alts"][0] in (("quy", "trinh"), ("quy", "dinh"), ("huong", "dan"), ("bieu", "mau"),
                                           ("ma", "tran", "phan", "cong")) for c in concepts)

    def run(unit_filter: int | None) -> list[dict]:
        allowed = {i for i, d in docs.items() if not unit_filter or d["unit_id"] in (unit_filter, None)}
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
            final = cover + 0.25 * title_score + (0.05 if unit_filter and d["unit_id"] == unit_filter else 0)
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
                    "unit_name": d["unit_name"] or "Toàn công ty / chưa gắn đơn vị", "match": f"{round(cover * 100)}%",
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
