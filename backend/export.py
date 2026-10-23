"""Xuất Word / Excel / PowerPoint theo yêu cầu của người dùng trong khung chat.

AI gọi công cụ `tao_file` với nội dung có cấu trúc; module này kiểm tra lại dữ liệu rồi dựng file theo màu AZB.
File lưu ở data/exports, đặt tên theo người tạo nên chỉ chính người đó tải được (xem endpoint trong app.py).
"""
import re
import secrets
import time
import unicodedata
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.dml.color import RGBColor as PRGB
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt as PPt

EXPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "exports"
LOGO = Path(__file__).resolve().parent.parent / "frontend" / "logo.png"
KEEP_SECONDS = 7 * 86400
MAX_SECTIONS, MAX_BULLETS, MAX_ROWS, MAX_COLS = 40, 40, 500, 12
MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
BRAND, BRAND_DARK, ACCENT, SOFT = "004C97", "001A38", "F47A20", "EAF2FB"
_TOKEN = re.compile(r"^[0-9a-f]{16}$")
_LH_MARK = re.compile(r"\s*\[\[LH:\d+\]\]")


def _rgb(hex_: str) -> RGBColor:
    return RGBColor.from_string(hex_)


def _prgb(hex_: str) -> PRGB:
    return PRGB.from_string(hex_)


def _text(value, limit: int = 2000) -> str:
    """Chuỗi sạch: bỏ dấu [[LH:id]] (liên hệ chỉ điền ở khung chat), bỏ ký tự điều khiển, giới hạn độ dài."""
    s = _LH_MARK.sub("", "" if value is None else str(value))
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s).replace("**", "").replace("__", "")
    return s.strip()[:limit]


def _slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s[:60] or "AZB"


def normalize(args: dict) -> dict:
    """Làm sạch tham số AI gửi (model nhẹ hay sinh sai cấu trúc). Ném ValueError với thông báo để AI sửa lại."""
    kind = _text(args.get("loai")).lower().lstrip(".")
    if kind not in MIME:
        raise ValueError("loai phải là docx, xlsx hoặc pptx")
    title = _text(args.get("tieu_de"), 200)
    if not title:
        raise ValueError("thiếu tieu_de")
    sections = args.get("phan")
    if isinstance(sections, dict):
        sections = [sections]
    if not isinstance(sections, list) or not sections:
        raise ValueError("phan phải là danh sách các phần, mỗi phần có tieu_de, noi_dung và/hoặc bang")
    out = []
    for sec in sections[:MAX_SECTIONS]:
        if not isinstance(sec, dict):
            continue
        bullets = sec.get("noi_dung") or []
        if isinstance(bullets, str):
            bullets = [b for b in bullets.splitlines() if b.strip()]
        bullets = [_text(b) for b in bullets if _text(b)][:MAX_BULLETS] if isinstance(bullets, list) else []
        table = sec.get("bang")
        cols, data = [], []
        if isinstance(table, dict):
            cols = [_text(c, 120) for c in (table.get("cot") or [])][:MAX_COLS]
            for r in (table.get("dong") or [])[:MAX_ROWS]:
                if isinstance(r, list):
                    cells = [_text(c, 500) for c in r][:len(cols)]
                    data.append(cells + [""] * (len(cols) - len(cells)))
        if not cols:
            data = []
        name = _text(sec.get("tieu_de"), 120)
        if name or bullets or data:
            out.append({"tieu_de": name, "noi_dung": bullets, "cot": cols, "dong": data})
    if not out:
        raise ValueError("các phần đều trống: cần có noi_dung hoặc bang")
    return {"loai": kind, "tieu_de": title, "ten_file": _slug(_text(args.get("ten_file"), 80) or title),
            "tom_tat": _text(args.get("tom_tat"), 400), "phan": out}


# ---------------- Word ----------------
def _shade(cell, hex_: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_)
    tc_pr.append(shd)


