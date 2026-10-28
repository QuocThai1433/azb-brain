"""Nạp "Mục tiêu và chương trình hành động Công ty năm 2026" (02/01/2026 - 31/12/2026).

Chạy: python -m backend.okr2026  (thêm WIG/KRI vào bảng targets và POA vào action_programs)

- Chạy lại nhiều lần vẫn an toàn: dòng đã có (cùng kỳ + chỉ tiêu, hoặc cùng năm + mã POA) thì giữ nguyên, không ghi đè số thực hiện.
- Số thực hiện (actual_value) để trống: file mẫu chỉ có chỉ tiêu, số thực tế nhập sau trên trang Mục tiêu.
- Dòng toàn công ty (unit_id NULL). Tiền lưu theo VNĐ như dữ liệu cũ (3,168 tỷ đồng = 3.168.000.000.000).
"""
from .db import connect, init_db

PERIOD = "2026"
TY = 1_000_000_000

# (mã WIG, nội dung WIG)
WIGS = {
    "WIG 01.26": "Giữ vững thị trường thế mạnh phân khúc xây dựng công nghiệp và mở rộng phân khúc dân dụng.",
    "WIG 02.26": "Doanh thu tập trung mục tiêu hiệu quả.",
    "WIG 03.26": "Tối ưu chi phí, thực hiện dự án đạt hiệu quả tài chính cao.",
    "WIG 04.26": "Tăng thanh khoản dòng tiền, hiệu quả thu hồi công nợ cao.",
    "WIG 05.26": "Nâng cao chất lượng, đảm bảo tiến độ, an toàn, thực hiện triển khai Dự án chuyên nghiệp.",
}

# (mã WIG, metric, tên chỉ tiêu (chỉ dùng khi metric = khac), giá trị mục tiêu, đơn vị tính, ghi chú thêm)
KRIS = [
    ("WIG 01.26", "doanh_so", "", 3168 * TY, "VNĐ", "KRI 01: Doanh số bán hàng đạt 3,168 tỷ đồng."),
    ("WIG 02.26", "doanh_thu", "", 2568 * TY, "VNĐ", "KRI 02: Doanh thu thực hiện đạt 2,568 tỷ đồng."),
    ("WIG 03.26", "khac", "KRI 03: Ngân sách chung công ty tối ưu thêm so với năm 2025", 1, "%",
     "Ngân sách chung công ty tối ưu thêm 1% so với năm 2025."),
    ("WIG 03.26", "khac", "KRI 03: Tổng ngân sách thi công thực hiện thấp hơn ngân sách ban hành", 2, "%",
     "Tổng ngân sách thi công thực hiện đạt thấp hơn tối thiểu 2% so với ngân sách ban hành."),
    ("WIG 04.26", "khac", "KRI 04: Thu hồi công nợ từ các dự án cũ", 100, "%", "Chỉ tiêu thu hồi công nợ từ các dự án cũ 100%."),
    ("WIG 04.26", "khac", "KRI 04: Thu hồi công nợ thực hiện mới", 90, "%", "Chỉ tiêu thu hồi công nợ thực hiện mới đạt 90%."),
    ("WIG 04.26", "khac", "KRI 04: Thu tạm ứng từ dự án mới", 100, "%", "Chỉ tiêu thu tạm ứng từ dự án mới: 100%."),
    ("WIG 04.26", "khac", "KRI 04: Tiến độ thu tiền", 90, "%", "Chỉ tiêu tiến độ thu tiền đạt từ 90%."),
    ("WIG 05.26", "okr_du_an", "", 90, "%",
     "KRI 05: 90% dự án đạt yêu cầu trên 85% theo Bộ chỉ tiêu Dự án OKRs Kỹ thuật được ban hành."),
]

# (mã, tên chương trình, phụ trách)
POAS = [
    ("POA 01", "Chương trình xây dựng Lực lượng Thầu phụ, Tổ đội chiến lược.", "Ban Dự án"),
    ("POA 02", "Chương trình triển khai các bộ tiêu chuẩn AZB: Thi công và Đấu thầu.", "Ban Dự án"),
    ("POA 03", "Triển khai công tác 3s đồng nhất tại các Dự án.", "Ban Dự án"),
    ("POA 04", "Chương trình quy hoạch và đào tạo đội ngũ kế thừa cấp trung.", "Ban T&D"),
    ("POA 05", "Đẩy mạnh công tác số hóa và AI trong công tác vận hành quản lý, nhằm tối ưu hiệu suất làm việc "
               "và nâng cao chất lượng dịch vụ.", "Toàn công ty"),
]
START, END = "2026-01-02", "2026-12-31"


def import_okr_2026(conn) -> dict:
    added = {"targets": 0, "action_programs": 0}
    for wig, metric, name, value, label, note in KRIS:
        exists = conn.execute(
            "SELECT 1 FROM targets WHERE unit_id IS NULL AND period = ? AND metric = ? AND COALESCE(metric_name, '') = ?",
            (PERIOD, metric, name)).fetchone()
        if exists:
            continue
        conn.execute("INSERT INTO targets (unit_id, period, metric, metric_name, target_value, unit_label, notes)"
                     " VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                     (PERIOD, metric, name, value, label, f"{wig}: {WIGS[wig]} {note}"))
        added["targets"] += 1
    for i, (code, name, owner) in enumerate(POAS, 1):
        if conn.execute("SELECT 1 FROM action_programs WHERE year = ? AND code = ?", (PERIOD, code)).fetchone():
            continue
        conn.execute("INSERT INTO action_programs (year, code, name, owner, start_date, end_date, sort_order)"
                     " VALUES (?, ?, ?, ?, ?, ?, ?)", (PERIOD, code, name, owner, START, END, i))
        added["action_programs"] += 1
    return added


if __name__ == "__main__":
    init_db()
    with connect() as conn:
        print("Đã thêm:", import_okr_2026(conn))
        print("Hiện có:", conn.execute("SELECT COUNT(*) FROM targets WHERE unit_id IS NULL AND period = ?", (PERIOD,)).fetchone()[0],
              "mục tiêu,", conn.execute("SELECT COUNT(*) FROM action_programs WHERE year = ?", (PERIOD,)).fetchone()[0], "POA năm", PERIOD)
