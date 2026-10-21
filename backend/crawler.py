"""Thu thập nội dung website công ty (azb.vn) vào kho tài liệu để trợ lý AI tra cứu.

Mỗi trang web là một dòng trong bảng `documents` (doc_type = 'website', `filename` = URL) và được chia đoạn
vào `doc_chunks` như tài liệu tải lên; file PDF/DOCX/XLSX đính kèm trên web cũng được tải về và trích xuất.
HTML gốc lưu ở `data/web/raw`, file đính kèm ở `data/web/files`. Chạy lại an toàn: trang không đổi thì bỏ qua.

Chạy: .venv\\Scripts\\python -X utf8 -m backend.crawler [--lang vi|en|zh|all] [--limit N] [--delay 0.5]
"""
import argparse
import hashlib
import re
import time
from collections import deque
from pathlib import Path
from urllib import robotparser
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import lxml.html
import requests

from . import documents
from .db import DB_PATH, connect, init_db

BASE = "https://azb.vn"
WEB_DIR = DB_PATH.parent / "web"
RAW_DIR = WEB_DIR / "raw"
FILES_DIR = WEB_DIR / "files"
USER_AGENT = "AZB-Brain-Crawler/1.0 (noi bo cong ty AZB)"
DOC_TYPE = "website"
MAX_PAGES = 2000
SOFT_404_TITLE = "Chúng tôi không tìm thấy trang"
MAX_FILE_BYTES = documents.MAX_UPLOAD_BYTES
SKIP_PATH_PREFIX = ("/files/", "/media/", "/assets/", "/uploads/")
BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "tr", "section", "article", "table", "h1", "h2", "h3", "h4", "h5", "h6",
              "figcaption", "blockquote", "dt", "dd"}
DROP_TAGS = ("script", "style", "noscript", "svg", "form", "iframe", "button", "select")


def lang_of(url: str) -> str:
    first = urlsplit(url).path.strip("/").split("/", 1)[0]
    return first if first in ("en", "zh") else "vi"


def norm_url(url: str) -> str:
    """Chuẩn hoá để loại trùng: bỏ #fragment, giải mã %xx, bỏ '/' cuối (trừ trang chủ)."""
    p = urlsplit(url)
    path = unquote(p.path).rstrip("/") or "/"
    return urlunsplit((p.scheme or "https", p.netloc, path, p.query, ""))


def is_crawlable(url: str, robots: robotparser.RobotFileParser) -> bool:
    p = urlsplit(url)
    if p.netloc not in ("azb.vn", "www.azb.vn"):
        return False
    if "per_page" in p.query or p.path.startswith(SKIP_PATH_PREFIX):  # trang phân trang chỉ lặp lại danh sách
        return False
    return robots.can_fetch(USER_AGENT, url)


class Fetcher:
    def __init__(self, delay: float):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last = 0.0

    def get(self, url: str, **kw) -> requests.Response | None:
        for attempt in range(3):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.session.get(url, timeout=30, **kw)
            except requests.RequestException:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(3 * (attempt + 1))
                continue
            return r
        return None


# ---------------- Trích xuất nội dung trang ----------------
def html_to_text(root) -> str:
    for el in root.xpath("|".join(f".//{t}" for t in DROP_TAGS)):
        el.drop_tree()
    for img in root.xpath(".//img[@alt]"):  # logo đối tác, chứng nhận... chỉ có chữ ở thuộc tính alt
        alt = img.get("alt").strip()
        if len(alt) > 2 and not re.search(r"\.(jpe?g|png|gif|webp)$|^(image|img|photo|hình)\s*\d*$", alt, re.I):
            img.tail = f"\n{alt}\n" + (img.tail or "")
    for br in root.xpath(".//br"):
        br.tail = "\n" + (br.tail or "")
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag in ("td", "th"):
            el.tail = " | " + (el.tail or "")
        elif el.tag in BLOCK_TAGS:
            el.text = "\n" + (el.text or "")
            el.tail = "\n" + (el.tail or "")
    text = root.text_content().replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip(" |\t") for ln in text.splitlines()]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank and out:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def parse_page(html: str, url: str) -> dict:
    doc = lxml.html.fromstring(html)
    doc.make_links_absolute(url)
    title = (doc.findtext(".//title") or "").strip()
    meta = doc.xpath("//meta[@name='description']/@content")
    # nội dung chính nằm trong section.page-content; trang chủ không có thì lấy cả <main>
    body = doc.xpath("//section[contains(@class,'page-content')]") or doc.xpath("//main") or doc.xpath("//body")
    links, attachments = set(), set()
    for a in doc.xpath("//a[@href]|//iframe[@src]|//embed[@src]|//object[@data]"):
        href = a.get("href") or a.get("src") or a.get("data") or ""
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        href = href.split("#")[0]
        if Path(unquote(urlsplit(href).path)).suffix.lower() in documents.ALLOWED_EXT:
            attachments.add(href)
        elif a.tag == "a":
            links.add(href)
    # sách lật (flipbook) nạp PDF qua JavaScript nên không có thẻ <a>
    for m in re.finditer(r"https?:(?:\\?/){2}azb\.vn(?:\\?/)files[^\"'\s<>]*?\.(?:pdf|docx?|xlsx?)", html, re.I):
        attachments.add(m.group(0).replace("\\/", "/"))
    crumbs = " > ".join(t.strip() for t in doc.xpath("//ul[contains(@class,'breadcrumb')]//li//text()") if t.strip())
    text = html_to_text(body[0]) if body else ""
    if meta and meta[0].strip() and meta[0].strip()[:60] not in text:
        text = meta[0].strip() + "\n\n" + text
    return {"title": title, "text": text, "crumbs": crumbs, "links": links, "attachments": attachments}


