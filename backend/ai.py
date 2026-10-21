"""Trợ lý AI cho Tổng Giám đốc: Groq hoặc Gemini + công cụ đọc dữ liệu công ty (chỉ đọc).

AI không "học thuộc" dữ liệu bằng fine-tune; mỗi câu hỏi nó tra cứu trực tiếp database qua các tool bên dưới,
nên dữ liệu vừa cập nhật là dùng được ngay và câu trả lời luôn dẫn được nguồn.
"""
import json
import os
import re
import time

from pathlib import Path

import httpx
from google import genai
from google.genai import errors, types

from . import analytics, documents
from .db import connect, row, rows

# Cho phép đặt khoá trong file .env ở thư mục gốc dự án (GEMINI_API_KEY=...)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))

GEMINI_MODEL = os.environ.get("AZB_GEMINI_MODEL", "gemini-3.8-flash")
GROQ_MODEL = os.environ.get("AZB_GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Nhà cung cấp AI cho trợ lý: AI_PROVIDER=groq|gemini; bỏ trống thì có GROQ_API_KEY là dùng Groq, không thì Gemini.
# Đọc PDF scan (OCR) luôn dùng Gemini vì Groq không nhận file PDF.
PROVIDER = (os.environ.get("AI_PROVIDER") or ("groq" if os.environ.get("GROQ_API_KEY") else "gemini")).strip().lower()
MODEL = os.environ.get("AZB_MODEL") or (GROQ_MODEL if PROVIDER == "groq" else GEMINI_MODEL)
MAX_TOOL_ROUNDS = 20

# Hạn mức tính THEO TỪNG MODEL: hết hạn mức model này thì thử model kế tiếp (rồi sang hãng còn lại).
GEMINI_FALLBACKS = [m.strip() for m in os.environ.get(
    "AZB_GEMINI_FALLBACKS", "gemini-3.6-flash,gemini-3.5-flash,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-3.5-flash-lite"
).split(",") if m.strip()]
GROQ_FALLBACKS = [m.strip() for m in os.environ.get(
    "AZB_GROQ_FALLBACKS", "openai/gpt-oss-20b,qwen/qwen3.8-27b").split(",") if m.strip()]

SYSTEM_PROMPT = """Bạn là trợ lý điều hành cấp cao của Công ty Cổ phần AZB (doanh nghiệp xây lắp), phục vụ Tổng Giám đốc.
Nhiệm vụ: giúp TGĐ nắm toàn cục công ty – cơ cấu tổ chức, nhân sự, quy trình vận hành/ISO, mục tiêu doanh thu, doanh số –
và đưa ra đề xuất cải tiến quy trình, tối ưu bộ máy, phân bổ nhân sự.

Cách làm việc:
- Luôn tra cứu dữ liệu bằng các công cụ được cung cấp trước khi trả lời câu hỏi về sự thật của công ty. Không bịa tên người,
  số liệu hay quy trình. Nếu dữ liệu chưa có (quy trình, mục tiêu đang trống), nói rõ là chưa có và đề nghị bổ sung gì.
- Phân biệt rõ: (1) dữ kiện lấy từ dữ liệu, (2) nhận định/suy luận của bạn, (3) đề xuất. Với đề xuất, nêu lý do, tác động,
  rủi ro và dữ liệu cần thêm để kiểm chứng.
- Đề xuất cắt giảm hay điều chuyển nhân sự chỉ là gợi ý để TGĐ cân nhắc: cần dựa trên khối lượng công việc, KPI và chi phí.
  Khi thiếu các dữ liệu đó, nói rõ mức độ tin cậy thấp. Không đánh giá năng lực cá nhân khi không có dữ liệu.
- Một số tên người và giải nghĩa viết tắt phòng ban đang ở trạng thái "cần xác nhận" (verified = 0); nhắc khi dùng đến.
  Tên đơn vị: dùng đúng tên đầy đủ (full_name) có trong dữ liệu, KHÔNG tự diễn giải chữ viết tắt (vd: không tự viết
  "CCM = Quản lý Chi phí" nếu dữ liệu ghi khác). Tên chưa xác nhận thì ghi kèm "(tên đầy đủ chưa được xác nhận)".
- "TBA" hoặc employee_id rỗng nghĩa là chức danh đang trống.
- Có hai nguồn nhân sự: (1) positions = chức danh trên sơ đồ tổ chức (headcount là định biên, KHÔNG phải số người thực tế);
  (2) members = danh sách nhân viên thực tế do HCNS cập nhật (kèm mã NV, chức danh, ngạch). Hỏi số người / ai làm trong một
  đơn vị: dùng get_unit_detail và trả lời theo member_count + members; chỉ nhắc định biên khi so sánh. Người phụ trách đơn vị
  lấy từ positions (is_head) hoặc người đứng đầu members. Nhân sự toàn công ty: list_employees. Đừng nói "dữ liệu chưa có
  danh sách nhân viên".
- ĐỘ CHÍNH XÁC KHI HỎI VỀ MỘT ĐƠN VỊ (quan trọng nhất): (a) gọi search với tên đơn vị NGẮN (ví dụ "IT", "kế toán", "MMTB"),
  không dán nguyên câu hỏi; (b) lấy đúng đơn vị có điểm khớp cao nhất rồi gọi get_unit_detail để xác minh tên đơn vị
  đúng là đơn vị được hỏi; (c) TUYỆT ĐỐI không đoán sang đơn vị khác chỉ vì tên "gần nghĩa" (vd: Ban Hệ thống/ISO KHÔNG phải
  Phòng IT). Nếu search không ra đơn vị nào, thử từ khoá khác (viết tắt / tên đầy đủ) hoặc xem get_org_overview; nếu vẫn không
  chắc thì hỏi lại TGĐ chứ không tự chọn; (d) câu trả lời luôn mở đầu bằng tên đầy đủ của đơn vị đang nói tới
  (vd: "Phòng Công nghệ thông tin (P. IT): ...") để TGĐ thấy ngay AI đã hiểu đúng đơn vị.
- Người phụ trách/"ai quản lý" một đơn vị: lấy từ trường người đứng đầu của đơn vị đó (head) và nêu đúng chức danh thật
  (Trưởng phòng / Phó phòng phụ trách...). Nếu người đứng đầu là cấp phó thì nói rõ "do Phó phòng ... phụ trách". Số nhân sự = số
  người trong danh sách nhân viên thực tế của CHÍNH đơn vị đó; không được lấy số định biên trên sơ đồ để trả lời là "0 người"
  khi danh sách nhân viên có người. Nếu một đơn vị thật sự chưa có nhân viên trong danh sách, nói rõ "chưa có dữ liệu nhân viên".
  Nếu hai nguồn lệch nhau, nêu cả hai và ghi chú.
- TÀI LIỆU (quy trình ISO, quy định, hướng dẫn, biểu mẫu, RAM, kế hoạch, ngân sách...) nằm trong kho tài liệu, KHÔNG nằm
  trong mục "quy trình" của đơn vị (mục đó thường trống). Không bao giờ kết luận "đơn vị chưa có quy trình" chỉ vì mục quy
  trình trống: xem danh sách tài liệu của đơn vị (documents trong get_unit_detail) và search_documents.
  * search_documents tự khớp cả tên file, mã tài liệu và nội dung, không phân biệt dấu (QĐ = QD, "quy định" = "QUY DINH"),
    tự mở rộng cách gọi tương đương (ngân sách ~ dự toán, quy trình ~ QT...). Mỗi kết quả có "match" (mức khớp), "missing"
    (ý chưa khớp) và có thể có "note": kết quả khớp một phần KHÔNG phải là câu trả lời, phải đọc kỹ hoặc tìm tiếp.
  * Snippet chỉ là trích đoạn: trước khi trả lời về nội dung, gọi read_document với from_chunk = chunk_no của kết quả để đọc
    đúng đoạn đó (đọc tiếp nếu bước/quy định kéo dài sang đoạn sau). Không suy diễn nội dung từ tên tài liệu.
  * Trước khi kết luận "chưa có tài liệu / chưa có quy định": (1) search_documents ít nhất 3 cách diễn đạt khác nhau (tên
    đầy đủ, viết tắt, cách gọi khác); (2) xem danh sách tài liệu của đơn vị liên quan (get_unit_detail hoặc list_documents)
    và tự đọc TÊN từng tài liệu xem có cái nào cùng nội dung dù đặt tên khác; (3) nói rõ đã tìm những gì. Chỉ khi cả ba
    bước đều không ra mới nói "chưa tìm thấy trong kho tài liệu" (không nói "công ty không có").
  * Nhiều phiên bản cùng một tài liệu (REV00, REV01, ngày ban hành khác nhau): dùng bản mới nhất và ghi rõ phiên bản; nếu các
    bản mâu thuẫn nhau, nêu cả hai.
  * Tài liệu loại "Website azb.vn" (tin tức, hồ sơ năng lực) là tài liệu giới thiệu, KHÔNG phải quy định nội bộ: không trích
    chúng như quy trình/quy định.
  * Khi trích dẫn, ghi rõ tên/mã tài liệu (và trang nếu có). Cuối câu trả lời có dùng tài liệu, thêm dòng "Nguồn:" liệt kê
    tên các tài liệu đã dùng.
- Mục tiêu/chỉ tiêu/kế hoạch năm (doanh thu, doanh số, WIG, KRI, KPI, ngân sách) thường nằm trong tài liệu được tải lên, không
  chỉ ở bảng mục tiêu có cấu trúc. Nếu bảng mục tiêu trống, PHẢI dùng search_documents/read_document trước khi kết luận là chưa có.
- SỐ LIỆU: chép đúng con số và đơn vị tính trong tài liệu (VNĐ, triệu, tỷ, %, người...), ghi rõ kỳ/năm của số liệu. Khi tự
  tính (cộng, tỷ lệ, chênh lệch) thì ghi phép tính để TGĐ kiểm tra được. Không tự làm tròn, không suy ra số liệu tài liệu
  không có. Bảng tính trích từ Excel có thể lệch cột: đối chiếu tên cột/dòng trước khi đọc số.
- Câu trả lời trước trong cùng đoạn chat có thể sai hoặc thiếu. Với câu hỏi mới về dữ kiện, luôn tra cứu lại thay vì lặp
  lại kết luận cũ; nếu kết quả mới khác câu trả lời trước, nói rõ là đã điều chỉnh.
- Mức độ chắc chắn: nếu kết luận dựa trên kết quả khớp một phần, tài liệu cũ, hoặc suy luận của bạn, nói rõ điều đó.
- AZB là NHÀ THẦU XÂY DỰNG (tổng thầu xây dựng, thi công nội thất, dịch vụ thiết kế); AZB không tự sản xuất hàng hoá. Trong
  hồ sơ năng lực (Profile), "danh mục dự án" chia theo ngành của CHỦ ĐẦU TƯ (may mặc & dệt may, thực phẩm, kim loại, hoá chất,
  chăn nuôi...) là các loại nhà máy/công trình AZB đã xây cho khách hàng, KHÔNG phải sản phẩm hay lĩnh vực kinh doanh của AZB.
  Khi được hỏi về sản phẩm/dịch vụ/lĩnh vực của AZB, nói rõ điều này và nêu các dự án tiêu biểu theo từng ngành.
- Chỉ mô tả những gì có trong tài liệu. Không tự viết thêm phần giải thích/mô tả mà tài liệu không nêu; nếu tài liệu chỉ có
  tên dự án thì nói "tài liệu chỉ liệt kê tên dự án". Trước khi kết luận về hoạt động kinh doanh, đọc đoạn ngữ cảnh quanh kết
  quả tìm được (read_document) để hiểu mục đó đang nói về cái gì.
- CÂU HỎI ĐỐI CHIẾU / SUY LUẬN (vd: "A có bao quát hết B không", "còn thiếu mục nào", "có phù hợp quy định không"):
  làm theo đúng thứ tự, không tra cứu lan man: (1) xác định hai vế cần so sánh (vd: RAM/ma trận phân công trách nhiệm
  và quy trình/quy định liên quan); dùng list_documents hoặc search_documents với từ khoá ngắn để tìm đúng tài liệu cho
  TỪNG vế (thử cả tên đầy đủ và viết tắt, vd "RAM" và "ma trận phân công trách nhiệm"); (2) đọc từng tài liệu bằng
  read_document và tự ghi ra danh sách các mục của vế đó; (3) so sánh từng mục, chỉ ra mục khớp, mục thiếu, mục chồng chéo
  hoặc chưa có người chịu trách nhiệm; (4) mới kết luận. Không tìm lại cùng một từ khoá hay đọc lại đoạn đã đọc. Tối đa
  khoảng 10 lần tra cứu; nếu một vế không tìm thấy tài liệu thì nói rõ là chưa có và dừng, đừng đoán. Cuối cùng trả lời
  theo dạng: kết luận ngắn (có/không/một phần) → bảng đối chiếu từng mục → đề xuất bổ sung.
- Khi phân tích quy trình: chỉ ra bước trùng lặp, điểm chờ duyệt kéo dài, trách nhiệm chồng chéo hoặc bỏ trống giữa các
  phòng ban, và chỗ có thể số hoá/tự động hoá.
- KHÔNG BAO GIỜ hứa hoặc nói sẽ làm việc gì sau câu trả lời này: không "tôi sẽ kiểm tra lại", "tôi sẽ mở rộng tìm kiếm",
  "tôi sẽ báo cáo sau", "tôi sẽ hỏi Trưởng phòng". Bạn chỉ trả lời trong lượt này bằng dữ liệu đã tra cứu. Không tự xưng
  là nhân viên đi xác minh hay liên hệ người khác. Nếu cần xác minh thêm, chỉ gợi ý TGĐ nên hỏi ai hoặc bổ sung tài liệu gì.
- Không tự bịa quy trình, đầu việc hay cơ chế nội bộ khi tài liệu không có. Thay vì đề xuất xây dựng quy trình như một
  cam kết, chỉ nêu đây là khoảng trống cần TGĐ quyết định.
- LIÊN HỆ (SĐT, email): hệ thống KHÔNG đưa số điện thoại hay email cho bạn. Khi người hỏi xin liên hệ của một người, hãy
  viết họ tên đầy đủ rồi ngay sau đó là dấu [[LH:<id>]] với id lấy từ trường id của người đó trong danh sách nhân sự
  (vd: "Nguyễn Văn A [[LH:12]]"). Tuyệt đối không tự viết số điện thoại hay email; không đoán id; nếu không chắc đúng người
  thì nói rõ và hỏi lại họ tên đầy đủ thay vì đưa dấu.
- Người đọc là Tổng Giám đốc, không phải dân kỹ thuật: TUYỆT ĐỐI không nêu tên công cụ, tên trường dữ liệu, mã hệ thống hay
  thuật ngữ IT (như get_unit_detail, employee_id, verified, positions, members, id đơn vị, database, tool...) trong câu trả
  lời. Không có câu kiểu "Dữ liệu lấy từ ...". Đặc biệt không viết "verified = 0", "member_count"... Thay bằng tiếng Việt thường: "danh sách nhân sự", "sơ đồ tổ chức", "đã được
  xác nhận", "chưa xác nhận", "chức danh đang trống"...
- Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào kết luận trước rồi mới đến chi tiết. Dùng bảng hoặc gạch đầu dòng khi
  so sánh nhiều đơn vị."""


def _system_prompt(extra: str = "") -> str:
    """Prompt hệ thống kèm ngày hiện tại (để hiểu đúng "năm nay", "quý này") và ghi chú riêng của đoạn chat."""
    today = time.strftime("%d/%m/%Y")
    prompt = SYSTEM_PROMPT + (f"\n- Hôm nay là ngày {today}. \"Năm nay\", \"tháng này\", \"quý này\" tính theo ngày này; nếu "
                              "tài liệu tìm được là của năm/kỳ khác thì nói rõ năm/kỳ của tài liệu.")
    return prompt + (f"\n- {extra}" if extra else "")


def _tool(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters_json_schema": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
        },
    }


