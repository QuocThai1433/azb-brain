"""Kiểm tra chéo các tài liệu đã đọc bằng AI (PDF scan): so văn bản đã lưu với bản gốc, báo trang nghi ngờ.

Hai lớp kiểm tra:
  1. Miễn phí (luôn chạy): thiếu trang, trang trống dù có nhiều mực, [không rõ], ký tự lỗi, mất dấu tiếng Việt.
  2. Đọc lại độc lập (tốn phí Anthropic, chỉ khi có --sample): mỗi tài liệu lấy N trang ngẫu nhiên, cho AI đọc lại từ ảnh trang,
     rồi so từ và con số với văn bản đã lưu. Lệch nhiều → nghi ngờ.

Chạy (từ thư mục gốc dự án):
  python -m backend.verify_scan                       # chỉ lớp 1, toàn bộ 74 tài liệu
  python -m backend.verify_scan --sample 2            # lớp 1 + đọc lại 2 trang/tài liệu
  python -m backend.verify_scan --sample 2 --docs 3,221 --seed 7
Kết quả: data/verify_scan_report.md (không sửa dữ liệu nào).
"""
import argparse
import difflib
import random
import re
import time
import unicodedata
from pathlib import Path

import anthropic

from .db import DB_PATH, connect, rows
from .documents import split_pages

REPORT = DB_PATH.parent / "verify_scan_report.md"
NUM = re.compile(r"\d[\d.,]*\d|\d")
VI_DIACRITIC = re.compile("[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
INK_RICH = 0.03          # tỷ lệ điểm ảnh tối: trên mức này coi là trang có nhiều nội dung
MIN_CHARS_INK_RICH = 80  # trang nhiều mực mà văn bản ngắn hơn mức này → nghi ngờ
SIM_WARN = 0.85
NUM_RECALL_WARN = 0.8


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[#*_`|>\-]+", " ", text)  # bỏ ký hiệu Markdown
    return re.sub(r"\s+", " ", text).strip()


def _nums(text: str) -> list[str]:
    return [re.sub(r"[.,]", "", n) for n in NUM.findall(text)]


def ink_ratio(page) -> float:
    import pymupdf
    pix = page.get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5), colorspace=pymupdf.csGRAY)
    data = pix.samples
    return sum(1 for b in data if b < 128) / max(len(data), 1)


def free_checks(doc, pdf, pages: dict[int, str]) -> dict[int, list[str]]:
    """Lớp 1. Trả về {số trang: [lý do nghi ngờ]}."""
    flags: dict[int, list[str]] = {}
    n = len(pdf)
    missing = [p for p in range(1, n + 1) if p not in pages]
    for p in missing:
        flags.setdefault(p, []).append("không có dòng đánh dấu trang trong văn bản đã lưu")
    for p, text in pages.items():
        why = flags.setdefault(p, [])
        if p > n:
            why.append(f"số trang {p} vượt số trang thật ({n})")
            continue
        ink = ink_ratio(pdf[p - 1])
        if ink >= INK_RICH and len(text.strip()) < MIN_CHARS_INK_RICH:
            why.append(f"trang nhiều mực ({ink:.0%}) nhưng chỉ có {len(text.strip())} ký tự")
        if "[không rõ]" in text.lower():
            why.append(f"{text.lower().count('[không rõ]')} chỗ AI ghi [không rõ]")
        if "�" in text:
            why.append("có ký tự lỗi �")
        letters = sum(c.isalpha() for c in text)
        if letters > 300 and len(VI_DIACRITIC.findall(text)) / letters < 0.01 and doc["lang_vi"]:
            why.append("gần như không có dấu tiếng Việt (có thể mất dấu)")
        if re.search(r"(\w[^\n|]{11,}?)\1{3,}", re.sub(r"[-_.=\s|:]{4,}", " ", text)):  # bỏ đường kẻ bảng, dấu chấm dẫn
            why.append("có đoạn lặp bất thường (AI bị kẹt vòng lặp)")
    return {p: w for p, w in flags.items() if w}


def reread_page(pdf, page_no: int) -> str:
    """Lớp 2: cho Claude đọc lại đúng một trang từ ảnh, độc lập với lần đọc cũ."""
    import base64

    import pymupdf

    from .ai import ANTHROPIC_MODEL, client, log_usage, message_text

    png = pdf[page_no - 1].get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
    prompt = ("Chép lại nguyên văn toàn bộ chữ trong ảnh trang tài liệu này (tiếng Việt, giữ đúng dấu và mọi con số). "
              "Bảng thì dùng bảng Markdown. Không tóm tắt, không bình luận.")
    claude = client(timeout_s=300)
    data = base64.standard_b64encode(png).decode("ascii")
    for attempt in range(3):
        try:
            msg = claude.messages.create(
                model=ANTHROPIC_MODEL, max_tokens=16000, output_config={"effort": "low"},
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
                    {"type": "text", "text": prompt}]}])
            log_usage("verify_scan", ANTHROPIC_MODEL, getattr(msg, "usage", None), f"trang {page_no}")
            return message_text(msg)
        except anthropic.APIStatusError as e:
            if e.status_code < 500 or attempt == 2:
                raise
            time.sleep(10 * (attempt + 1))
    return ""


