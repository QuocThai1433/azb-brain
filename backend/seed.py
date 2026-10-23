"""Nạp dữ liệu sơ đồ điều hành AZB REV02 (01/08/2026).

Chạy: python -m backend.seed  (xoá và nạp lại toàn bộ dữ liệu tổ chức)

Ghi chú:
- Tên trên sơ đồ có chỗ viết tắt (VD "Ng. V. Trung") -> lưu nguyên văn, đánh dấu verified=0 để bổ sung sau.
- Giải nghĩa viết tắt phòng ban nào chưa chắc chắn cũng đánh dấu verified=0.
- "TBA" trên sơ đồ = chức danh đang trống (employee_id NULL).
"""
from .db import connect, init_db

# (code, name, full_name, unit_type, parent_code, color_group, verified, notes)
UNITS = [
    ("HDQT", "Hội đồng Quản trị", None, "board", None, "exec", 1, None),
    ("KSNB", "Ban KSNB / Ban Audit", "Ban Kiểm soát nội bộ / Kiểm toán nội bộ", "committee", "HDQT", "exec", 1,
     "Báo cáo trực tiếp Chủ tịch HĐQT."),
    ("TGD", "Ban Tổng Giám đốc", None, "executive", "HDQT", "exec", 1, None),
    ("TROLY", "Ban Trợ lý", "Ban Trợ lý Tổng Giám đốc", "committee", "TGD", "exec", 1, None),
    ("PTGD-TC", "PTGĐ Tài chính", "Phó Tổng Giám đốc Tài chính", "executive", "TGD", "finance", 1, None),
    ("PTGD-TT", "PTGĐ Thường trực", "Phó Tổng Giám đốc Thường trực", "executive", "TGD", "construction", 1,
     "Chịu trách nhiệm điều hành mảng xây lắp và các nhiệm vụ được TGĐ ủy quyền theo từng thời điểm."),
    ("PTGD-TM", "PTGĐ Thương mại", "Phó Tổng Giám đốc Thương mại", "executive", "TGD", "commercial", 1, None),

    # Khối Nhân sự Hành chính – trực thuộc TGĐ
    ("K-NSHC", "Khối Nhân sự Hành chính", None, "division", "TGD", "hr", 1, None),
    ("P-HCNS", "P. Hành chính Nhân sự", None, "department", "K-NSHC", "hr", 1, None),

    # Khối Vận hành – trực thuộc TGĐ
    ("K-VH", "Khối Vận hành", None, "division", "TGD", "ops", 1, None),
    ("B-HT", "Ban Hệ thống", "Ban Hệ thống (quản lý hệ thống / ISO)", "department", "K-VH", "ops", 0,
     "Giải nghĩa phạm vi 'Hệ thống' cần xác nhận."),
    ("P-MKT", "P. MKT", "Phòng Marketing", "department", "K-VH", "ops", 1, None),
    ("P-PL", "P. Pháp lý", "Phòng Pháp lý", "department", "K-VH", "ops", 1, None),
    ("B-TD", "Ban T&D", "Ban Đào tạo & Phát triển (Training & Development)", "department", "K-VH", "ops", 0, None),
    ("P-IT", "P. IT", "Phòng Công nghệ thông tin", "department", "K-VH", "ops", 1, None),

    # Khối Tài chính Kế toán – dưới PTGĐ Tài chính
    ("K-TCKT", "Khối Tài chính Kế toán", None, "division", "PTGD-TC", "finance", 1, None),
    ("P-KT", "P. Kế toán", "Phòng Kế toán", "department", "K-TCKT", "finance", 1, None),
    ("B-TC", "Ban Tài chính", None, "department", "K-TCKT", "finance", 1, None),
    ("B-QLCN", "Ban QLCN", "Ban Quản lý công nợ", "department", "K-TCKT", "finance", 0,
     "Giải nghĩa QLCN cần xác nhận."),

    # Khối Kinh tế Kỹ thuật – dưới PTGĐ Thường trực
    ("K-KTKT", "Khối Kinh tế Kỹ thuật", None, "division", "PTGD-TT", "technical", 1, None),
    ("P-TKKT", "P. Thiết kế - Kỹ thuật", "Phòng Thiết kế - Kỹ thuật", "department", "K-KTKT", "technical", 1, None),
    ("P-DT", "P. Đấu thầu", "Phòng Đấu thầu", "department", "K-KTKT", "technical", 1, None),
    ("P-PTDA", "P. PT Dự án", "Phòng Phát triển Dự án", "department", "K-KTKT", "technical", 0, None),
    ("P-CCM", "P. CCM", "Phòng Quản lý Chi phí & Hợp đồng (Cost & Contract Management)", "department", "K-KTKT",
     "technical", 0, "Giải nghĩa CCM cần xác nhận."),

    # Khối Thi công – dưới PTGĐ Thường trực
    ("K-TC", "Khối Thi công", None, "division", "PTGD-TT", "construction", 1, None),
    ("PMSM", "PM/SM", "Quản lý dự án / Chỉ huy trưởng công trường (Project Manager / Site Manager)", "department",
     "K-TC", "construction", 0, None),
    ("P-MEPF", "P. MEPF", "Phòng Cơ điện (Mechanical, Electrical, Plumbing, Fire)", "department", "K-TC",
     "construction", 1, None),
    ("P-BH", "P. Bảo hành", "Phòng Bảo hành", "department", "K-TC", "construction", 1, None),
    ("P-MMTB", "P. MMTB", "Phòng Máy móc Thiết bị", "department", "K-TC", "construction", 0, None),
    ("P-KTTC", "P. KTTC", "Phòng Kỹ thuật Thi công", "department", "K-TC", "construction", 0, None),
    ("P-LLTC", "P. LLTC", "Phòng Lực lượng Thi công", "department", "K-TC", "construction", 0,
     "Giải nghĩa LLTC cần xác nhận."),

    # Trực thuộc PTGĐ Thường trực (không qua khối)
    ("P-QAQC", "P. QA/QC", "Phòng Đảm bảo & Kiểm soát chất lượng", "department", "PTGD-TT", "construction", 1, None),
    ("P-HSSE", "P. HSSE", "Phòng An toàn, Sức khỏe, An ninh & Môi trường", "department", "PTGD-TT", "construction",
     1, None),

    # Khối Thương mại – dưới PTGĐ Thương mại
    ("K-TM", "Khối Thương mại", None, "division", "PTGD-TM", "commercial", 1, None),
    ("P-VT", "P. Vật tư", "Phòng Vật tư", "department", "K-TM", "commercial", 1, None),
    ("P-TP", "P. Thầu phụ", "Phòng Thầu phụ", "department", "K-TM", "commercial", 1, None),

    # Các Ban Quản lý Dự án – nhận hỗ trợ từ tất cả phòng ban
    ("BQLDA", "Các Ban Quản lý Dự án", None, "project", "TGD", "exec", 1,
     "Tất cả phòng ban trên sơ đồ đều hỗ trợ các Ban QLDA (mũi tên xuống thanh 'Các Ban quản lý dự án')."),
]