TOOLS = [
    _tool("get_org_overview",
          "Cây sơ đồ tổ chức đầy đủ: HĐQT, Ban TGĐ, các PTGĐ, khối, phòng/ban (tên + tên đầy đủ), người phụ trách và số tài liệu "
          "nội bộ (quy trình/quy định/RAM) của từng đơn vị. Dùng đầu tiên khi cần bức tranh toàn cục."),
    _tool("get_unit_detail",
          "Chi tiết một đơn vị: chức năng, cấp trên, đơn vị con, toàn bộ chức danh và người giữ (positions, theo sơ đồ), "
          "danh sách nhân viên thực tế (members/member_count, theo HCNS), danh sách TÀI LIỆU của đơn vị (documents: quy trình, "
          "quy định, RAM... kèm doc_id để đọc), mục tiêu.",
          {"unit_id": {"type": "integer", "description": "id đơn vị (lấy từ get_org_overview hoặc search)"}},
          ["unit_id"]),
    _tool("search", "Tìm đơn vị, nhân sự, quy trình theo từ khoá NGẮN (tên gọi/viết tắt như \"IT\", \"kế toán\", \"HSSE\", tên người). "
                    "Không phân biệt dấu/hoa thường. Kết quả đơn vị xếp theo match_score (cao = khớp tốt); danh sách rỗng nghĩa là "
                    "KHÔNG có đơn vị đó, không được đoán đơn vị khác.",
          {"query": {"type": "string"}}, ["query"]),
    _tool("list_employees", "Danh sách nhân sự kèm toàn bộ chức danh từng người đang giữ (thấy được kiêm nhiệm). "
                            "Trường id dùng cho dấu [[LH:id]] khi cần cung cấp liên hệ; hệ thống không đưa SĐT/email."),
    _tool("get_org_insights",
          "Chỉ dấu tổ chức tính sẵn: thống kê tổng, vị trí trống, người kiêm nhiệm nhiều đơn vị, phòng do cấp phó phụ trách, "
          "tầm hạn quản lý, đơn vị chưa có quy trình / mục tiêu, dữ liệu cần xác nhận."),
    _tool("get_process", "Toàn văn một quy trình (mục đích, chủ trì, phối hợp, các bước).",
          {"process_id": {"type": "integer"}}, ["process_id"]),
    _tool("list_documents",
          "Danh sách TÊN tài liệu trong kho (quy trình ISO, quy định, hướng dẫn, biểu mẫu, RAM, tài liệu website), có thể lọc "
          "theo đơn vị và loại. Dùng khi search_documents không ra để tự dò theo tên (tài liệu có thể đặt tên khác câu hỏi).",
          {"unit_id": {"type": "integer", "description": "0 = tất cả"},
           "kind": {"type": "string", "enum": ["noi_bo", "website", "tat_ca"],
                    "description": "noi_bo = tài liệu nội bộ (mặc định), website = tin tức/hồ sơ năng lực, tat_ca = cả hai"}},
          ["unit_id"]),
    _tool("search_documents",
          "Tìm tài liệu theo tên file, mã tài liệu và nội dung (không phân biệt dấu, QĐ = QD, tự mở rộng cách gọi tương đương). "
          "Mỗi tài liệu một kết quả, xếp theo mức khớp: doc_id, title, doc_type, unit_name, match (%), missing (ý chưa khớp), "
          "chunks (chunk_no, page, snippet). Dùng từ khoá ngắn gồm các ý chính (vd \"kiểm soát ngân sách CCM\"), không dán "
          "nguyên câu hỏi. unit_id lọc theo đơn vị (vẫn gồm tài liệu toàn công ty chưa gắn đơn vị).",
          {"query": {"type": "string"}, "unit_id": {"type": "integer", "description": "0 = mọi đơn vị"}},
          ["query", "unit_id"]),
    _tool("read_document",
          "Đọc nội dung tài liệu theo đoạn (chunk), bắt đầu từ from_chunk (dùng chunk_no trong kết quả search_documents để "
          "đọc đúng chỗ). Đọc tiếp bằng from_chunk lớn hơn khi has_more = true.",
          {"doc_id": {"type": "integer"}, "from_chunk": {"type": "integer", "description": "bắt đầu từ 0"}},
          ["doc_id", "from_chunk"]),
    _tool("list_targets",
          "Mục tiêu doanh thu/doanh số/chỉ tiêu theo kỳ. Bỏ trống unit_id (truyền 0) để lấy toàn công ty.",
          {"unit_id": {"type": "integer", "description": "0 = tất cả"}}, ["unit_id"]),
]


