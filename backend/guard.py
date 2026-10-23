"""Phòng thủ cho trợ lý AI: chống "prompt injection" trong tài liệu, giới hạn tần suất hỏi và che dữ liệu cá nhân.

Nguyên tắc:
- Mọi chữ do công cụ trả về (nội dung tài liệu, tên file, trang web) là DỮ LIỆU KHÔNG ĐÁNG TIN. Trước khi đưa cho AI,
  ký tự ẩn bị xoá và các câu mang dạng "chỉ dẫn gửi AI" bị vô hiệu hoá (kèm cờ cảnh báo để ghi nhật ký và báo người hỏi).
- Đây chỉ là lớp bổ sung. Lớp chính là quyền hạn: AI chỉ có công cụ ĐỌC, chạy trên kết nối database chỉ-đọc
  (xem ai._run_tool), nên dù bị lừa AI cũng không có cách gửi email, xoá hay sửa dữ liệu.
- Câu trả lời của AI bị bỏ ảnh/link markdown trỏ ra ngoài (ảnh tự tải về = kênh âm thầm đưa dữ liệu ra ngoài).
"""
import os
import re
import time
import unicodedata
from collections import defaultdict, deque

from fastapi import HTTPException

NEUTRALIZED = "[nội dung bị vô hiệu hoá: giống chỉ dẫn ép AI]"

# Ký tự tàng hình hay dùng để giấu lệnh trong tài liệu: zero-width, đổi chiều chữ, khối "tag" U+E0000.
_HIDDEN_TAGS = re.compile("[\U000e0000-\U000e007f]")
_INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿\U000e0000-\U000e007f]")

# Mẫu chạy trên bản đã bỏ dấu + chữ thường (xem _fold), nên viết không dấu. Cố ý hẹp để ít báo nhầm văn bản ISO bình thường
# (vd "gửi email cho trưởng phòng" là quy trình hợp lệ, không bị chặn).
_PATTERNS = [re.compile(p) for p in (
    r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|any|your|the|system)\b"
    r"[^.\n]{0,30}\b(instructions?|prompts?|rules?|guidelines?|directions?)\b",
    r"\b(bo qua|quen di|phot lo|vo hieu hoa|khong can tuan theo)\b[^.\n]{0,40}\b(huong dan|chi dan|chi thi|quy tac|lenh|prompt|yeu cau)\b",
    r"\b(system prompt|developer message|developer mode|jailbreak|dan mode|prompt he thong)\b",
    r"\b(you are now|from now on,? you|tu bay gio,? (ban|ai|tro ly))\b",
    r"\b(reveal|print|show|leak|repeat|tiet lo|in ra|hien thi)\b[^.\n]{0,30}\b(system prompt|api key|password|mat khau|khoa api|prompt he thong)\b",
    r"\b(do not|don'?t|never|khong duoc|dung)\b[^.\n]{0,20}\b(tell|inform|mention|noi cho|bao cho)\b[^.\n]{0,20}\b(the user|nguoi dung|nguoi hoi|tgd)\b",
    r"<\|?(im_start|im_end|system|endoftext)\|?>",
    r"\[/?(inst|sys)\]",
    r"\b(assistant|ai|tro ly|chatbot)\b[^.\n]{0,25}\b(must|phai|bat buoc)\b[^.\n]{0,40}\b(send|email|delete|xoa|gui|upload|forward|chuyen tiep)\b",
)]


def _fold(s: str) -> str:
    """Bỏ dấu + chữ thường nhưng GIỮ NGUYÊN độ dài (từng ký tự một) để vị trí khớp trùng với văn bản gốc."""
    out = []
    for c in s:
        base = "d" if c in "đĐ" else unicodedata.normalize("NFD", c)[0]
        low = base.lower()
        out.append(low if len(low) == 1 else base)
    return "".join(out)