def build_docx(spec: dict, path: Path) -> None:
    doc = Document()
    base = doc.styles["Normal"]
    base.font.name, base.font.size = "Calibri", Pt(11)
    base.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    if LOGO.exists():
        doc.add_picture(str(LOGO), height=Pt(36))
    title = doc.add_paragraph()
    run = title.add_run(spec["tieu_de"])
    run.bold, run.font.size, run.font.color.rgb = True, Pt(22), _rgb(BRAND)
    meta = doc.add_paragraph()
    meta.add_run(f"Công ty Cổ phần AZB · {time.strftime('%d/%m/%Y')}").font.color.rgb = _rgb("6B7280")
    if spec["tom_tat"]:
        p = doc.add_paragraph()
        r = p.add_run(spec["tom_tat"])
        r.italic = True
    for sec in spec["phan"]:
        if sec["tieu_de"]:
            h = doc.add_heading(sec["tieu_de"], level=1)
            for r in h.runs:
                r.font.color.rgb, r.font.name = _rgb(BRAND), "Calibri"
        for b in sec["noi_dung"]:
            doc.add_paragraph(b, style="List Bullet")
        if sec["cot"]:
            t = doc.add_table(rows=1, cols=len(sec["cot"]))
            t.style, t.alignment = "Table Grid", WD_TABLE_ALIGNMENT.CENTER
            for i, c in enumerate(sec["cot"]):
                cell = t.rows[0].cells[i]
                cell.text = ""
                r = cell.paragraphs[0].add_run(c)
                r.bold, r.font.color.rgb = True, _rgb("FFFFFF")
                _shade(cell, BRAND)
            for n, row_ in enumerate(sec["dong"]):
                cells = t.add_row().cells
                for i, v in enumerate(row_):
                    cells[i].text = v
                    if n % 2:
                        _shade(cells[i], SOFT)
            doc.add_paragraph()
    doc.save(path)


# ---------------- Excel ----------------
def _sheet_name(name: str, used: set) -> str:
    base = re.sub(r"[\[\]\\/*?:]", " ", name).strip()[:28] or "Sheet"
    cand, n = base, 2
    while cand.lower() in used:
        cand = f"{base[:25]} {n}"
        n += 1
    used.add(cand.lower())
    return cand


def _number(v: str):
    """Ô số thật (để Excel cộng/sắp xếp được): '1.234,5' hoặc '1,234.5' hoặc '12%' -> số; còn lại giữ chuỗi."""
    s = v.strip().replace(" ", "")
    if not s or not re.fullmatch(r"-?\d{1,3}([.,]\d{3})*([.,]\d+)?|-?\d+([.,]\d+)?", s):
        return v
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif s.count(".") > 1 or s.count(",") > 1:
        s = s.replace(".", "").replace(",", "")
    elif re.fullmatch(r"-?\d{1,3}[.,]\d{3}", s):
        s = s.replace(".", "").replace(",", "")  # 1.234 / 1,234 là hàng nghìn
    else:
        s = s.replace(",", ".")
    try:
        f = float(s)
    except ValueError:
        return v
    return int(f) if f.is_integer() else f


