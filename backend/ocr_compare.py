"""So sánh đọc scan giữa Claude và Gemini trên vài file mẫu, chỉ để đánh giá: không ghi vào kho tài liệu hay ai_usage_log.

Chạy (từ thư mục gốc dự án):
  python -X utf8 -m backend.ocr_compare a.pdf b.png          # chỉ ước tính chi phí, KHÔNG gọi API
  python -X utf8 -m backend.ocr_compare a.pdf b.png --run    # gọi cả hai API, lưu kết quả vào data/ocr_compare/

NỘI DUNG FILE được gửi tới Anthropic và Google. Chỉ dùng file không thuộc loại mật.
"""
import argparse
import base64
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from .documents import IMAGE_MIME, OCR_PAGES_PER_CALL, OCR_PDF_PROMPT

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "ocr_compare"
MAX_FILES = 10
IMAGE_PROMPT = (
    "Chép lại nguyên văn mọi chữ nhìn thấy trong ảnh (tiếng Việt, giữ đúng dấu), bảng thì dựng lại dạng bảng Markdown, "
    "giữ nguyên số liệu. Chữ mờ không đọc được ghi [không rõ]. Không tóm tắt, không bình luận."
)

# Ước lượng THÔ, chỉ để biết cỡ số tiền trước khi chạy thật; chỉnh bằng biến môi trường nếu đo thấy lệch.
# Token vào mỗi trang scan (Claude đọc cả chữ lẫn ảnh trang nên nhiều hơn), token chữ ra mỗi trang.
EST_CLAUDE_IN_PER_PAGE = int(os.environ.get("AZB_EST_CLAUDE_IN_PER_PAGE", "2500"))
EST_GEMINI_IN_PER_PAGE = int(os.environ.get("AZB_EST_GEMINI_IN_PER_PAGE", "1000"))
EST_OUT_PER_PAGE = int(os.environ.get("AZB_EST_OUT_PER_PAGE", "900"))
# Giá Gemini lấy từ trang tổng hợp bên thứ ba, chưa đối chiếu trang giá chính thức: chỉnh bằng AZB_PRICE_GEMINI=in,out
_GEMINI_PRICE_DEFAULT = (0.50, 3.00)


def gemini_price() -> tuple[float, float]:
    try:
        p_in, p_out = (float(x) for x in os.environ.get("AZB_PRICE_GEMINI", "").split(","))
        return p_in, p_out
    except ValueError:
        return _GEMINI_PRICE_DEFAULT


def gemini_model() -> str:
    return os.environ.get("AZB_GEMINI_OCR_MODEL") or os.environ.get("AZB_GEMINI_MODEL", "gemini-3.8-flash")


# ---------------- Chuẩn bị file ----------------
def load_parts(path: Path) -> list[dict]:
    """Chia file thành các phần gửi một lần: PDF theo cụm OCR_PAGES_PER_CALL trang, ảnh là một phần.
    Mỗi phần: {label, mime, data (bytes), pages, start}."""
    ext = path.suffix.lower()
    if ext in IMAGE_MIME:
        return [{"label": path.name, "mime": IMAGE_MIME[ext], "data": path.read_bytes(), "pages": 1, "start": 1}]
    if ext != ".pdf":
        raise ValueError(f"Chỉ so sánh PDF hoặc ảnh (png/jpg/webp), không phải {ext or 'file không đuôi'}")
    import pymupdf
    parts = []
    with pymupdf.open(path) as src:
        total = len(src)
        for start in range(0, total, OCR_PAGES_PER_CALL):
            end = min(start + OCR_PAGES_PER_CALL, total) - 1
            part = pymupdf.open()
            part.insert_pdf(src, from_page=start, to_page=end)
            data = part.tobytes()
            part.close()
            parts.append({"label": f"{path.name} (trang {start + 1}-{end + 1})", "mime": "application/pdf",
                          "data": data, "pages": end - start + 1, "start": start + 1})
    return parts


def estimate(parts: list[dict], claude_price: tuple[float, float]) -> dict:
    """Ước tính chi phí đọc các phần này bằng Claude và Gemini (USD)."""
    pages = sum(p["pages"] for p in parts)
    g_in, g_out = gemini_price()
    c_in, c_out = claude_price
    out_tok = pages * EST_OUT_PER_PAGE
    return {
        "pages": pages,
        "claude_usd": (pages * EST_CLAUDE_IN_PER_PAGE * c_in + out_tok * c_out) / 1_000_000,
        "gemini_usd": (pages * EST_GEMINI_IN_PER_PAGE * g_in + out_tok * g_out) / 1_000_000,
    }


# ---------------- So sánh văn bản ----------------
_PAGE_MARK = re.compile(r"^\s*-{2,}\s*Trang\s+\d+\s*-{2,}\s*$", re.IGNORECASE | re.MULTILINE)
_WORD = re.compile(r"\w+", re.UNICODE)
_NUMBER = re.compile(r"\d[\d.,/]*\d|\d")