# ---------------- Lưu vào kho tài liệu ----------------
def save_document(conn, url: str, title: str, content: str, stored_path: Path, mime: str, size: int,
                  pages: list, page_count: int | None = None, note: str | None = None) -> str:
    """Thêm hoặc cập nhật tài liệu theo URL. Trả về 'new' | 'updated' | 'same'."""
    old = conn.execute("SELECT id, content FROM documents WHERE doc_type = ? AND filename = ?", (DOC_TYPE, url)).fetchone()
    if old and (old["content"] or "") == content:
        return "same"
    if old:
        doc_id = old["id"]
        conn.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("UPDATE documents SET title=?, stored_path=?, mime=?, size_bytes=?, uploaded_at=datetime('now','localtime') "
                     "WHERE id=?", (title, str(stored_path), mime, size, doc_id))
    else:
        doc_id = conn.execute(
            "INSERT INTO documents (unit_id, title, doc_type, filename, stored_path, mime, size_bytes) VALUES (NULL,?,?,?,?,?,?)",
            (title, DOC_TYPE, url, str(stored_path), mime, size)).lastrowid
    for i, (page_no, text) in enumerate(documents.chunk(pages)):
        conn.execute("INSERT INTO doc_chunks (text, doc_id, chunk_no, page) VALUES (?,?,?,?)", (text, doc_id, i, page_no))
    conn.execute("UPDATE documents SET extract_status='ok', extract_note=?, content=?, page_count=?, char_count=? WHERE id=?",
                 (note, content, page_count, len(content), doc_id))
    return "updated" if old else "new"


def save_page(conn, url: str, html: bytes, page: dict) -> str:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw = RAW_DIR / (hashlib.sha1(norm_url(url).encode()).hexdigest()[:16] + ".html")
    raw.write_bytes(html)
    title = re.sub(r"\s*\|\s*AZB\s*$", "", page["title"]) or unquote(urlsplit(url).path)
    head = [title, f"Nguồn: {url}"]
    if page["crumbs"]:
        head.append(f"Mục: {page['crumbs']}")
    content = "\n".join(head) + "\n\n" + page["text"]
    return save_document(conn, url, title, content, raw, "text/html", len(html), [(None, content)])


def save_attachment(conn, url: str, fetcher: Fetcher, use_ocr: bool = False) -> str:
    name = documents.safe_filename(unquote(Path(urlsplit(url).path).name))
    dest = FILES_DIR / (hashlib.sha1(norm_url(url).encode()).hexdigest()[:10] + "_" + name)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        r = fetcher.get(url, stream=True)
        if r is None or r.status_code != 200:
            return "error"
        size = int(r.headers.get("Content-Length") or 0)
        if size > MAX_FILE_BYTES:
            return "skipped-large"
        data = r.content
        if len(data) > MAX_FILE_BYTES:
            return "skipped-large"
        dest.write_bytes(data)
    try:
        # PDF scan chỉ đọc bằng Gemini (tốn phí) khi chạy với --ocr
        result = documents.extract(dest, use_ocr=use_ocr)
    except Exception as e:
        return f"error ({e})"
    content = "\n\n".join(p for _, p in result["pages"])
    title = f"{Path(unquote(urlsplit(url).path)).stem} (file đính kèm trên website)"
    if not content.strip():
        return f"no-text ({result['note'] or 'không có chữ'})"
    return save_document(conn, url, title, f"{title}\nNguồn: {url}\n\n{content}", dest, "application/octet-stream",
                         dest.stat().st_size, result["pages"], result["page_count"], result["note"])