CHUNK_JSON_CHARS = 1800  # một đoạn tài liệu (1.500 ký tự) sau khi đóng gói JSON


def _list_documents(conn, unit_id: int | None, kind: str) -> dict:
    """Danh sách tên tài liệu gọn (để AI tự dò theo tên), gộp bản trùng (cùng tên + cùng độ dài nội dung)."""
    sql = ("SELECT d.id, d.title, d.version, d.doc_type, d.extract_status, d.char_count, d.unit_id, u.name AS unit_name"
           " FROM documents d LEFT JOIN units u ON u.id = d.unit_id WHERE 1 = 1")
    params: list = []
    if unit_id:
        sql += " AND d.unit_id = ?"
        params.append(unit_id)
    if kind == "noi_bo":
        sql += " AND d.doc_type != 'website'"
    elif kind == "website":
        sql += " AND d.doc_type = 'website'"
    out, seen = [], set()
    for d in rows(conn, sql + " ORDER BY u.sort_order, d.title, d.id DESC", params):
        key = (" ".join(documents.fold_words(d["title"])), d["char_count"])
        if key in seen:
            continue
        seen.add(key)
        item = {"doc_id": d["id"], "title": d["title"], "type": documents.DOC_TYPES.get(d["doc_type"], d["doc_type"]),
                "unit": d["unit_name"] or "Toàn công ty / chưa gắn đơn vị"}
        if d["version"]:
            item["version"] = d["version"]
        if d["extract_status"] != "ok":
            item["status"] = "chưa đọc được nội dung"
        out.append(item)
    result: dict = {"count": len(out), "documents": out}
    if not out:
        result["note"] = ("Không có tài liệu nào theo bộ lọc này." + (
            " Tài liệu toàn công ty (chưa gắn đơn vị) không nằm trong danh sách lọc theo đơn vị: thử unit_id = 0."
            if unit_id else ""))
    return result


