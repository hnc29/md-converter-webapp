import re
from typing import List

VIETNAMESE_ADMIN_REPLACEMENTS = [
    # Document titles and headers
    (r'\bQUYET DINH\b', 'QUYẾT ĐỊNH'),
    (r'\bQUYÉT ĐỊNH\b', 'QUYẾT ĐỊNH'),
    (r'\bHOI DONG THÀNH VIÊN\b', 'HỘI ĐỒNG THÀNH VIÊN'),
    (r'\bHOI ĐONG THÀNH VIÊN\b', 'HỘI ĐỒNG THÀNH VIÊN'),
    (r'\bHỘI DONG THÀNH VIÊN\b', 'HỘI ĐỒNG THÀNH VIÊN'),
    (r'\bHội dong thành viên\b', 'Hội đồng thành viên'),
    (r'\bHội đông thành viên\b', 'Hội đồng thành viên'),
    (r'\bHội đồng Thành viên\b', 'Hội đồng thành viên'),
    (r'\bTAP DOAN\b', 'TẬP ĐOÀN'),
    (r'\bBUU CHINH VIEN THONG\b', 'BƯU CHÍNH VIỄN THÔNG'),
    (r'\bBƯU CHÍNH VIÊN THÔNG\b', 'BƯU CHÍNH VIỄN THÔNG'),
    (r'\bBƯU CHÍNH VIỄN THONG\b', 'BƯU CHÍNH VIỄN THÔNG'),
    (r'\bVIET NAM\b', 'VIỆT NAM'),
    (r'\bCONG HOA XA HOI CHU NGHIA\b', 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA'),
    (r'\bĐộc lập - Tự do - Hanh phúc\b', 'Độc lập - Tự do - Hạnh phúc'),
    
    # Chapters
    (r'\bCHƯƠNG\s+HI\b', 'CHƯƠNG III'),
    (r'\bCHUONG\s+HI\b', 'CHƯƠNG III'),
    (r'\bCHUONG\s+III\b', 'CHƯƠNG III'),
    (r'\bCHƯƠNG\s+L[il1I]+\b', 'CHƯƠNG III'),
    (r'\bCHƯƠNG\s+\]V\b', 'CHƯƠNG IV'),
    (r'\bCHUONG\s+IV\b', 'CHƯƠNG IV'),
    (r'\bCHUONG\s+I\b', 'CHƯƠNG I'),
    (r'\bCHUONG\s+II\b', 'CHƯƠNG II'),
    (r'\bDIEU KHOẢN THI HANE\b', 'ĐIỀU KHOẢN THI HÀNH'),
    (r'\bDIEU KHOẢN THỊ HÀNH\b', 'ĐIỀU KHOẢN THI HÀNH'),
    (r'\bDIEU KHOAN TH1 HANH\b', 'ĐIỀU KHOẢN THI HÀNH'),
    (r'\bQUYÉT ĐỊNH DAU TƯ\b', 'QUYẾT ĐỊNH ĐẦU TƯ'),
    (r'\bQUYET DINH DAU TU\b', 'QUYẾT ĐỊNH ĐẦU TƯ'),
    (r'\bQUY CHE PHAN CAP\b', 'QUY CHẾ PHÂN CẤP'),
    (r'\bUY QUYEN\b', 'ỦY QUYỀN'),
    (r'\bUỶ QUYEN\b', 'UỶ QUYỀN'),
    (r'\bUY QUYỀN\b', 'ỦY QUYỀN'),
    
    # Legal References & Document numbers
    (r'\bCăn cứ Luật quản bp và dau tư\b', 'Căn cứ Luật Quản lý và đầu tư'),
    (r'\bCăn cứ Luật quản lý và dau tư\b', 'Căn cứ Luật Quản lý và đầu tư'),
    (r'\bCăn cứ Luật Đâu tư công\b', 'Căn cứ Luật Đầu tư công'),
    (r'\b9535/QĐ-TTg\b', '955/QĐ-TTg'),
    (r'\b953/QĐ-TTg\b', '955/QĐ-TTg'),
    (r'\b05/OD-VNPT-HDTV-NL\b', '05/QĐ-VNPT-HĐTV-NL'),
    (r'\b1211Qa 9 VNPT-HĐTV-KHĐT\b', '121/QĐ-VNPT-HĐTV-KHĐT'),
    (r'\b151/QD-VNPT-HDTV-KHDT\b', '151/QĐ-VNPT-HĐTV-KHĐT'),
    (r'\b121/QD-VNPT-HDTV-KHDT\b', '121/QĐ-VNPT-HĐTV-KHĐT'),
    (r'\b52/QD-VNPT-KHDT-KSNB\b', '52/QĐ-VNPT-KHĐT-KSNB'),
    (r'\b239\s*/\s*QD-VNPT-HDTV-KHDT\b', '239/QĐ-VNPT-HĐTV-KHĐT'),
    (r'\b239\s*/\s*QĐ-VNPT-HĐTV-KHĐT\b', '239/QĐ-VNPT-HĐTV-KHĐT'),
    
    # Common OCR term corrections
    (r'\bđược phân cap\b', 'được phân cấp'),
    (r'\bngười được ủy quyên\b', 'người được ủy quyền'),
    (r'\bthấm quyên\b', 'thẩm quyền'),
    (r'\bquyét định\b', 'quyết định'),
    (r'\bđâu tư\b', 'đầu tư'),
    (r'\bđau tư\b', 'đầu tư'),
    (r'\bsửa đôi\b', 'sửa đổi'),
    (r'\bbô sung\b', 'bổ sung'),
    (r'\bbé sung\b', 'bổ sung'),
    (r'\bmục treng\b', 'mục trong'),
    (r'\bkhôi nhà\b', 'khối nhà'),
    (r'\bmệt tập hop\b', 'một tập hợp'),
    (r'\bnhiệm vu Øïøo\b', 'nhiệm vụ giao'),
    (r'\bthực biện hậu kiểm\b', 'thực hiện hậu kiểm'),
    (r'\btrược pháo luật\b', 'trước pháp luật'),
    (r'\bvướng mặc can\b', 'vướng mắc cần'),
    (r'\bphát trié đguồ\b', 'phát triển nguồn'),
    (r'\bnhân lực quyét\b', 'nhân lực quyết'),
    (r'\bĐơn vi\b', 'Đơn vị'),
    (r'\bDon vi\b', 'Đơn vị'),
    (r'\bđoa vị\b', 'đơn vị'),
    (r'\bTrường bợp\b', 'Trường hợp'),
    (r'\bcủa dyn vi\b', 'của đơn vị'),
    (r'\btổng mức dau tư\b', 'tổng mức đầu tư'),
    (r'\bchi trương\b', 'chủ trương'),
    
    # Telecom & Technical quality metrics (4G/LTE, OSS, Drive test)
    (r'\bchi tieu quilt ly\b', 'chỉ tiêu quản lý'),
    (r'\bchi tieu quan ly\b', 'chỉ tiêu quản lý'),
    (r'\bch[iI]t luarng\b', 'chất lượng'),
    (r'\bchAt luvng\b', 'chất lượng'),
    (r'\bchat ltryng\b', 'chất lượng'),
    (r'\bchAt hrcyng\b', 'chất lượng'),
    (r'\btam thiri\b', 'tạm thời'),
    (r'\btam thoi\b', 'tạm thời'),
    (r'\bAM THIJI\b', 'TẠM THỜI'),
    (r'\bFTAM THỜI\b', 'TẠM THỜI'),
    (r'\bmang 4G/LTE cua VNPT\b', 'mạng 4G/LTE của VNPT'),
    (r'\bPHTJ LUC\b', 'PHỤ LỤC'),
    (r'\bPH-Cf LUC\b', 'PHỤ LỤC'),
    (r'\bPHU LUC\b', 'PHỤ LỤC'),
    (r'\bDinh nghla\b', 'Định nghĩa'),
    (r'\bDinh ngliia\b', 'Định nghĩa'),
    (r'\bDinh nghTa\b', 'Định nghĩa'),
    (r'\bDinh nghia\b', 'Định nghĩa'),
    (r'\bPhuang phap xac dinh\b', 'Phương pháp xác định'),
    (r'\bPhucmg phap xac dinh\b', 'Phương pháp xác định'),
    (r'\bPhuong phap xac dinh\b', 'Phương pháp xác định'),
    (r'\bCong thirc tinh\b', 'Công thức tính'),
    (r'\bCong -auk tinh\b', 'Công thức tính'),
    (r'\bC6ng tilde tinh\b', 'Công thức tính'),
    (r'\bC8ng thirc tinh\b', 'Công thức tính'),
    (r'\bTan suit va Phuang phap th6ng ke\b', 'Tần suất và phương pháp thống kê'),
    (r'\bTan suit va Phuong phap thOng ke\b', 'Tần suất và phương pháp thống kê'),
    (r'\bTL suAt va phucmg phap thong\b', 'Tần suất và phương pháp thống kê'),
    (r'\bSO luting\b', 'Số lượng'),
    (r'\bSO hro•ng\b', 'Số lượng'),
    (r'\bS6 luting\b', 'Số lượng'),
    (r'\bSo hro•ng\b', 'Số lượng'),
    (r'\bSO Wong\b', 'Số lượng'),
    (r'\bket not\b', 'kết nối'),
    (r'\bk6t not\b', 'kết nối'),
    (r'\b1\(61 not\b', 'kết nối'),
    (r'\bthanh ding\b', 'thành công'),
    (r'\bthanh cong\b', 'thành công'),
    (r'\byeu cau\b', 'yêu cầu'),
    (r'\byeu cAu\b', 'yêu cầu'),
    (r'\byen cau\b', 'yêu cầu'),
    (r'\byeu cL\b', 'yêu cầu'),
    (r'\bchuyen giao\b', 'chuyển giao'),
    (r'\bchuy6n giao\b', 'chuyển giao'),
    (r'\bchuy\'L giao\b', 'chuyển giao'),
    (r'\bchuy8n giao\b', 'chuyển giao'),
    (r'\btan so\b', 'tần số'),
    (r'\btan s6\b', 'tần số'),
    (r'\bcuoc goi\b', 'cuộc gọi'),
    (r'\bcuOc goi\b', 'cuộc gọi'),
    (r'\bcultic goi\b', 'cuộc gọi'),
    (r'\bcue goi\b', 'cuộc gọi'),
    (r'\bkhac tan so\b', 'khác tần số'),
    (r'\bkhac tan s6\b', 'khác tần số'),
    (r'\bding tan so\b', 'cùng tần số'),
    (r'\bcling tan s6\b', 'cùng tần số'),
    (r'\bcimg tan so\b', 'cùng tần số'),
    (r'\btai nguyen RB\b', 'tài nguyên RB'),
    (r'\btai nguyen\b', 'tài nguyên'),
    (r'\bhuong downlink\b', 'hướng downlink'),
    (r'\bhuOng downlink\b', 'hướng downlink'),
    (r'\bhuong Uplink\b', 'hướng Uplink'),
    (r'\bhuang Uplink\b', 'hướng Uplink'),
    (r'\bHieu suit sir dung\b', 'Hiệu suất sử dụng'),
    (r'\bHieu suit\b', 'Hiệu suất'),
    (r'\bvo tuyen\b', 'vô tuyến'),
    (r'\bvo tuy\'L\b', 'vô tuyến'),
    (r'\bvo tuy8n\b', 'vô tuyến'),
    (r'\bvo tuyk\b', 'vô tuyến'),
    (r'\btruy nhap\b', 'truy nhập'),
    (r'\btruy nhfip\b', 'truy nhập'),
    (r'\bphan doan\b', 'phân đoạn'),
    (r'\bphin doan\b', 'phân đoạn'),
    (r'\bhe thong OSS\b', 'hệ thống OSS'),
    (r'\bhe thOng OSS\b', 'hệ thống OSS'),
    (r'\b1116 thOng OSS\b', 'hệ thống OSS'),
    (r'\bDo kiem\b', 'Đo kiểm'),
    (r'\bDo kie\'m\b', 'Đo kiểm'),
    (r'\bmo phOng\b', 'mô phỏng'),
    (r'\bmo ph\'Ong\b', 'mô phỏng'),
    (r'\btoi thieu\b', 'tối thiểu'),
    (r'\bthi thi\'eu\b', 'tối thiểu'),
    (r'\bt6i thi6u\b', 'tối thiểu'),
    (r'\bdieu kien do kiem\b', 'điều kiện đo kiểm'),
    (r'\bngoai troi\b', 'ngoài trời'),
    (r'\bngodi trod\b', 'ngoài trời'),
    (r'\bngoai trgi\b', 'ngoài trời'),
    (r'\btrong nha\b', 'trong nhà'),
    (r'\bco dinh\b', 'cố định'),
    (r'\bc6 dinh\b', 'cố định'),
    (r'\bdi dong\b', 'di động'),
    (r'\bdi dOng\b', 'di động'),
    (r'\bdi Ong\b', 'di động'),
    (r'\bthue bao\b', 'thuê bao'),
    (r'\bkhoang cach\b', 'khoảng cách'),
    (r'\bkhoang each\b', 'khoảng cách'),
    (r'\bben xe o to\b', 'bến xe ô tô'),
    (r'\bben xe 6 to\b', 'bến xe ô tô'),
    (r'\bblenh vien\b', 'bệnh viện'),
    (r'\bhao tang\b', 'bảo tàng'),
    (r'\bdog trinh cong Ong\b', 'công trình công cộng'),
    (r'\bcong trinh cong cong\b', 'công trình công cộng'),
    (r'\bcling hang khong\b', 'cảng hàng không'),
    (r'\bcang hang khong\b', 'cảng hàng không'),
    (r'\bnha ga tau hoa\b', 'nhà ga tàu hỏa'),
    (r'\bnha ga tau hem\b', 'nhà ga tàu hỏa'),
    (r'\bbOn tau h6a\b', 'bến tàu hỏa'),
    (r'\bDo kha dung\b', 'Độ khả dụng'),
    (r'\bD6 kha dung\b', 'Độ khả dụng'),
    (r'\bDO kha dung\b', 'Độ khả dụng'),
    (r'\b613 kha dung\b', 'độ khả dụng'),
    (r'\bguy dinh tai QuOt clinh so\b', 'quy định tại Quyết định số'),
    (r'\bquy dinh tai Quyet dinh so\b', 'quy định tại Quyết định số'),
    (r'\bTong cong ty\b', 'Tổng công ty'),
    (r'\bTOng cong ty\b', 'Tổng công ty'),
    (r'\bPho Tong giam doc\b', 'Phó Tổng Giám đốc'),
    (r'\bPHO TONG GIAI4 DOC\b', 'PHÓ TỔNG GIÁM ĐỐC'),
    (r'\bTong giam doc\b', 'Tổng Giám đốc'),
    (r'\bTONG GIAM DOC\b', 'TỔNG GIÁM ĐỐC'),
    (r'\bChanh Van phong\b', 'Chánh Văn phòng'),
    (r'\bTrtrOng cac Ban\b', 'Trưởng các Ban'),
    (r'\bTruong cac Ban\b', 'Trưởng các Ban'),
    (r'\bBan Cong nghe - Mang\b', 'Ban Công nghệ - Mạng'),
    (r'\bBan Chat luting\b', 'Ban Chất lượng'),
    (r'\bBan Chat luong\b', 'Ban Chất lượng'),
    (r'\bTo Manh Cuong\b', 'Tô Mạnh Cường'),
    (r'\bTO Manh Cuong\b', 'Tô Mạnh Cường'),
    (r'\b(?:TS\/|Ty|TS,|TiS)\s+1e\b', 'Tỷ lệ'),
    (r'\b1\)?7\s+lO\b', 'Tỷ lệ'),
]

class VietnameseProcessor:
    """
    Sanitizes noise, watermark artifacts, stamps, and standardizes Vietnamese
    administrative/legal documents.
    """

    @staticmethod
    def clean_watermark_and_stray_artifacts(text: str) -> str:
        """Removes email watermarks, timestamp stamps, page markers, and OCR noise lines."""
        if not text:
            return ""

        lines = text.split("\n")
        cleaned_lines: List[str] = []

        for line in lines:
            # Inline strip email watermark and timestamp patterns without dropping whole line
            cleaned = re.sub(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:[_\s]*\d{1,2}:\d{2}(?:\s+\d{1,2}/\d{1,2}/\d{2,4})?)?",
                "",
                line,
                flags=re.IGNORECASE
            )
            cleaned = re.sub(r"\b\d{1,2}:\d{2}\s+\d{1,2}/\d{1,2}/\d{2,4}\b", "", cleaned)
            s = cleaned.strip()
            if not s:
                continue

            # Remove standalone page indicator (e.g. 1/6, 2/6, 6/6)
            if re.match(r"^\d+/\d+$", s):
                continue

            # Remove noise strings with non-alphanumeric OCR remnants (e.g. "—", "---", "|", "~")
            if re.match(r"^[#@&~`^_\-|\/\\\s:.,+*%<>=]+$", s) and len(s) < 25:
                continue

            # Remove short random noise tokens (e.g., "c@", "vs\"", "oy", "\O")
            if re.match(r"^[a-zA-Z0-9@_`~^|\\/]{1,3}$", s) and s.lower() not in (
                "bộ", "và", "do", "số", "từ", "của", "về", "nơi", "tm", "iv", "iii", "ii", "i", "dl", "ul"
            ):
                continue

            cleaned_lines.append(cleaned)

        return "\n".join(cleaned_lines)

    @staticmethod
    def correct_administrative_terms(text: str) -> str:
        """Applies high-precision corrections to Vietnamese administrative legal text."""
        if not text:
            return ""

        for pattern, replacement in VIETNAMESE_ADMIN_REPLACEMENTS:
            text = re.sub(pattern, replacement, text)

        # Standardize signature ending
        text = re.sub(r"\./[^\s\n]*", "./.", text)
        return text

    @classmethod
    def process_text(cls, text: str) -> str:
        """Full sanitization and correction pipeline for OCR output."""
        cleaned = cls.clean_watermark_and_stray_artifacts(text)
        corrected = cls.correct_administrative_terms(cleaned)
        return corrected

vietnamese_processor = VietnameseProcessor()