# ---------------- Điều phối ----------------
def sitemap_urls(fetcher: Fetcher) -> list[str]:
    r = fetcher.get(f"{BASE}/sitemap.xml")
    if r is None or r.status_code != 200:
        return []
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", r.content.decode("utf-8", "replace"))


def crawl(lang: str = "vi", limit: int = MAX_PAGES, delay: float = 0.5, ocr: bool = False) -> dict:
    init_db()
    fetcher = Fetcher(delay)
    robots = robotparser.RobotFileParser()
    r = fetcher.get(f"{BASE}/robots.txt")
    robots.parse(r.text.splitlines() if r is not None and r.status_code == 200 else [])

    wanted = lambda u: lang == "all" or lang_of(u) == lang  # noqa: E731
    queue, seen = deque(), set()

    def enqueue(u: str) -> None:
        k = norm_url(u)
        if k not in seen and wanted(k) and is_crawlable(k, robots):
            seen.add(k)
            queue.append(u)

    enqueue(BASE + "/")
    for u in sitemap_urls(fetcher):
        enqueue(u)
    print(f"Hàng đợi ban đầu: {len(queue)} trang (ngôn ngữ: {lang})")

    stats = {"new": 0, "updated": 0, "same": 0, "error": 0, "files": 0, "file_problems": [], "errors": []}
    done_files: set[str] = set()
    n = 0
    with connect() as conn:
        while queue and n < limit:
            url = queue.popleft()
            n += 1
            r = fetcher.get(url)
            if r is None or r.status_code != 200 or "html" not in r.headers.get("Content-Type", ""):
                stats["error"] += 1
                stats["errors"].append(f"{url} -> {'không kết nối' if r is None else r.status_code}")
                continue
            html = r.content
            page = parse_page(html.decode("utf-8", "replace"), url)
            if page["title"].startswith(SOFT_404_TITLE):  # site trả 200 cho đường dẫn không tồn tại
                stats["error"] += 1
                stats["errors"].append(f"{url} -> trang không tồn tại (soft 404)")
                continue
            if len(page["text"]) >= 40:
                stats[save_page(conn, url, html, page)] += 1
            elif not page["attachments"]:  # trang sách lật chỉ có tiêu đề, nội dung nằm ở file PDF đính kèm
                stats["error"] += 1
                stats["errors"].append(f"{url} -> trang trống")
                continue
            for link in page["links"]:  # phát hiện trang chưa có trong sitemap
                enqueue(link)
            for att in page["attachments"]:
                key = norm_url(att)
                if key in done_files or urlsplit(att).netloc not in ("azb.vn", "www.azb.vn") \
                        or not robots.can_fetch(USER_AGENT, att):
                    continue
                done_files.add(key)
                res = save_attachment(conn, att, fetcher, ocr)
                if res in ("new", "updated", "same"):
                    stats["files"] += 1
                else:
                    stats["file_problems"].append(f"{att} -> {res}")
            conn.commit()
            if n % 20 == 0:
                print(f"  ...{n} trang (mới {stats['new']}, cập nhật {stats['updated']}, không đổi {stats['same']})")
    stats["pages_visited"] = n
    stats["remaining"] = len(queue)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Thu thập website azb.vn vào kho tài liệu")
    ap.add_argument("--lang", choices=["vi", "en", "zh", "all"], default="vi")
    ap.add_argument("--limit", type=int, default=MAX_PAGES, help="số trang tối đa")
    ap.add_argument("--delay", type=float, default=0.5, help="giây nghỉ giữa các request")
    ap.add_argument("--ocr", action="store_true", help="đọc PDF scan đính kèm bằng Gemini (tốn phí API)")
    a = ap.parse_args()
    s = crawl(a.lang, a.limit, a.delay, a.ocr)
    print(f"\nĐã duyệt {s['pages_visited']} trang: mới {s['new']}, cập nhật {s['updated']}, không đổi {s['same']}, "
          f"lỗi {s['error']}; file đính kèm đọc được: {s['files']}; còn trong hàng đợi: {s['remaining']}")
    for line in s["errors"][:20]:
        print("  LỖI:", line)
    for line in s["file_problems"][:20]:
        print("  FILE:", line)


if __name__ == "__main__":
    main()