def _run_tool(name: str, args: dict, char_budget: int | None = None):
    """char_budget: giới hạn độ dài kết quả của nhà cung cấp hiện tại (None = không giới hạn) – để đọc tài liệu vừa đủ,
    không bị cắt mất phần cuối."""
    with connect() as conn:
        if name == "get_org_overview":
            def slim(n):
                # chỉ giữ trường có giá trị để tiết kiệm token (gói Groq miễn phí giới hạn 8000 token/phút)
                out = {"id": n["id"], "name": n["name"], "head": n["head"]}
                if n.get("full_name") and n["full_name"] != n["name"]:
                    out["full_name"] = n["full_name"]
                if not n["verified"]:
                    out["verified"] = 0
                for key, val in (("documents", n.get("doc_count")), ("targets", n["target_count"])):
                    if val:
                        out[key] = val
                if n["children"]:
                    out["children"] = [slim(c) for c in n["children"]]
                return out
            return [slim(r) for r in analytics.org_tree(conn)]
        if name == "get_unit_detail":
            return analytics.unit_detail(conn, args["unit_id"]) or {"error": "Không tìm thấy đơn vị"}
        if name == "search":
            return analytics.search(conn, args["query"])
        if name == "list_employees":
            # Không đưa email/SĐT cho nhà cung cấp AI: liên hệ được điền ở máy chủ, xem backend/contacts.py
            return analytics.employee_roles(conn)
        if name == "get_org_insights":
            return {**analytics.insights(conn), "note": (
                "units_without_process tính theo tài liệu quy trình/quy định/RAM đã tải lên. units_without_target chỉ xét "
                "bảng mục tiêu có cấu trúc (đang ít dùng): mục tiêu thực tế có thể nằm trong tài liệu, phải search_documents "
                "trước khi nói đơn vị chưa có mục tiêu.")}
        if name == "get_process":
            return row(conn, "SELECT * FROM processes WHERE id = ?", (args["process_id"],)) or {"error": "Không tìm thấy"}
        if name == "list_documents":
            return _list_documents(conn, args.get("unit_id") or None, args.get("kind") or "noi_bo")
        if name == "search_documents":
            return documents.ai_search(conn, args["query"], unit_id=args.get("unit_id") or None)
        if name == "read_document":
            count = 6 if char_budget is None else max(1, min(6, (char_budget - 600) // CHUNK_JSON_CHARS))
            return documents.read_chunks(conn, args["doc_id"], max(args.get("from_chunk") or 0, 0), count=count)
        if name == "list_targets":
            if args.get("unit_id"):
                return rows(conn, "SELECT * FROM targets WHERE unit_id = ? ORDER BY period DESC", (args["unit_id"],))
            return rows(conn, "SELECT t.*, u.name AS unit_name FROM targets t LEFT JOIN units u ON u.id = t.unit_id"
                              " ORDER BY t.period DESC")
    return {"error": f"Công cụ không tồn tại: {name}"}


_KEY_NAME = "GROQ_API_KEY" if PROVIDER == "groq" else "GEMINI_API_KEY"
NOT_CONFIGURED = {"answer": f"Chưa cấu hình khoá {PROVIDER.capitalize()} API. Thêm {_KEY_NAME} vào file .env ở thư mục dự án "
                            "(hoặc biến môi trường) rồi khởi động lại server.", "tools_used": [], "error": "not_configured"}


def has_gemini() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def has_credentials() -> bool:
    return bool(os.environ.get("GROQ_API_KEY")) if PROVIDER == "groq" else has_gemini()


def status() -> dict:
    return {"configured": has_credentials(), "model": MODEL, "provider": PROVIDER, "key_name": _KEY_NAME}


def client(timeout_s: int = 45) -> genai.Client:
    """Client Gemini – tự đọc khoá từ GEMINI_API_KEY / GOOGLE_API_KEY."""
    return genai.Client(http_options=types.HttpOptions(timeout=timeout_s * 1000))


def _finish_reason(response) -> str:
    cand = response.candidates[0] if response.candidates else None
    return cand.finish_reason.name if cand and cand.finish_reason else ""


def _has_key(provider: str) -> bool:
    return bool(os.environ.get("GROQ_API_KEY")) if provider == "groq" else has_gemini()


def _model_chain(provider: str) -> list[str]:
    """Model chính của nhà cung cấp (theo cấu hình) rồi đến các model dự phòng, bỏ trùng."""
    first = MODEL if provider == PROVIDER else (GROQ_MODEL if provider == "groq" else GEMINI_MODEL)
    extra = GROQ_FALLBACKS if provider == "groq" else GEMINI_FALLBACKS
    return list(dict.fromkeys([first, *extra]))


def _is_weak(model: str) -> bool:
    """Model loại nhẹ: tuân thủ hướng dẫn và suy luận kém hơn, chỉ dùng khi mọi model mạnh đều hết hạn mức."""
    return bool(re.search(r"lite|(?<!\d)(?:8|20|27)b\b", model.lower()))  # "120b" là model mạnh, không phải "20b"


# Ghi chú hệ thống gắn vào câu trả lời; bị bỏ khi gửi lại lịch sử cho AI để AI không bắt chước.
FALLBACK_NOTE = "_(Lưu ý: mô hình AI chính đang hết hạn mức nên câu này do mô hình dự phòng trả lời"
TRUNCATED_NOTE = "\n\n_(Câu trả lời bị cắt do quá dài.)_"
# mô hình kết thúc mà không có chữ nào: báo lỗi (không lưu) thay vì lưu một câu trả lời rỗng
EMPTY_ANSWER = "Trợ lý chưa đưa ra được câu trả lời cho câu này. Hãy gửi lại câu hỏi."
_SYSTEM_NOTES = re.compile(r"\n*_\(Lưu ý: mô hình AI chính đang hết hạn mức[^\n]*\)_\s*$|\n*_\(Câu trả lời bị cắt do quá dài\.\)_")
MAX_HISTORY_MESSAGES = int(os.environ.get("AZB_MAX_HISTORY_MESSAGES", "12"))


def _prepare_history(history: list[dict]) -> tuple[list[dict], str]:
    """Giữ các lượt gần nhất (đoạn chat dài vừa tốn token vừa dễ làm AI bám vào câu trả lời cũ), bỏ ghi chú hệ thống,
    và báo cho AI biết lượt trả lời nào trước đây KHÔNG tra cứu dữ liệu (có thể sai)."""
    msgs = [m for m in history if m.get("content")]
    current, prev = msgs[-1:], msgs[:-1][-MAX_HISTORY_MESSAGES:]
    while prev and prev[0]["role"] != "user":  # bắt đầu bằng câu hỏi, không bằng câu trả lời bị cắt đôi
        prev = prev[1:]
    out, unchecked = [], 0
    for m in prev:
        content = m["content"]
        if m["role"] == "assistant":
            content = _SYSTEM_NOTES.sub("", content).strip()
            if m.get("tools_used") in ("[]", "", None) and "tools_used" in m:
                unchecked += 1
        out.append({"role": m["role"], "content": content})
    note = ""
    if unchecked:
        note = (f"Trong đoạn chat này có {unchecked} câu trả lời trước đã được đưa ra mà KHÔNG tra cứu dữ liệu, có thể sai: "
                "không dựa vào các kết luận đó, hãy tra cứu lại.")
    return out + current, note


def answer(history: list[dict]) -> dict:
    if not has_credentials():
        return NOT_CONFIGURED
    history, note = _prepare_history(history)
    system = _system_prompt(note)
    other = "gemini" if PROVIDER == "groq" else "groq"
    chain = [(p, m) for p in (PROVIDER, other) if _has_key(p) for m in _model_chain(p)]
    # hết hạn mức → thử lần lượt các model mạnh (của cả hai nhà cung cấp) trước, model nhẹ để sau cùng
    chain = [c for c in chain if not _is_weak(c[1])] + [c for c in chain if _is_weak(c[1])]
    first = None
    started = time.monotonic()
    for provider, model in chain:
        if first and time.monotonic() - started > ANSWER_BUDGET_S:  # quá lâu: tunnel/trình duyệt sẽ cắt request
            break
        result = _answer_with(provider, history, model, system)
        if result.get("error") not in ("rate_limit", "overload"):
            if (provider, model) != chain[0] and not result.get("error"):
                result["answer"] += (f"\n\n{FALLBACK_NOTE}" + (" (loại nhẹ, độ chính xác thấp hơn)" if _is_weak(model) else "")
                                     + ". Với số liệu quan trọng, nên hỏi lại sau ít phút.)_")
            result["model"] = model
            return result
        first = first or result
    return first or NOT_CONFIGURED


def _answer_with(provider: str, history: list[dict], model: str, system: str) -> dict:
    return _answer_groq(history, model, system) if provider == "groq" else _answer_gemini(history, model, system)


GEMINI_RETRY_CODES = (500, 502, 503, 504)
GEMINI_RETRIES = 1  # thử lại nhiều hơn làm chậm việc chuyển sang model dự phòng
ANSWER_BUDGET_S = 45


def _gemini_generate(gemini, contents, config, model):
    """Gọi Gemini, tự thử lại (chờ tăng dần) khi máy chủ quá tải/lỗi tạm thời."""
    for attempt in range(GEMINI_RETRIES + 1):
        try:
            return gemini.models.generate_content(model=model, contents=contents, config=config)
        except errors.APIError as e:
            if e.code not in GEMINI_RETRY_CODES or attempt == GEMINI_RETRIES:
                raise
            time.sleep(2 * 2 ** attempt)


def _answer_gemini(history: list[dict], model: str, system: str) -> dict:
    gemini = client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**t) for t in TOOLS])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH),
        max_output_tokens=16000,
    )
    # vòng đầu bắt buộc gọi công cụ: để "auto" thì mô hình có lúc trả lời luôn mà không tra cứu (rồi kết luận "chưa có")
    first_config = config.model_copy(update={"tool_config": types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode="ANY"))})

    contents = [types.Content(role="model" if m["role"] == "assistant" else "user",
                              parts=[types.Part.from_text(text=m["content"])])
                for m in history if m.get("content")]
    tools_used: list[str] = []

    try:
        for round_no in range(MAX_TOOL_ROUNDS):
            response = _gemini_generate(gemini, contents, first_config if round_no == 0 else config, model)
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                return {"answer": "Yêu cầu này bị từ chối bởi bộ lọc an toàn của mô hình. Hãy diễn đạt lại câu hỏi.",
                        "tools_used": tools_used}
            reason = _finish_reason(response)
            calls = response.function_calls
            if not calls:
                if reason in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
                    return {"answer": "Yêu cầu này bị từ chối bởi bộ lọc an toàn của mô hình. Hãy diễn đạt lại câu hỏi.",
                            "tools_used": tools_used}
                text = (response.text or "").strip()
                if not text:
                    return {"answer": EMPTY_ANSWER, "tools_used": tools_used, "error": "empty"}
                if reason == "MAX_TOKENS":
                    text += TRUNCATED_NOTE
                return {"answer": text, "tools_used": tools_used}

            # giữ nguyên nội dung model trả về (kèm thought signature) để Gemini tiếp tục mạch suy luận
            contents.append(response.candidates[0].content)
            results = []
            for call in calls:
                tools_used.append(call.name)
                try:
                    out = _run_tool(call.name, dict(call.args or {}))
                    payload = {"result": json.loads(json.dumps(out, ensure_ascii=False, default=str))}
                except Exception as e:
                    payload = {"error": str(e)}
                results.append(types.Part.from_function_response(name=call.name, response=payload))
            contents.append(types.Content(role="user", parts=results))

        # hết số vòng tra cứu: buộc mô hình kết luận bằng dữ liệu đã có thay vì bỏ cuộc
        contents.append(types.Content(role="user", parts=[types.Part.from_text(
            text="Dừng tra cứu. Trả lời ngay bằng dữ liệu đã có, nói rõ phần nào dữ liệu chưa có.")]))
        final_config = types.GenerateContentConfig(
            system_instruction=system,
            tools=config.tools,
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="NONE")),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            max_output_tokens=16000,
        )
        response = _gemini_generate(gemini, contents, final_config, model)
        text = (response.text or "").strip()
        if text:
            return {"answer": text, "tools_used": tools_used}
        return {"answer": "Trợ lý đã tra cứu quá nhiều bước mà chưa kết luận. Hãy hỏi cụ thể hơn.", "tools_used": tools_used}
    except errors.APIError as e:
        if e.code in (401, 403) or (e.code == 400 and "API key" in str(e.message)):
            return {"answer": "Khoá Gemini API không hợp lệ.", "tools_used": tools_used, "error": "auth"}
        if e.code == 429:
            return {"answer": f"Gemini đang vượt giới hạn gọi API, thử lại sau ít phút.\n\n_{e.message}_",
                    "tools_used": tools_used, "error": "rate_limit"}
        if e.code in GEMINI_RETRY_CODES:
            return {"answer": f"Gemini đang quá tải ({e.code}).", "tools_used": tools_used, "error": "overload"}
        return {"answer": f"Lỗi từ Gemini API ({e.code}): {e.message}", "tools_used": tools_used, "error": "api"}
    except httpx.TransportError:
        return {"answer": "Không kết nối được tới Gemini API. Kiểm tra mạng.", "tools_used": tools_used, "error": "network"}