def _words(text: str) -> list[str]:
    return _WORD.findall(_PAGE_MARK.sub(" ", text).lower())


def _numbers(text: str) -> Counter:
    return Counter(_NUMBER.findall(_PAGE_MARK.sub(" ", text)))


def compare_texts(a: str, b: str) -> dict:
    """So hai bản chép: độ trùng từ (F1 theo tần suất từ, không xét thứ tự) và các con số chỉ có ở một bên.
    Con số là chỗ sai nguy hiểm nhất của OCR nên tách riêng."""
    wa, wb = Counter(_words(a)), Counter(_words(b))
    na, nb = sum(wa.values()), sum(wb.values())
    common = sum((wa & wb).values())
    if na == 0 and nb == 0:
        f1 = 1.0
    elif na == 0 or nb == 0:
        f1 = 0.0
    else:
        prec, rec = common / nb, common / na
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    ca, cb = _numbers(a), _numbers(b)
    return {
        "words_a": na, "words_b": nb, "word_f1": f1,
        "numbers_a": sum(ca.values()), "numbers_b": sum(cb.values()),
        "only_a": sorted((ca - cb).elements()), "only_b": sorted((cb - ca).elements()),
    }


# ---------------- Gọi API ----------------
def run_claude(parts: list[dict]) -> dict:
    from .ai import ANTHROPIC_MODEL, client, has_anthropic, message_text, record_usage

    if not has_anthropic():
        raise RuntimeError("Thiếu ANTHROPIC_API_KEY")
    claude = client(timeout_s=600)
    audit: dict = {}
    texts, notes = [], []
    started = time.monotonic()
    for p in parts:
        kind = "document" if p["mime"] == "application/pdf" else "image"
        prompt = OCR_PDF_PROMPT + f" Cụm này bắt đầu từ trang {p['start']}." if kind == "document" else IMAGE_PROMPT
        data = base64.standard_b64encode(p["data"]).decode("ascii")
        with claude.messages.stream(
            model=ANTHROPIC_MODEL, max_tokens=64000, output_config={"effort": "low"},
            messages=[{"role": "user", "content": [
                {"type": kind, "source": {"type": "base64", "media_type": p["mime"], "data": data}},
                {"type": "text", "text": prompt}]}],
        ) as stream:
            msg = stream.get_final_message()
        record_usage(audit, ANTHROPIC_MODEL, getattr(msg, "usage", None))
        if msg.stop_reason == "refusal":
            raise RuntimeError(f"Claude từ chối đọc {p['label']}")
        if msg.stop_reason == "max_tokens":
            notes.append(f"{p['label']}: có thể thiếu phần cuối")
        texts.append(message_text(msg))
    u = audit.get("usage", {})
    return {"model": ANTHROPIC_MODEL, "text": "\n\n".join(texts), "cost_usd": u.get("cost_usd", 0.0),
            "in_tokens": u.get("input", 0) + u.get("cache_read", 0) + u.get("cache_write", 0), "out_tokens": u.get("output", 0),
            "seconds": time.monotonic() - started, "notes": notes}