def build_xlsx(spec: dict, path: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    used: set = set()
    side = Side(style="thin", color="D1D5DB")
    border = Border(left=side, right=side, top=side, bottom=side)
    tables = [s for s in spec["phan"] if s["cot"]]
    notes = [s for s in spec["phan"] if not s["cot"] and (s["tieu_de"] or s["noi_dung"])]
    if notes or not tables:
        ws = wb.create_sheet(_sheet_name("Tổng quan", used))
        ws["A1"] = spec["tieu_de"]
        ws["A1"].font = Font(bold=True, size=16, color=BRAND)
        r = 3
        if spec["tom_tat"]:
            ws.cell(r, 1, spec["tom_tat"]).alignment = Alignment(wrap_text=True)
            r += 2
        for s in notes:
            if s["tieu_de"]:
                ws.cell(r, 1, s["tieu_de"]).font = Font(bold=True, size=12, color=BRAND)
                r += 1
            for b in s["noi_dung"]:
                ws.cell(r, 1, "• " + b).alignment = Alignment(wrap_text=True, vertical="top")
                r += 1
            r += 1
        ws.column_dimensions["A"].width = 110
    for s in tables:
        ws = wb.create_sheet(_sheet_name(s["tieu_de"] or "Bảng", used))
        top = 1
        if s["tieu_de"]:
            ws["A1"] = s["tieu_de"]
            ws["A1"].font = Font(bold=True, size=14, color=BRAND)
            top = 3
        for i, c in enumerate(s["cot"], 1):
            cell = ws.cell(top, i, c)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=BRAND)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
        for n, row_ in enumerate(s["dong"], top + 1):
            for i, v in enumerate(row_, 1):
                cell = ws.cell(n, i, _number(v))
                cell.border = border
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                if (n - top) % 2 == 0:
                    cell.fill = PatternFill("solid", fgColor=SOFT)
        for i, c in enumerate(s["cot"], 1):
            longest = max([len(c)] + [len(str(r[i - 1])) for r in s["dong"]])
            ws.column_dimensions[get_column_letter(i)].width = min(max(longest + 3, 10), 60)
        ws.freeze_panes = ws.cell(top + 1, 1)
        if s["dong"]:
            ws.auto_filter.ref = f"A{top}:{get_column_letter(len(s['cot']))}{top + len(s['dong'])}"
    wb.save(path)


# ---------------- PowerPoint ----------------
W, H = Inches(13.333), Inches(7.5)


def _box(slide, x, y, w, h, fill=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.line.fill.background()
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = _prgb(fill)
    else:
        s.fill.background()
    return s


def _label(slide, x, y, w, h, text, size, color="1F2937", bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap, tf.vertical_anchor = True, anchor
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = PPt(size), bold, _prgb(color), "Calibri"
    return tb


def _footer(slide, n: int, total: int) -> None:
    _box(slide, 0, H - Inches(0.45), W, Inches(0.45), SOFT)
    _label(slide, Inches(0.5), H - Inches(0.42), Inches(8), Inches(0.4), "Công ty Cổ phần AZB", 11, "6B7280",
           anchor=MSO_ANCHOR.MIDDLE)
    _label(slide, W - Inches(1.5), H - Inches(0.42), Inches(1), Inches(0.4), f"{n}/{total}", 11, "6B7280",
           align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)


def _chunks(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), size)] or [[]]