# (key, full_name, display_name_on_chart, verified)
EMPLOYEES = [
    ("tuan", "Nguyễn Lê Anh Tuấn", "Mr. Nguyễn Lê Anh Tuấn", 1),
    ("nhon", "Trần Minh Nhơn", "Mr. Trần Minh Nhơn", 1),
    ("nam", "Võ Thành Nam", "Võ Thành Nam", 1),
    ("duy", "Trần Thị Thùy Duy", "Trần Thị Thùy Duy", 1),
    ("tinh", "Nguyễn Đức Tịnh", "Mr. Nguyễn Đức Tịnh", 1),
    ("hoang", "Trần Quốc Hoàng", "Mr. Trần Quốc Hoàng", 1),
    ("maihan", "Nguyễn Ngọc Mai Hân", "N. N. Mai Hân", 1),
    ("cuongvv", "Võ Văn Cường", "Võ Văn Cường", 1),
    ("uyen", "Phan H. P. Uyên", "Phan H. P. Uyên", 0),
    ("thao", "Ng. Lê Thanh Thảo", "Ng. Lê Thanh Thảo", 0),
    ("thuy", "Ng. P. Kim Thúy", "Ng. P. Kim Thúy", 0),
    ("phucnv", "Nguyễn Văn Phúc", "Nguyễn Văn Phúc", 1),
    ("nga", "Huỳnh T. Ngọc Nga", "Huỳnh T. Ngọc Nga", 0),
    ("viet", "Vương Xuân Việt", "Vương Xuân Việt", 1),
    ("trung", "Ng. V. Trung", "Ng. V. Trung", 0),
    ("thuc", "Phí T. Thực", "Phí T. Thực", 0),
    ("minhphuc", "Ng. H. Minh Phúc", "Ng. H. Minh Phúc", 0),
    ("triet", "Trần M. Triết", "Trần M. Triết", 0),
    ("haiq", "Ng. Q. Hải", "Ng Q. Hải", 0),
    ("haibv", "Bùi Văn Hải", "Bùi Văn Hải", 1),
    ("hien", "Nguyễn Đức Hiền", "Nguyễn Đức Hiền", 1),
    ("cong", "Nguyễn Thái Công", "Nguyễn Thái Công", 1),
    ("phucth", "Trương Hữu Phúc", "Trương Hữu Phúc", 1),
    ("quang", "Đinh Duy Quang", "Đinh Duy Quang", 1),
    ("luan", "Trần Kinh Luân", "Trần Kinh Luân", 1),
    ("le", "Nguyễn Công Lê", "Nguyễn Công Lê", 1),
    ("nguyen", "Phạm Thượng Nguyên", "Phạm Thượng Nguyên", 1),
    ("thien", "Đinh Quang Thiện", "Đinh Quang Thiện", 1),
    ("cuongt", "Triệu Cường", "Triệu Cường", 1),
]

