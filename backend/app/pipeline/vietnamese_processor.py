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
            s = line.strip()
            if not s:
                cleaned_lines.append("")
                continue

            # Remove email watermark (e.g. hoangnc@vnpt.vn)
            if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", s):
                continue

            # Remove timestamp patterns (e.g. 16:37 15/09/2026)
            if re.search(r"\d{2}:\d{2}\s+\d{2}/\d{2}/\d{4}", s):
                continue

            # Remove standalone page indicator (e.g. 1/6, 2/6, 6/6)
            if re.match(r"^\s*\d+/\d+\s*$", s):
                continue

            # Remove isolated single/double digit lines like "2" on signature page
            if re.match(r"^\s*\d{1,2}\s*$", s):
                continue

            # Remove noise strings with non-alphanumeric OCR remnants
            if re.match(r"^[#@&~`^_\-|\/\\\s\d:.,+*%<>=]+$", s) and len(s) < 25:
                continue

            # Remove short random noise tokens (e.g., "c@", "vs\"", "oy", "\O")
            if re.match(r"^[a-zA-Z0-9@_`~^|\\/]{1,3}$", s) and s.lower() not in (
                "bộ", "và", "do", "số", "từ", "của", "về", "nơi", "tm", "iv", "iii", "ii", "i"
            ):
                continue

            cleaned_lines.append(line)

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
