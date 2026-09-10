from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from ..models import ConvertResponse

class IndexGenerator:
    """
    Generates 00_Master_Index.md, manifest.json, and conversion_report.md
    for comprehensive AI Knowledge Base navigation and quality audits.
    """

    @staticmethod
    def generate_master_index(documents: List[ConvertResponse], kb_name: str = "VNPT-AI-Knowledge-Base") -> str:
        now_iso = datetime.now().astimezone().isoformat()
        
        md_lines = [
            "---",
            f"knowledge_base: \"{kb_name}\"",
            f"generated_at: \"{now_iso}\"",
            f"document_count: {len(documents)}",
            "---",
            "",
            "# MASTER INDEX — BẢN ĐỒ TRI THỨC HỆ THỐNG",
            "",
            "Tài liệu này là Entry Point định hướng cho các Agent AI, mô hình RAG và người dùng tra cứu toàn bộ cơ sở tri thức.",
            "",
            "## 1. Danh mục tài liệu trong Knowledge Base",
            "",
            "| STT | Document ID | Tên tài liệu | Loại | Phiên bản | Trạng thái | Ngày | File Markdown |",
            "|---|---|---|---|---|---|---|---|"
        ]

        for idx, doc in enumerate(documents, start=1):
            meta = doc.metadata
            doc_id = meta.document_id if meta else doc.document_id or f"DOC-{idx:02d}"
            title = meta.title if meta and meta.title else doc.filename
            doc_type = meta.document_type if meta else ""
            version = meta.version if meta else ""
            status = meta.document_status if meta else ""
            date_val = (meta.issued_date or meta.effective_date) if meta else ""
            md_path = f"documents/{Path(doc.filename).stem}.md"

            md_lines.append(
                f"| {idx} | **{doc_id}** | {title} | {doc_type} | {version} | {status} | {date_val} | [`{md_path}`]({md_path}) |"
            )

        md_lines.append("\n---\n")
        md_lines.append("## 2. Chi tiết mục lục & Cấu trúc phân cấp từng tài liệu\n")

        for doc in documents:
            meta = doc.metadata
            doc_id = meta.document_id if meta else doc.document_id
            title = meta.title if meta and meta.title else doc.filename
            md_path = f"documents/{Path(doc.filename).stem}.md"

            md_lines.append(f"### 📄 {doc_id} — {title}")
            md_lines.append(f"- **Tệp nguồn gốc (Source file):** `{doc.filename}`")
            if meta:
                if meta.version:
                    md_lines.append(f"- **Phiên bản:** {meta.version}")
                if meta.document_status:
                    md_lines.append(f"- **Trạng thái:** {meta.document_status}")
                if meta.issued_date or meta.effective_date:
                    md_lines.append(f"- **Ngày ban hành / hiệu lực:** {meta.issued_date or meta.effective_date}")
                if meta.source_sha256:
                    md_lines.append(f"- **Mã băm SHA-256:** `{meta.source_sha256}`")
            md_lines.append(f"- **Liên kết file Markdown:** [`{md_path}`]({md_path})")
            md_lines.append(f"- **Tổng số trang:** {doc.pages_total}")
            
            md_lines.append("\n#### Cấu trúc đề mục nội dung:")
            if doc.sections:
                for sec in doc.sections:
                    indent = "  " * max(0, sec.level - 1)
                    page_info = f" *(Trang {sec.source_page_start})*" if sec.source_page_start else ""
                    md_lines.append(f"{indent}- [{sec.heading}]({md_path}#{sec.id}){page_info}")
            else:
                md_lines.append("- *(Văn bản liền mạch không chia phân đoạn nhỏ)*")

            md_lines.append("\n")

        return "\n".join(md_lines).strip()

    @staticmethod
    def generate_manifest(documents: List[ConvertResponse], kb_name: str = "VNPT-AI-Knowledge-Base") -> Dict[str, Any]:
        now_iso = datetime.now().astimezone().isoformat()
        
        doc_list = []
        for doc in documents:
            meta = doc.metadata
            doc_item = {
                "document_id": meta.document_id if meta else doc.document_id,
                "source_file": doc.filename,
                "markdown_file": f"documents/{Path(doc.filename).stem}.md",
                "sha256": meta.source_sha256 if meta else doc.source_sha256,
                "title": meta.title if meta else doc.filename,
                "document_type": meta.document_type if meta else "",
                "version": meta.version if meta else "",
                "status": meta.document_status if meta else "",
                "issued_date": meta.issued_date if meta else "",
                "effective_date": meta.effective_date if meta else "",
                "page_count": doc.pages_total,
                "word_count": doc.word_count,
                "character_count": doc.character_count,
                "retention_ratio": meta.text_retention_ratio if meta else 1.0,
                "validation_status": doc.validation.status if doc.validation else "PASS",
                "sections": [
                    {
                        "id": sec.id,
                        "heading": sec.heading,
                        "level": sec.level,
                        "source_page_start": sec.source_page_start,
                        "source_page_end": sec.source_page_end
                    } for sec in doc.sections
                ]
            }
            doc_list.append(doc_item)

        return {
            "schema_version": "1.0",
            "knowledge_base": kb_name,
            "generated_at": now_iso,
            "total_documents": len(documents),
            "documents": doc_list
        }

    @staticmethod
    def generate_conversion_report(documents: List[ConvertResponse]) -> str:
        md_lines = [
            "# BÁO CÁO KIỂM ĐỊNH CHẤT LƯỢNG CHUYỂN ĐỔI (CONVERSION QUALITY REPORT)",
            "",
            "Báo cáo tự động đánh giá độ toàn vẹn cấu trúc và độ tin cậy của các tài liệu sau khi chuyển đổi sang Markdown.",
            "",
            "## 1. Ma trận tổng quan",
            "",
            "| Tệp nguồn | Kết quả | Số trang | Số đề mục | Tỷ lệ giữ ký tự | OCR | Cảnh báo |",
            "|---|---|---:|---:|---:|---|---|"
        ]

        for doc in documents:
            meta = doc.metadata
            v_status = doc.validation.status if doc.validation else "PASS"
            status_badge = f"**{v_status}**"
            if v_status == "PASS":
                status_badge = "✅ PASS"
            elif v_status == "WARNING":
                status_badge = "⚠️ WARNING"
            else:
                status_badge = "❌ FAIL"

            retention_str = f"{int(meta.text_retention_ratio * 100)}%" if meta else "100%"
            ocr_str = f"Có ({len(doc.pages_ocr)} trang)" if doc.pages_ocr else "Không"
            warn_count = len(doc.warnings) + (len(doc.validation.warnings) if doc.validation else 0)
            warn_str = f"{warn_count} cảnh báo" if warn_count > 0 else "0"

            md_lines.append(
                f"| `{doc.filename}` | {status_badge} | {doc.pages_total} | {len(doc.sections)} | {retention_str} | {ocr_str} | {warn_str} |"
            )

        md_lines.append("\n---\n")
        md_lines.append("## 2. Chi tiết kết quả kiểm định từng tài liệu\n")

        for doc in documents:
            md_lines.append(f"### 📋 `{doc.filename}`")
            if doc.validation:
                for check in doc.validation.checks:
                    icon = "✅" if check.passed else "⚠️"
                    md_lines.append(f"- {icon} **{check.name}:** {check.message}")

            if doc.warnings or (doc.validation and doc.validation.warnings):
                all_warns = list(set(doc.warnings + (doc.validation.warnings if doc.validation else [])))
                md_lines.append("\n**Cảnh báo ghi nhận:**")
                for w in all_warns:
                    md_lines.append(f"  - ⚠️ {w}")
            md_lines.append("\n")

        return "\n".join(md_lines).strip()

index_generator = IndexGenerator()