def build_pptx(spec: dict, path: Path) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    blank = prs.slide_layouts[6]

    # trang bìa
    s = prs.slides.add_slide(blank)
    _box(s, 0, 0, W, H, BRAND_DARK)
    _box(s, 0, 0, Inches(0.35), H, ACCENT)
    if LOGO.exists():
        _box(s, Inches(0.9), Inches(0.7), Inches(2.6), Inches(1.0), "FFFFFF", MSO_SHAPE.ROUNDED_RECTANGLE)
        s.shapes.add_picture(str(LOGO), Inches(1.05), Inches(0.8), height=Inches(0.8))
    _label(s, Inches(0.9), Inches(2.5), Inches(11.4), Inches(2.0), spec["tieu_de"], 44, "FFFFFF", True, anchor=MSO_ANCHOR.BOTTOM)
    _box(s, Inches(0.95), Inches(4.65), Inches(1.6), Emu(45000), ACCENT)
    sub = spec["tom_tat"] or "Công ty Cổ phần AZB"
    _label(s, Inches(0.9), Inches(4.85), Inches(11), Inches(1.2), sub, 20, "B9D3EF")
    _label(s, Inches(0.9), H - Inches(0.9), Inches(6), Inches(0.5), time.strftime("%d/%m/%Y"), 14, "B9D3EF")

    pages = []  # (tiêu đề, bullets, cột, dòng, chỉ số trang con)
    for sec in spec["phan"]:
        name = sec["tieu_de"] or spec["tieu_de"]
        if sec["noi_dung"]:
            parts = _chunks(sec["noi_dung"], 6)
            for i, part in enumerate(parts):
                pages.append((name + (f" ({i + 1}/{len(parts)})" if len(parts) > 1 else ""), part, [], []))
        if sec["cot"]:
            parts = _chunks(sec["dong"], 8)
            for i, part in enumerate(parts):
                pages.append((name + (f" ({i + 1}/{len(parts)})" if len(parts) > 1 else ""), [], sec["cot"], part))
    total = len(pages) + 1
    for n, (name, bullets, cols, data) in enumerate(pages, 2):
        s = prs.slides.add_slide(blank)
        _box(s, 0, 0, W, Inches(1.25), BRAND)
        _box(s, 0, Inches(1.25), W, Emu(40000), ACCENT)
        _label(s, Inches(0.6), Inches(0.1), Inches(12.1), Inches(1.05), name, 30, "FFFFFF", True, anchor=MSO_ANCHOR.MIDDLE)
        if bullets:
            size = 24 if len(bullets) <= 4 else 20
            step = Inches(0.95 if len(bullets) <= 4 else 0.78)
            for i, b in enumerate(bullets):
                y = Inches(1.7) + step * i
                _box(s, Inches(0.7), y + Inches(0.12), Inches(0.22), Inches(0.22), ACCENT, MSO_SHAPE.OVAL)
                _label(s, Inches(1.1), y, Inches(11.6), step, b, size)
        else:
            rows_n = len(data) + 1
            gt = s.shapes.add_table(rows_n, len(cols), Inches(0.6), Inches(1.7), W - Inches(1.2), Inches(0.5) * rows_n)
            tbl = gt.table
            fs = 14 if len(cols) <= 5 else 11
            for i, c in enumerate(cols):
                cell = tbl.cell(0, i)
                cell.text = c
                cell.fill.solid()
                cell.fill.fore_color.rgb = _prgb(BRAND)
                for p in cell.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size, r.font.bold, r.font.color.rgb = PPt(fs), True, _prgb("FFFFFF")
            for ri, row_ in enumerate(data, 1):
                for ci, v in enumerate(row_):
                    cell = tbl.cell(ri, ci)
                    cell.text = v
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = _prgb(SOFT if ri % 2 == 0 else "FFFFFF")
                    for p in cell.text_frame.paragraphs:
                        for r in p.runs:
                            r.font.size, r.font.color.rgb = PPt(fs), _prgb("1F2937")
        _footer(s, n, total)
    prs.save(path)


BUILDERS = {"docx": build_docx, "xlsx": build_xlsx, "pptx": build_pptx}


def cleanup() -> None:
    """Xoá file xuất đã quá hạn lưu."""
    if not EXPORT_DIR.exists():
        return
    cutoff = time.time() - KEEP_SECONDS
    for f in EXPORT_DIR.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def create(args: dict, user_id: int) -> dict:
    """Dựng file từ tham số của AI. Trả về thông tin cho AI (và `_export` để máy chủ gắn link vào câu trả lời)."""
    try:
        spec = normalize(args or {})
    except ValueError as e:
        return {"error": f"Không tạo được file: {e}. Hãy gọi lại tao_file với đúng cấu trúc."}
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    cleanup()
    token = secrets.token_hex(8)
    filename = f"{spec['ten_file']}.{spec['loai']}"
    path = EXPORT_DIR / f"{int(user_id)}_{token}__{filename}"
    BUILDERS[spec["loai"]](spec, path)
    return {"ok": True, "ten_file": filename, "so_phan": len(spec["phan"]),
            "ghi_chu": "File đã được tạo và hệ thống tự gắn link tải vào cuối câu trả lời. Đừng tự viết link; chỉ nói ngắn gọn "
                       "đã tạo file gì và gồm những nội dung nào.",
            "_export": {"token": token, "filename": filename}}


def find(user_id: int, token: str) -> Path | None:
    """File xuất của đúng người dùng này, hoặc None."""
    if not _TOKEN.match(token or "") or not EXPORT_DIR.exists():
        return None
    for f in EXPORT_DIR.glob(f"{int(user_id)}_{token}__*"):
        return f
    return None


def display_name(path: Path) -> str:
    return path.name.split("__", 1)[1]