# (unit_code, title, title_code, employee_key | None, is_head)
POSITIONS = [
    ("HDQT", "Chủ tịch Hội đồng Quản trị", "CT", "tuan", 1),
    ("KSNB", "Trưởng ban", "TB", "nam", 1),
    ("TGD", "Tổng Giám đốc", "TGĐ", "nhon", 1),
    ("TROLY", "Trưởng ban", "TB", "duy", 1),
    ("PTGD-TC", "Phó Tổng Giám đốc Tài chính", "PTGĐ", "nam", 1),
    ("PTGD-TT", "Phó Tổng Giám đốc Thường trực", "PTGĐ", "tinh", 1),
    ("PTGD-TM", "Phó Tổng Giám đốc Thương mại", "PTGĐ", "hoang", 1),

    ("K-NSHC", "Giám đốc Khối", "GĐ", "maihan", 1),
    ("P-HCNS", "Giám đốc", "GĐ", "maihan", 1),
    ("P-HCNS", "Phó phòng", "PP", "cuongvv", 0),

    ("K-VH", "Giám đốc Khối", "GĐ", None, 1),
    ("B-HT", "Trưởng ban", "TB", "duy", 1),
    ("P-MKT", "Phó phòng", "PP", "uyen", 1),
    ("P-PL", "Phó phòng", "PP", "thao", 1),
    ("B-TD", "Phó ban", "PB", "thuy", 1),
    ("P-IT", "Phó phòng", "PP", "phucnv", 1),

    ("K-TCKT", "Giám đốc Khối", "GĐ", None, 1),
    ("P-KT", "Phó phòng", "PP", "nga", 1),
    ("B-TC", "Trưởng ban", "TB", "nam", 1),
    ("B-QLCN", "Trưởng ban", "TB", None, 1),

    ("K-KTKT", "Giám đốc Khối", "GĐ", None, 1),
    ("P-TKKT", "Trưởng phòng", "TP", "viet", 1),
    ("P-DT", "Trưởng phòng", "TP", "trung", 1),
    ("P-DT", "Phó phòng", "PP", "thuc", 0),
    ("P-PTDA", "Phó phòng", "PP", "minhphuc", 1),
    ("P-CCM", "Phó phòng", "PP", "triet", 1),
    ("P-CCM", "Phó phòng", "PP", "haiq", 0),

    ("K-TC", "Giám đốc Khối", "GĐ", "haibv", 1),
    ("PMSM", "Giám đốc Khối (GĐK)", "GĐK", "haibv", 1),
    ("P-MEPF", "Trưởng phòng", "TP", "hien", 1),
    ("P-BH", "Trưởng bộ phận", "TBP", "cong", 1),
    ("P-MMTB", "Phó phòng", "PP", "phucth", 1),
    ("P-KTTC", "Phó phòng", "PP", "quang", 1),
    ("P-LLTC", "Phó phòng", "PP", "luan", 1),

    ("P-QAQC", "Phó phòng", "PP", "le", 1),
    ("P-HSSE", "Trưởng phòng", "TP", "nguyen", 1),

    ("K-TM", "Giám đốc Khối", "GĐ", "thien", 1),
    ("P-VT", "Trưởng phòng", "TP", "cuongt", 1),
    ("P-TP", "Giám đốc", "GĐ", "thien", 1),
]


def seed() -> None:
    init_db()
    with connect() as conn:
        for t in ("positions", "processes", "targets", "employees", "units"):
            conn.execute(f"DELETE FROM {t}")

        unit_ids: dict[str, int] = {}
        for i, (code, name, full, utype, parent, color, verified, notes) in enumerate(UNITS):
            cur = conn.execute(
                "INSERT INTO units (code, name, full_name, unit_type, parent_id, color_group, verified, notes, sort_order)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (code, name, full, utype, unit_ids.get(parent), color, verified, notes, i),
            )
            unit_ids[code] = cur.lastrowid

        emp_ids: dict[str, int] = {}
        for key, full, display, verified in EMPLOYEES:
            cur = conn.execute(
                "INSERT INTO employees (full_name, display_name, verified, notes) VALUES (?,?,?,?)",
                (full, display, verified, None if verified else "Tên đang viết tắt theo sơ đồ – cần bổ sung họ tên đầy đủ."),
            )
            emp_ids[key] = cur.lastrowid

        for i, (ucode, title, tcode, ekey, is_head) in enumerate(POSITIONS):
            conn.execute(
                "INSERT INTO positions (unit_id, title, title_code, employee_id, is_head, sort_order) VALUES (?,?,?,?,?,?)",
                (unit_ids[ucode], title, tcode, emp_ids.get(ekey) if ekey else None, is_head, i),
            )

        conn.execute(
            "INSERT INTO audit_log (action, entity, detail) VALUES ('seed','all','Nạp sơ đồ điều hành AZB-SDTC-REV02 (01/08/2026)')"
        )
    print(f"Đã nạp {len(UNITS)} đơn vị, {len(EMPLOYEES)} nhân sự, {len(POSITIONS)} chức danh.")


if __name__ == "__main__":
    seed()