def compare(stored: str, again: str) -> tuple[float, float, list[str]]:
    """Trả về (độ giống theo từ, tỷ lệ con số của bản đọc lại có trong bản lưu, các con số lệch)."""
    a, b = _norm(stored).split(), _norm(again).split()
    sim = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0.0
    ns, na = _nums(stored), _nums(again)
    pool = list(ns)
    missing = []
    for n in na:
        if n in pool:
            pool.remove(n)
        else:
            missing.append(n)
    recall = 1 - len(missing) / len(na) if na else 1.0
    return sim, recall, missing


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, default=0, help="số trang đọc lại bằng AI cho mỗi tài liệu (0 = chỉ lớp 1)")
    ap.add_argument("--docs", help="chỉ kiểm tra các id này, ví dụ 3,221")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    import pymupdf

    rng = random.Random(a.seed)
    from .documents import AI_READ_PDF_SQL
    with connect() as conn:
        docs = rows(conn, f"SELECT id, title, stored_path, page_count, content FROM documents WHERE {AI_READ_PDF_SQL} ORDER BY id")
    if a.docs:
        want = {int(x) for x in a.docs.split(",")}
        docs = [d for d in docs if d["id"] in want]
    if a.sample:
        from .ai import has_anthropic
        if not has_anthropic():
            raise SystemExit("Chưa có ANTHROPIC_API_KEY – bỏ --sample để chỉ chạy lớp 1.")

    out, summary = [], []
    quota_hit = False
    for d in docs:
        path = Path(d["stored_path"])
        if not path.exists():
            summary.append((d["id"], d["title"], "THIẾU FILE GỐC", 0, 0))
            continue
        with pymupdf.open(path) as pdf:
            d["lang_vi"] = True
            n_pages = len(pdf)
            pages = split_pages(d["content"] or "", len(pdf))
            flags = free_checks(d, pdf, pages)
            reread = []
            if a.sample and not quota_hit:
                for p in rng.sample(sorted(x for x in pages if x <= len(pdf)), min(a.sample, len(pages))):
                    try:
                        sim, recall, miss = compare(pages[p], reread_page(pdf, p))
                    except Exception as e:  # lỗi mạng: ghi lại; hết hạn mức (429) thì dừng đọc lại, vẫn giữ kết quả lớp 1
                        reread.append((p, None, None, [], str(e)[:100]))
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            quota_hit = True
                            break
                        continue
                    reread.append((p, sim, recall, miss, ""))
                    if sim < SIM_WARN or recall < NUM_RECALL_WARN:
                        flags.setdefault(p, []).append(f"đọc lại khác bản lưu: giống {sim:.0%}, con số khớp {recall:.0%}")
                    time.sleep(1)
        bad = sorted(flags)
        summary.append((d["id"], d["title"], f"{len(bad)} trang nghi ngờ" if bad else "ổn", n_pages, len(reread)))
        if bad or reread:
            out.append(f"\n### #{d['id']} {d['title']} ({n_pages} trang)")
            for p in bad:
                out.append(f"- **Trang {p}**: " + "; ".join(flags[p]))
            for p, sim, recall, miss, err in reread:
                if err:
                    out.append(f"- (đọc lại trang {p} lỗi: {err})")
                else:
                    out.append(f"- đọc lại trang {p}: giống {sim:.0%}, con số khớp {recall:.0%}"
                               + (f", lệch số: {', '.join(miss[:10])}" if miss else ""))
        print(f"#{d['id']} {d['title'][:55]}: {summary[-1][2]}", flush=True)

    head = [f"# Báo cáo kiểm tra chéo tài liệu scan\n", f"- Số tài liệu: {len(summary)}; trang đọc lại bằng AI mỗi tài liệu: {a.sample}",
            f"- Ngưỡng: giống từ < {SIM_WARN:.0%} hoặc con số khớp < {NUM_RECALL_WARN:.0%} thì nghi ngờ",
            f"- Tài liệu có trang nghi ngờ: {sum(1 for s in summary if 'nghi ngờ' in s[2] or 'THIẾU' in s[2])}/{len(summary)}\n",
            "Chỉ là cảnh báo để người kiểm tra mở bản gốc; không có nghĩa chắc chắn sai."]
    REPORT.write_text("\n".join(head + out), encoding="utf-8")
    print(f"\nĐã ghi {REPORT}")


if __name__ == "__main__":
    main()