def sanitize_text(text: str) -> tuple[str, int]:
    """(văn bản đã làm sạch, số điểm đáng ngờ). Xoá ký tự ẩn; thay các câu giống chỉ dẫn gửi AI bằng NEUTRALIZED."""
    if not text:
        return text, 0
    flags = 1 if _HIDDEN_TAGS.search(text) else 0
    text = _INVISIBLE.sub("", unicodedata.normalize("NFC", text))
    folded = _fold(text)
    spans = sorted(m.span() for p in _PATTERNS for m in p.finditer(folded))
    if not spans:
        return text, flags
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out, pos = [], 0
    for a, b in merged:
        out += [text[pos:a], NEUTRALIZED]
        pos = b
    out.append(text[pos:])
    return "".join(out), flags + len(merged)


def scan(text: str) -> int:
    """Số điểm đáng ngờ trong văn bản (dùng khi tài liệu mới được tải lên)."""
    return sanitize_text(text)[1]


def sanitize_obj(obj):
    """Làm sạch mọi chuỗi trong kết quả công cụ (dict/list lồng nhau). Trả về (đối tượng mới, tổng số điểm đáng ngờ)."""
    if isinstance(obj, str):
        return sanitize_text(obj)
    if isinstance(obj, list):
        pairs = [sanitize_obj(x) for x in obj]
        return [p[0] for p in pairs], sum(p[1] for p in pairs)
    if isinstance(obj, dict):
        out, total = {}, 0
        for k, v in obj.items():
            out[k], n = sanitize_obj(v)
            total += n
        return out, total
    return obj, 0


_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)|!\[([^\]]*)\]\[[^\]]*\]")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((?!#)[^)]*\)")


def clean_answer(text: str) -> str:
    """Bỏ ảnh/link markdown trong câu trả lời (ảnh tự tải về có thể mang dữ liệu ra ngoài qua đường dẫn)."""
    text = _MD_IMAGE.sub(lambda m: m.group(1) or m.group(2) or "", text or "")
    return _MD_LINK.sub(r"\1", text)


# Dữ liệu cá nhân không bao giờ gửi cho nhà cung cấp AI (SĐT/email đã xử lý riêng trong contacts.py).
PII_KEYS = {"email", "phone", "birth_date", "joined_date", "contract_term", "labor_group", "employee_code"}
# Nhân sự gửi cho AI: chỉ những trường này (ghi chú nội bộ, ngày sinh, hợp đồng... ở lại máy chủ).
EMPLOYEE_AI_FIELDS = ("id", "full_name", "display_name", "job_title", "grade", "unit_id", "unit_name", "hr_department",
                      "hr_division", "status", "verified", "roles")


def strip_pii(obj):
    if isinstance(obj, list):
        return [strip_pii(x) for x in obj]
    if isinstance(obj, dict):
        return {k: strip_pii(v) for k, v in obj.items() if k not in PII_KEYS}
    return obj


# ---------------- Giới hạn tần suất hỏi AI ----------------
AI_PER_MINUTE = int(os.environ.get("AZB_AI_PER_MINUTE", "8"))
AI_PER_DAY = int(os.environ.get("AZB_AI_PER_DAY", "300"))
MAX_QUESTION_CHARS = int(os.environ.get("AZB_MAX_QUESTION_CHARS", "4000"))
_asked: dict[int, deque] = defaultdict(deque)


def check_ai_rate(user_id: int, now: float | None = None) -> None:
    """Mỗi tài khoản tối đa AI_PER_MINUTE câu/phút và AI_PER_DAY câu/ngày (chống lạm dụng, tốn hạn mức, dò dữ liệu hàng loạt)."""
    now = time.time() if now is None else now
    q = _asked[user_id]
    while q and now - q[0] > 86400:
        q.popleft()
    if len(q) >= AI_PER_DAY:
        raise HTTPException(429, "Đã dùng hết số câu hỏi AI trong ngày của tài khoản này")
    if sum(1 for t in q if now - t < 60) >= AI_PER_MINUTE:
        raise HTTPException(429, "Bạn hỏi quá nhanh, vui lòng chờ ít giây rồi hỏi tiếp")
    q.append(now)