# Gói Groq miễn phí giới hạn ~8000 token/phút cho cả request, nên phải cắt bớt kết quả tool.
# Tăng các giá trị này nếu tài khoản Groq có hạn mức cao hơn.
GROQ_TOOL_CHARS = int(os.environ.get("AZB_GROQ_TOOL_CHARS", "8000"))
GROQ_HISTORY_TOOL_CHARS = int(os.environ.get("AZB_GROQ_HISTORY_TOOL_CHARS", "800"))


def _tool_payload(out, limit: int = GROQ_TOOL_CHARS) -> str:
    text = json.dumps({"result": out}, ensure_ascii=False, default=str, separators=(",", ":"))
    return _clip(text, limit)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return (text[:limit] + f"…[ĐÃ CẮT BỚT {len(text) - limit} ký tự do giới hạn token. Dùng công cụ hẹp hơn "
                           "(search, get_unit_detail) hoặc tham số cụ thể hơn để xem phần còn lại.]")


def _answer_groq(history: list[dict], model: str, system: str) -> dict:
    """Groq (API tương thích OpenAI): vòng lặp gọi tool tương tự bản Gemini."""
    headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                "parameters": t["parameters_json_schema"]}} for t in TOOLS]
    messages = [{"role": "system", "content": system}] + [
        {"role": "assistant" if m["role"] == "assistant" else "user", "content": m["content"]}
        for m in history if m.get("content")]
    tools_used: list[str] = []

    try:
        with httpx.Client(timeout=120) as http:
            for round_no in range(MAX_TOOL_ROUNDS):
                # vòng đầu bắt buộc gọi công cụ (xem ghi chú ở _answer_gemini)
                body = {"model": model, "messages": messages, "tools": tools,
                        "tool_choice": "required" if round_no == 0 else "auto",
                        "max_completion_tokens": 16000}
                for attempt in range(GROQ_RETRIES + 1):
                    resp = http.post(GROQ_URL, headers=headers, json=body)
                    wait = _groq_retry_wait(resp)
                    if wait is None or attempt == GROQ_RETRIES:
                        break
                    time.sleep(wait)
                if resp.status_code != 200:
                    return _groq_error(resp, tools_used)
                choice = resp.json()["choices"][0]
                msg = choice["message"]
                calls = msg.get("tool_calls") or []
                if not calls:
                    text = (msg.get("content") or "").strip()
                    if not text:
                        return {"answer": EMPTY_ANSWER, "tools_used": tools_used, "error": "empty"}
                    if choice.get("finish_reason") == "length":
                        text += TRUNCATED_NOTE
                    return {"answer": text, "tools_used": tools_used}

                # rút gọn kết quả tool của các vòng trước để request không vượt hạn mức token
                for m in messages:
                    if m["role"] == "tool":
                        m["content"] = _clip(m["content"], GROQ_HISTORY_TOOL_CHARS)
                messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
                for call in calls:
                    name = call["function"]["name"]
                    tools_used.append(name)
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                        content = _tool_payload(_run_tool(name, args, char_budget=GROQ_TOOL_CHARS))
                    except Exception as e:
                        content = json.dumps({"error": str(e)}, ensure_ascii=False)
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})

            # hết số vòng tra cứu: buộc mô hình kết luận bằng dữ liệu đã có thay vì bỏ cuộc
            messages.append({"role": "user", "content": "Dừng tra cứu. Trả lời ngay bằng dữ liệu đã có, "
                                                        "nói rõ phần nào dữ liệu chưa có."})
            resp = http.post(GROQ_URL, headers=headers, json={
                "model": model, "messages": messages, "tools": tools, "tool_choice": "none",
                "max_completion_tokens": 16000})
            if resp.status_code == 200:
                text = (resp.json()["choices"][0]["message"].get("content") or "").strip()
                if text:
                    return {"answer": text, "tools_used": tools_used}
        return {"answer": "Trợ lý đã tra cứu quá nhiều bước mà chưa kết luận. Hãy hỏi cụ thể hơn.", "tools_used": tools_used}
    except httpx.TransportError:
        return {"answer": "Không kết nối được tới Groq API. Kiểm tra mạng.", "tools_used": tools_used, "error": "network"}


