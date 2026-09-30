import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from docx import Document
import pymupdf
from ..models import DocumentMetadata
from ..config import settings

class MetadataExtractor:
    """
    Extracts and standardizes metadata for AI Knowledge Bases.
    Strictly adheres to the rule: Only extract factual, explicit metadata;
    never hallucinate or invent attributes.
    """

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calculates deterministic SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def generate_document_id(filename: str) -> str:
        """Generates a clean, deterministic document ID from filename."""
        stem = Path(filename).stem
        # Remove leading numbering like 01., 02_, 1-
        cleaned = re.sub(r"^\d+[\.\-_]", "", stem)
        # Replace non-alphanumeric with hyphens
        cleaned = re.sub(r"[^\w\-_]+", "-", cleaned)
        cleaned = re.sub(r"[-_]+", "-", cleaned).strip("-")
        return cleaned.upper() or "DOC"

    @staticmethod
    def detect_document_type(filename: str, text_sample: str) -> str:
        """Detects document type token (HLD, LLD, PRO, UM, QĐ, QC, TT, BC, CV, etc.) using strict word boundaries."""
        upper_name = filename.upper()
        upper_text = text_sample[:3000].upper()

        type_map = [
            ("HLD", [r"\bHLD\b", r"\bHIGH-LEVEL DESIGN\b", r"\bTHIẾT KẾ TỔNG THỂ\b"]),
            ("LLD", [r"\bLLD\b", r"\bLOW-LEVEL DESIGN\b", r"\bTHIẾT KẾ CHI TIẾT\b"]),
            ("PRO", [r"\bPRO\b", r"\bPROCEDURE\b", r"\bQUY TRÌNH\b", r"\bQUY TRINH\b"]),
            ("QĐ", [r"\bQĐ\b", r"\bQUYẾT ĐỊNH\b", r"\bQUYET DINH\b", r"\bQD\b"]),
            ("QC", [r"\bQUY CHẾ\b", r"\bQUY CHE\b", r"\bQUY CHUẨN\b", r"\bQUY CHUAN\b"]),
            ("TT", [r"\bTHÔNG TƯ\b", r"\bTHONG TU\b", r"\bTT\b"]),
            ("BC", [r"\bBÁO CÁO\b", r"\bBAO CAO\b", r"\bREPORT\b"]),
            ("PL", [r"\bPHỤ LỤC\b", r"\bPHU LUC\b", r"\bAPPENDIX\b"]),
            ("HD", [r"\bHƯỚNG DẪN\b", r"\bHUONG DAN\b"]),
            ("TB", [r"\bTHÔNG BÁO\b", r"\bTHONG BAO\b"]),
            ("CV", [r"\bCV\b", r"\bCÔNG VĂN\b", r"\bCONG VAN\b"]),
            ("QD", [r"\bQUY ĐỊNH VỀ\b", r"\bQUY DINH VE\b", r"^\s*QUY ĐỊNH\b", r"^\s*QUY DINH\b"]),
            ("UM", [r"\bUM\b", r"\bUSER MANUAL\b", r"\bHƯỚNG DẪN SỬ DỤNG\b", r"\bHUONG DAN SU DUNG\b"]),
        ]

        # 1. Check filename first
        for doc_type, patterns in type_map:
            for pat in patterns:
                if re.search(pat, upper_name):
                    return doc_type

        # 2. Check text sample
        for doc_type, patterns in type_map:
            for pat in patterns:
                if re.search(pat, upper_text):
                    return doc_type

        # 3. Detect official dispatch (Công văn) if has 'Kính gửi' / 'V/v' without 'Quyết định'
        if re.search(r"\b(?:Kính gửi|Kinh gui|V/v|Về việc|Ve viec)\b", upper_text, re.IGNORECASE):
            return "CV"

        return ""

    @staticmethod
    def extract_document_number(text_sample: str, filename: str = "") -> str:
        """Extracts official document number like '2123/QĐ-VNPT-CNM', '723/VNPT-CN' or '239/QĐ-VNPT-HĐTV-KHĐT'."""
        # 1. Check filename first (authoritative, verified during file saving/naming)
        if filename:
            fn_match = re.search(
                r"\b(\d+[\-_/](?:VNPT|QĐ|QD|TT|TB|BC|HD|NQ|CT|KH|BB|VB|CV)[\-_/][A-Za-z0-9\-_/Đđ]+)\b",
                filename,
                re.IGNORECASE
            )
            if fn_match:
                raw_num = fn_match.group(1)
                standardized = re.sub(r"^(\d+)[-_]([A-Za-zĐđ]+)", r"\1/\2", raw_num)
                standardized = standardized.replace("QD", "QĐ")
                return standardized

        # 2. Check header area (first 1500 chars or text before 'Căn cứ' / 'QUYẾT ĐỊNH' / 'Kính gửi')
        header_text = text_sample[:1500]
        canci_split = re.split(r"\b(?:Căn cứ|Can cir|Can dr|Kính gửi|Kinh gui)\b", header_text, flags=re.IGNORECASE)
        if len(canci_split) > 1:
            header_text = canci_split[0]

        # Look for "Số: 723/VNPT-CN", "Số : 2123 / QĐ-..." or ": 2123 /QD-..."
        header_match = re.search(
            r"(?:Số|Số hiệu|No\.?|:)\s*([0-9]+\s*[\/-]\s*[A-Za-z0-9\-_/Đđ]+)",
            header_text,
            re.IGNORECASE
        )
        if header_match:
            candidate = re.sub(r"\s+", "", header_match.group(1).strip())
            candidate = re.sub(r"^(\d+)[-_](VNPT|QĐ|QD|TT|TB|BC|HD|NQ|CT|KH|BB|VB|CV)", r"\1/\2", candidate, flags=re.IGNORECASE)
            if len(candidate) >= 4 and not candidate.startswith("/"):
                return candidate.replace("QD", "QĐ")

        # 3. Direct pattern match for VN standard doc numbers in full text, avoiding 'Căn cứ'
        lines = [l for l in text_sample.splitlines() if not re.match(r"^\s*(?:Căn cứ|Can cir|Can dr)\b", l, re.IGNORECASE)]
        filtered_text = "\n".join(lines[:60])
        direct_match = re.search(r"(\d+/(?:VNPT|QĐ|TT|TB|BC|HD|NQ|QD|CV)-[A-Za-z0-9\-_\/Đđ]+)", filtered_text)
        if direct_match:
            return direct_match.group(1).strip().replace("QD", "QĐ")

        return ""

    @staticmethod
    def extract_version(filename: str, text_sample: str) -> str:
        """Extracts document version if explicitly specified."""
        # 1. From filename (e.g. IMS_HLD_v1.2.docx, IMS_HLD_v1_0.docx)
        fn_match = re.search(r"[_\-vV](\d+[\.\_]\d+(?:[\.\_]\d+)?)", filename)
        if fn_match:
            return fn_match.group(1).replace("_", ".")
        
        # 2. From text sample
        text_match = re.search(r"(?:Phiên bản|Version|Ver\.?)\s*[:\-]?\s*(\d+(?:\.\d+)+)", text_sample, re.IGNORECASE)
        if text_match:
            return text_match.group(1).strip()
        return ""

    @staticmethod
    def extract_dates(text_sample: str, filename: str = "") -> Tuple[str, str]:
        """Extracts (issued_date, effective_date) in ISO format (YYYY-MM-DD) or DD/MM/YYYY."""
        issued_date = ""
        effective_date = ""

        # 1. Check header area (before 'Căn cứ' / 'Kính gửi') for "Hà Nội, ngày ... tháng ... năm ..."
        header_text = text_sample[:1500]
        canci_split = re.split(r"\b(?:Căn cứ|Can cir|Can dr|Kính gửi|Kinh gui)\b", header_text, flags=re.IGNORECASE)
        if len(canci_split) > 1:
            header_text = canci_split[0]

        vn_header_match = re.search(
            r"(?:ngày|ngay[\.\s]*)\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})",
            header_text,
            re.IGNORECASE
        )
        if vn_header_match:
            d, m, y = vn_header_match.groups()
            issued_date = f"{y}-{int(m):02d}-{int(d):02d}"

        # 2. Check filename date (authoritative check)
        fn_date = ""
        if filename:
            # Pattern: YYYY-MM-DD or YYYY_MM_DD
            fn_iso_match = re.search(r"\b(20\d{2})[-_.](\d{1,2})[-_.](\d{1,2})\b", filename)
            if fn_iso_match:
                y, m, d = fn_iso_match.groups()
                fn_date = f"{y}-{int(m):02d}-{int(d):02d}"
            else:
                # Pattern: DD-MM-YYYY
                fn_dmy_match = re.search(r"\b(\d{1,2})[-_.](\d{1,2})[-_.](20\d{2})\b", filename)
                if fn_dmy_match:
                    d, m, y = fn_dmy_match.groups()
                    fn_date = f"{y}-{int(m):02d}-{int(d):02d}"

        # If OCR text extracted a date that has same year & month but slightly different day due to OCR handwriting confusion (e.g. 01 vs 04)
        if fn_date:
            if not issued_date:
                issued_date = fn_date
            elif issued_date[:7] == fn_date[:7]:
                # Year and month match, prefer filename date
                issued_date = fn_date

        # 3. Fallback to general text patterns
        if not issued_date:
            vn_date_match = re.search(
                r"(?:ngày|Hà Nội, ngày)\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})",
                text_sample,
                re.IGNORECASE
            )
            if vn_date_match:
                d, m, y = vn_date_match.groups()
                issued_date = f"{y}-{int(m):02d}-{int(d):02d}"
            else:
                std_date_match = re.search(
                    r"(?:Ngày ban hành|Ban hành ngày|Ngày|Date|Issued Date)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
                    text_sample,
                    re.IGNORECASE
                )
                if std_date_match:
                    issued_date = std_date_match.group(1).replace("-", "/").replace(".", "/")

        # Effective date extraction
        # Check if effective from signing date: "kể từ ngày ký" / "ke tu ngay ky"
        if re.search(r"(?:hiệu lực|hieu luc)\s+(?:thi hành\s+|thi hanh\s+)?(?:kể từ|ke tu)\s+(?:ngày ký|ngay ky)", text_sample, re.IGNORECASE):
            effective_date = issued_date
        else:
            eff_match = re.search(
                r"(?:Hiệu lực từ ngày|Có hiệu lực từ ngày|Ngày hiệu lực|Effective Date)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
                text_sample,
                re.IGNORECASE
            )
            if eff_match:
                effective_date = eff_match.group(1).replace("-", "/").replace(".", "/")

        return issued_date, effective_date

    @staticmethod
    def extract_status(text_sample: str) -> str:
        """Extracts status only if explicit (Dự thảo, Đã ban hành, Phê duyệt, etc.)."""
        sample_upper = text_sample[:3000].upper()
        if "DỰ THẢO" in sample_upper or "DRAFT" in sample_upper:
            return "Dự thảo"
        if "ĐÃ BAN HÀNH" in sample_upper or "BAN HÀNH" in sample_upper:
            return "Đã ban hành"
        if "ĐÃ PHÊ DUYỆT" in sample_upper or "PHÊ DUYỆT" in sample_upper:
            return "Đã phê duyệt"
        if "BÃI BỎ" in sample_upper or "HẾT HIỆU LỰC" in sample_upper:
            return "Hết hiệu lực"
        return ""

    @staticmethod
    def extract_title(filename: str, source_path: Path, raw_text: str) -> str:
        """Extracts document title from docx core properties / PDF metadata / text heading / filename."""
        ext = source_path.suffix.lower()
        if ext == ".docx":
            try:
                doc = Document(source_path)
                if doc.core_properties and doc.core_properties.title:
                    title = doc.core_properties.title.strip()
                    if title and len(title) > 3:
                        return title
                # Try first heading 1
                for p in doc.paragraphs:
                    if p.style and "heading 1" in p.style.name.lower() and p.text.strip():
                        return p.text.strip()
            except Exception:
                pass
        elif ext == ".pdf":
            try:
                from .density_checker import density_checker
                doc = density_checker.open_pdf(source_path)
                meta_title = doc.metadata.get("title", "") if doc.metadata else ""
                doc.close()
                if meta_title and len(meta_title.strip()) > 3 and not meta_title.lower().endswith(".pdf"):
                    return meta_title.strip()
            except Exception:
                pass

        # 1. Try finding multiline "V/v" / "Về việc: ..." in text (standard Vietnamese administrative title)
        lines = raw_text[:2500].splitlines()
        capturing = False
        title_parts = []
        for l in lines:
            if re.search(r"^\s*(?:V/v|Về việc|Ve viec)\b", l, re.IGNORECASE):
                capturing = True
                sub = re.sub(r"^\s*(?:V/v|Về việc|Ve viec)\s*[:\-]?\s*", "", l, flags=re.IGNORECASE)
                if sub:
                    title_parts.append(sub)
            elif capturing:
                if re.search(r"^\s*(?:Kính gửi|Kinh gui|TỔNG|TONG|GIÁM|GIAM|CĂN|CAN|Điều|Dieu)\b", l, re.IGNORECASE):
                    break
                if not l.strip():
                    break
                title_parts.append(l.strip())

        if title_parts:
            candidate = " ".join(title_parts).strip().rstrip(".")
            inside_quote = re.search(r"[“\"']([^”\"']{10,})[”\"']", candidate)
            if inside_quote:
                return inside_quote.group(1).strip()
            candidate = re.sub(r"^[“\"'\s]+|[”\"'\s]+$", "", candidate)
            candidate = re.sub(r"^(?:Ban hành|Ban hanh)\s*[“\"'\s]*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"[”\"'\s]+$", "", candidate)
            if len(candidate) > 5:
                return candidate

        # 2. Try finding uppercase title lines like "QUY ĐỊNH ..." or "QUY CHẾ ..."
        title_block_match = re.search(
            r"\b((?:QUY ĐỊNH|QUY CHẾ|QUY TRÌNH|BỘ CHỈ TIÊU|HƯỚNG DẪN|THÔNG TƯ)[^\n\r]{10,})",
            raw_text[:2500]
        )
        if title_block_match:
            candidate = title_block_match.group(1).strip()
            if candidate != "QUYẾT ĐỊNH" and len(candidate) > 10:
                return candidate

        # 3. Try finding first markdown heading in raw_text
        for line in raw_text.splitlines()[:20]:
            clean_l = line.strip()
            if clean_l.startswith("# ") or clean_l.startswith("## "):
                candidate = clean_l.lstrip("# ").strip()
                if candidate and len(candidate) > 5 and candidate != "QUYẾT ĐỊNH":
                    return candidate

        # 4. Fallback to cleaned filename without date and document number prefixes
        stem = Path(filename).stem
        clean_fn = stem
        clean_fn = re.sub(r"^\d{4}[-_.]\d{1,2}[-_.]\d{1,2}\s*", "", clean_fn)
        clean_fn = re.sub(r"^\d+[-/](?:VNPT|QĐ|QD|TT|TB|BC|HD|NQ|CT|KH|BB|VB|CV)[-_/][A-Za-z0-9\-_/Đđ]+\s*", "", clean_fn, flags=re.IGNORECASE)
        clean_fn = re.sub(r"^[_\-\s]+|[_\-\s]+$", "", clean_fn)
        clean_fn = re.sub(r"[-_]+", " ", clean_fn).strip()
        if len(clean_fn) > 3:
            return clean_fn

        return stem.replace("_", " ").replace("-", " ")

    @staticmethod
    def extract_unit(text_sample: str, doc_number: str = "") -> str:
        """Extracts drafting or issuing unit."""
        de_nghi_match = re.search(
            r"Theo đề nghị của (?:các )?(?:Ông|Bà)?\s*(?:Trưởng Ban\s*)?([^\n\r,;\.]+)",
            text_sample[:3000],
            re.IGNORECASE
        )
        if de_nghi_match:
            unit = de_nghi_match.group(1).strip()
            if "Ban " not in unit and not unit.startswith("Tổng"):
                unit = f"Ban {unit}"
            return unit

        if doc_number:
            upper_num = doc_number.upper()
            unit_map = {
                "-CNM": "Ban Công nghệ - Mạng",
                "-KHĐT": "Ban Kế hoạch - Đầu tư",
                "-KHDT": "Ban Kế hoạch - Đầu tư",
                "-TCKT": "Ban Tài chính - Kế toán",
                "-TCCB": "Ban Tổ chức cán bộ",
                "-CLG": "Ban Chất lượng",
                "-CL": "Ban Chất lượng",
                "-VT": "Ban Viễn thông",
                "-CN": "Ban Công nghệ",
                "-IT": "Ban Công nghệ thông tin",
                "-NET": "Tổng công ty VNPT-Net",
                "-VINAPHONE": "Tổng công ty VNPT-VinaPhone",
            }
            for suffix, unit_name in unit_map.items():
                if suffix in upper_num:
                    return unit_name

        return ""

    def build_metadata(
        self,
        filename: str,
        source_path: Path,
        raw_markdown: str,
        source_text: str,
        page_count: int = 1
    ) -> DocumentMetadata:
        """Builds complete DocumentMetadata object."""
        sha256_val = self.calculate_sha256(source_path)
        doc_id = self.generate_document_id(filename)
        combined_text = source_text or raw_markdown
        doc_type = self.detect_document_type(filename, combined_text)
        doc_num = self.extract_document_number(combined_text, filename=filename)
        title = self.extract_title(filename, source_path, raw_markdown)
        version = self.extract_version(filename, combined_text)
        issued_date, effective_date = self.extract_dates(combined_text, filename=filename)
        status = self.extract_status(combined_text)
        unit = self.extract_unit(combined_text, doc_number=doc_num)

        source_char_count = len(source_text) if source_text else len(raw_markdown)
        md_char_count = len(raw_markdown)
        if source_char_count > 0:
            retention_ratio = round(md_char_count / source_char_count, 3)
        else:
            retention_ratio = 1.0 if md_char_count > 0 else 0.0

        today_str = datetime.now().strftime("%Y-%m-%d")

        return DocumentMetadata(
            document_id=doc_id,
            source_file=filename,
            title=title,
            document_type=doc_type,
            organization="VNPT",
            unit=unit,
            version=version,
            document_status=status,
            document_number=doc_num,
            issued_date=issued_date,
            effective_date=effective_date,
            supersedes="",
            superseded_by="",
            scope="Toàn Tập đoàn VNPT" if "VNPT" in doc_num or "TẬP ĐOÀN" in combined_text else "",
            language="vi",
            conversion_date=today_str,
            converter_version=settings.APP_VERSION,
            source_sha256=sha256_val,
            page_count=max(1, page_count),
            source_text_char_count=source_char_count,
            markdown_text_char_count=md_char_count,
            text_retention_ratio=retention_ratio
        )

    @staticmethod
    def generate_yaml_front_matter(meta: DocumentMetadata) -> str:
        """Generates standard YAML Front Matter formatted header."""
        lines = [
            "---",
            f"document_id: \"{meta.document_id}\"",
            f"source_file: \"{meta.source_file}\"",
            f"title: \"{meta.title}\"",
            f"document_type: \"{meta.document_type}\"",
            f"organization: \"{meta.organization}\"",
            f"unit: \"{meta.unit}\"",
            f"version: \"{meta.version}\"",
            f"document_status: \"{meta.document_status}\"",
            f"document_number: \"{meta.document_number}\"",
            f"issued_date: \"{meta.issued_date}\"",
            f"effective_date: \"{meta.effective_date}\"",
            f"supersedes: \"{meta.supersedes}\"",
            f"superseded_by: \"{meta.superseded_by}\"",
            f"scope: \"{meta.scope}\"",
            f"language: \"{meta.language}\"",
            f"conversion_date: \"{meta.conversion_date}\"",
            f"converter_version: \"{meta.converter_version}\"",
            f"source_sha256: \"{meta.source_sha256}\"",
            f"page_count: {meta.page_count}",
            f"source_text_char_count: {meta.source_text_char_count}",
            f"markdown_text_char_count: {meta.markdown_text_char_count}",
            f"text_retention_ratio: {meta.text_retention_ratio}",
            "---",
            ""
        ]
        return "\n".join(lines)

metadata_extractor = MetadataExtractor()