def run_gemini(parts: list[dict]) -> dict:
    from google.genai import errors, types

    from .ai import gemini_client, has_gemini

    if not has_gemini():
        raise RuntimeError("Thiếu GEMINI_API_KEY")
    model = gemini_model()
    g_in, g_out = gemini_price()
    gemini = gemini_client(timeout_s=600)
    texts, notes = [], []
    tok_in = tok_out = 0
    started = time.monotonic()
    for p in parts:
        prompt = OCR_PDF_PROMPT + f" Cụm này bắt đầu từ trang {p['start']}." if p["mime"] == "application/pdf" else IMAGE_PROMPT
        for attempt in range(3):  # model hay báo 503 "quá tải" tạm thời
            try:
                msg = gemini.models.generate_content(
                    model=model,
                    contents=[types.Part.from_bytes(data=p["data"], mime_type=p["mime"]), prompt],
                    config=types.GenerateContentConfig(
                        max_output_tokens=64000,
                        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)),
                )
                break
            except errors.ServerError:
                if attempt == 2:
                    raise
                time.sleep(10 * (attempt + 1))
        reason = msg.candidates[0].finish_reason.name if msg.candidates and msg.candidates[0].finish_reason else ""
        if (msg.prompt_feedback and msg.prompt_feedback.block_reason) or reason in ("SAFETY", "PROHIBITED_CONTENT"):
            raise RuntimeError(f"Gemini từ chối đọc {p['label']}")
        if reason == "MAX_TOKENS":
            notes.append(f"{p['label']}: có thể thiếu phần cuối")
        um = msg.usage_metadata
        tok_in += (getattr(um, "prompt_token_count", 0) or 0)
        tok_out += (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
        texts.append(msg.text or "")
    return {"model": model, "text": "\n\n".join(texts), "cost_usd": (tok_in * g_in + tok_out * g_out) / 1_000_000,
            "in_tokens": tok_in, "out_tokens": tok_out, "seconds": time.monotonic() - started, "notes": notes}


# ---------------- Báo cáo ----------------
def _safe(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", name, flags=re.UNICODE)[:80] or "file"


def compare_file(path: Path, claude_fn=run_claude, gemini_fn=run_gemini, out_dir: Path = OUT_DIR) -> dict:
    """Đọc một file bằng cả hai bên, lưu bản chép và trả kết quả so sánh. Lỗi một bên không làm mất bên kia."""
    parts = load_parts(path)
    res: dict = {"file": path.name, "pages": sum(p["pages"] for p in parts)}
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, fn in (("claude", claude_fn), ("gemini", gemini_fn)):
        try:
            r = fn(parts)
            res[key] = r
            (out_dir / f"{_safe(path.stem)}.{key}.md").write_text(r["text"], encoding="utf-8")
        except Exception as e:  # noqa: BLE001 - báo lỗi từng bên rồi đi tiếp
            res[key] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    if "text" in res["claude"] and "text" in res["gemini"]:
        res["diff"] = compare_texts(res["claude"]["text"], res["gemini"]["text"])
    return res


def format_report(results: list[dict]) -> str:
    lines = ["# So sánh đọc scan: Claude và Gemini", "",
             "Độ trùng từ cao chưa chắc đúng; phải mở bản chép và đối chiếu file gốc, nhất là các con số.", ""]
    tot = {"claude": 0.0, "gemini": 0.0}
    for r in results:
        lines.append(f"## {r['file']} ({r['pages']} trang)")
        for key, name in (("claude", "Claude"), ("gemini", "Gemini")):
            x = r[key]
            if "error" in x:
                lines.append(f"- {name}: LỖI – {x['error']}")
                continue
            tot[key] += x["cost_usd"]
            lines.append(f"- {name} ({x['model']}): {len(x['text'].split())} từ, ${x['cost_usd']:.4f}, {x['seconds']:.0f}s"
                         + (f", lưu ý: {'; '.join(x['notes'])}" if x["notes"] else ""))
        d = r.get("diff")
        if d:
            lines.append(f"- Độ trùng từ (F1): {d['word_f1']:.1%}; số liệu: Claude {d['numbers_a']}, Gemini {d['numbers_b']}")
            lines.append(f"- Số chỉ Claude có: {', '.join(d['only_a'][:30]) or '(không)'}")
            lines.append(f"- Số chỉ Gemini có: {', '.join(d['only_b'][:30]) or '(không)'}")
        lines.append("")
    lines.append(f"**Tổng chi phí:** Claude ${tot['claude']:.4f}, Gemini ${tot['gemini']:.4f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="So sánh đọc scan Claude và Gemini (mặc định chỉ ước tính chi phí).")
    ap.add_argument("files", nargs="+", type=Path, help=f"PDF hoặc ảnh, tối đa {MAX_FILES} file")
    ap.add_argument("--run", action="store_true", help="gọi API thật (TỐN TIỀN, gửi nội dung file tới Anthropic và Google)")
    args = ap.parse_args(argv)
    if len(args.files) > MAX_FILES:
        print(f"Tối đa {MAX_FILES} file mỗi lần để tránh tốn tiền ngoài ý muốn.", file=sys.stderr)
        return 2
    missing = [str(f) for f in args.files if not f.is_file()]
    if missing:
        print("Không thấy file: " + ", ".join(missing), file=sys.stderr)
        return 2

    from .ai import ANTHROPIC_MODEL, _price
    claude_price = _price(ANTHROPIC_MODEL)
    total = {"pages": 0, "claude_usd": 0.0, "gemini_usd": 0.0}
    for f in args.files:
        try:
            est = estimate(load_parts(f), claude_price)
        except Exception as e:  # noqa: BLE001
            print(f"{f.name}: không đọc được ({e})", file=sys.stderr)
            return 2
        for k in total:
            total[k] += est[k]
        print(f"{f.name}: {est['pages']} trang, ước tính Claude ${est['claude_usd']:.3f}, Gemini ${est['gemini_usd']:.3f}")
    print(f"TỔNG ước tính ({ANTHROPIC_MODEL} và {gemini_model()}): {total['pages']} trang, "
          f"Claude ${total['claude_usd']:.3f}, Gemini ${total['gemini_usd']:.3f} (ước lượng thô, giá Gemini chưa đối chiếu chính thức)")
    if not args.run:
        print("Đây là chạy thử, chưa gọi API. Thêm --run để chạy thật.")
        return 0

    print("Nội dung các file trên sẽ được gửi tới Anthropic và Google.", flush=True)
    results = [compare_file(f) for f in args.files]
    report = format_report(results)
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"\nBản chép và báo cáo lưu tại {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