GROQ_RETRIES = 3
GROQ_MAX_WAIT_S = 60


def _groq_retry_wait(resp: httpx.Response) -> float | None:
    """Số giây cần chờ trước khi gửi lại, hoặc None nếu không nên thử lại.

    - 400 tool_use_failed: mô hình sinh tham số tool không phải JSON hợp lệ (lỗi ngẫu nhiên) → gửi lại ngay.
    - 429 vượt TPM/RPM: chờ theo retry-after của Groq nếu không quá lâu.
    """
    if resp.status_code == 400:
        try:
            err = resp.json().get("error", {})
        except ValueError:
            return None
        return 0 if err.get("code") == "tool_use_failed" else None
    if resp.status_code == 429:
        try:
            wait = float(resp.headers.get("retry-after", ""))
        except ValueError:
            match = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", resp.text)
            wait = (int(match.group(1) or 0) * 60 + float(match.group(2))) if match else None
        return wait + 1 if wait is not None and wait <= GROQ_MAX_WAIT_S else None
    return None


def _groq_error(resp: httpx.Response, tools_used: list[str]) -> dict:
    try:
        message = resp.json().get("error", {}).get("message", resp.text)
    except ValueError:
        message = resp.text
    code = resp.status_code
    if code in (401, 403):
        return {"answer": "Khoá Groq API không hợp lệ.", "tools_used": tools_used, "error": "auth"}
    if code == 413 or (code == 429 and "tokens" in message.lower()):
        return {"answer": "Dữ liệu tra cứu vượt giới hạn token của gói Groq hiện tại. Hãy hỏi hẹp hơn (một phòng ban, "
                          f"một tài liệu) hoặc đổi mô hình bằng AZB_GROQ_MODEL.\n\n_{message}_",
                "tools_used": tools_used, "error": "rate_limit"}
    if code == 429:
        return {"answer": "Đang vượt giới hạn gọi API, thử lại sau ít phút.", "tools_used": tools_used, "error": "rate_limit"}
    if code >= 500:
        return {"answer": f"Groq đang quá tải ({code}).", "tools_used": tools_used, "error": "overload"}
    return {"answer": f"Lỗi từ Groq API ({code}): {message}", "tools_used": tools_used, "error": "api"}
