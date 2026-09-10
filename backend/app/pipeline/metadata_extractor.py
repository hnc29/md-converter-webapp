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
        """Detects document type token (HLD, LLD, PRO, UM, QD, TT, BC, etc.)."""
        upper_name = filename.upper()
        upper_text = text_sample[:2000].upper()

        type_map = [
            ("HLD", ["HLD", "HIGH-LEVEL DESIGN", "THIẾT KẾ TỔNG THỂ"]),
            ("LLD", ["LLD", "LOW-LEVEL DESIGN", "THIẾT KẾ CHI TIẾT"]),
            ("PRO", ["PRO", "PROCEDURE", "QUY TRÌNH"]),
            ("UM", ["UM", "USER MANUAL", "HƯỚNG DẪN SỬ DỤNG"]),
            ("QĐ", ["QĐ", "QUYẾT ĐỊNH", "QUYET DINH", "QD"]),
            ("TT", ["THÔNG TƯ", "THONG TU"]),
            ("BC", ["BÁO CÁO", "BAO CAO", "REPORT"]),
            ("PL", ["PHỤ LỤC", "PHU LUC", "APPENDIX"]),
            ("HD", ["HƯỚNG DẪN", "HUONG DAN"]),
            ("TB", ["THÔNG BÁO", "THONG BAO"]),
        ]

        for doc_type, keywords in type_map:
            for kw in keywords:
                if kw in upper_name or kw in upper_text:
                    return doc_type
        return ""

    @staticmethod
    def extract_document_number(text_sample: str) -> str:
        """Extracts official document number like '2079/QĐ-VNPT-CN' without guessing."""
        match = re.search(r"(?:Số|Số hiệu|No\.?):\s*([0-9]+[A-Za-z0-9\/\-_]+(?:VNPT|QĐ|TT|BC|HD)?[A-Za-z0-9\/\-_]*)", text_sample, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Direct pattern match for VN standard doc numbers
        direct_match = re.search(r"(\d+/(?:QĐ|TT|TB|BC|HD|NQ)-[A-Za-z0-9\-_]+)", text_sample)
        if direct_match:
            return direct_match.group(1).strip()
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
    def extract_dates(text_sample: str) -> Tuple[str, str]:
        """Extracts (issued_date, effective_date) if explicitly stated."""
        issued_date = ""
        effective_date = ""

        # Issued date pattern: "ngày ... tháng ... năm ..." or "dd/mm/yyyy"
        vn_date_match = re.search(r"(?:ngày|Hà Nội, ngày)\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})", text_sample, re.IGNORECASE)
        if vn_date_match:
            d, m, y = vn_date_match.groups()
            issued_date = f"{int(d):02d}/{int(m):02d}/{y}"
        else:
            std_date_match = re.search(r"(?:Ngày ban hành|Ban hành ngày|Ngày|Date|Issued Date)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})", text_sample, re.IGNORECASE)
            if std_date_match:
                issued_date = std_date_match.group(1).replace("-", "/").replace(".", "/")

        # Effective date pattern
        eff_match = re.search(r"(?:Hiệu lực từ ngày|Có hiệu lực từ ngày|Ngày hiệu lực|Effective Date)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})", text_sample, re.IGNORECASE)
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
                doc = pymupdf.open(str(source_path))
                meta_title = doc.metadata.get("title", "") if doc.metadata else ""
                if meta_title and len(meta_title.strip()) > 3:
                    return meta_title.strip()
            except Exception:
                pass

        # Try finding first markdown heading in raw_text
        for line in raw_text.splitlines()[:20]:
            clean_l = line.strip()
            if clean_l.startswith("# "):
                candidate = clean_l.lstrip("# ").strip()
                if candidate:
                    return candidate

        # Fallback to normalized filename without extension
        stem = Path(filename).stem
        return stem.replace("_", " ").replace("-", " ")

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
        title = self.extract_title(filename, source_path, raw_markdown)
        doc_type = self.detect_document_type(filename, source_text or raw_markdown)
        doc_num = self.extract_document_number(source_text or raw_markdown)
        version = self.extract_version(filename, source_text or raw_markdown)
        issued_date, effective_date = self.extract_dates(source_text or raw_markdown)
        status = self.extract_status(source_text or raw_markdown)

        source_char_count = len(source_text) if source_text else len(raw_markdown)
        md_char_count = len(raw_markdown)
        retention_ratio = round(md_char_count / max(1, source_char_count), 3) if source_char_count > 0 else 1.0

        today_str = datetime.now().strftime("%Y-%m-%d")

        return DocumentMetadata(
            document_id=doc_id,
            source_file=filename,
            title=title,
            document_type=doc_type,
            organization="VNPT",
            unit="",
            version=version,
            document_status=status,
            document_number=doc_num,
            issued_date=issued_date,
            effective_date=effective_date,
            supersedes="",
            superseded_by="",
            scope="",
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
