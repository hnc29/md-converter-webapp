from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from ..models import ConvertResponse

class IndexGenerator:
    """
    Generates 00_Master_Index.md, manifest.json, conversion_report.md,
    and README.txt for the Knowledge Package.
    """

    @staticmethod
    def generate_master_index(documents: List[ConvertResponse], kb_name: str = "VNPT-AI-Knowledge-Base") -> str:
        now_iso = datetime.now().astimezone().isoformat()
        
        md_lines = [
            "---",
            "knowledge_base_schema: \"1.0\"",
            f"generated_at: \"{now_iso}\"",
            f"document_count: {len(documents)}",
            "---",
            "",
            "# MASTER INDEX",
            "",
            "## Hướng dẫn sử dụng",
            "",
            "Đây là bản đồ điều hướng của Knowledge Base.",
            "",
            "Khi trả lời câu hỏi:",
            "1. Xác định tài liệu liên quan từ Master Index.",
            "2. Truy xuất nội dung từ tài liệu Markdown gốc.",
            "3. Không sử dụng Master Index thay cho tài liệu gốc để kết luận.",
            "4. Nếu có nhiều phiên bản, ưu tiên tài liệu có hiệu lực, thẩm quyền và thời gian phù hợp nếu có đủ căn cứ.",
            "5. Nếu không xác định được tài liệu hiện hành, không tự suy đoán.",
            "",
            "## Danh mục tài liệu",
            "",
            "| ID | Tài liệu | Loại | Phiên bản | Trạng thái | Ngày | File |",
            "|---|---|---|---|---|---|---|"
        ]

        for idx, doc in enumerate(documents, start=1):
            meta = doc.metadata
            doc_id = meta.document_id if meta else doc.document_id or f"DOC-{idx:02d}"
            title = meta.title if meta and meta.title else doc.filename
            doc_type = meta.document_type if meta else "Other"
            version = meta.version if meta else ""
            status = meta.document_status if meta else ""
            date_val = (meta.issued_date or meta.effective_date) if meta else ""
            md_filename = f"{Path(doc.filename).stem}.md"

            md_lines.append(
                f"| **{doc_id}** | {title} | {doc_type} | {version} | {status} | {date_val} | [`{md_filename}`]({md_filename}) |"
            )

        md_lines.append("\n---\n")
        md_lines.append("## Chi tiết cấu trúc mục lục từng tài liệu\n")

        for doc in documents:
            meta = doc.metadata
            doc_id = meta.document_id if meta else doc.document_id
            title = meta.title if meta and meta.title else doc.filename
            md_filename = f"{Path(doc.filename).stem}.md"

            md_lines.append(f"### {doc_id} — {title}")
            md_lines.append(f"**File:** `{md_filename}`")
            if meta:
                if meta.version:
                    md_lines.append(f"- **Phiên bản:** {meta.version}")
                if meta.document_status:
                    md_lines.append(f"- **Trạng thái:** {meta.document_status}")
                if meta.issued_date or meta.effective_date:
                    md_lines.append(f"- **Ngày ban hành / hiệu lực:** {meta.issued_date or meta.effective_date}")
                if meta.source_sha256:
                    md_lines.append(f"- **Mã băm SHA-256:** `{meta.source_sha256}`")

            md_lines.append("\n#### Cấu trúc đề mục:")
            if doc.sections:
                for sec in doc.sections:
                    indent = "  " * max(0, sec.level - 1)
                    page_info = f" *(Trang {sec.source_page_start})*" if sec.source_page_start else ""
                    md_lines.append(f"{indent}- [{sec.heading}]({md_filename}#{sec.id}){page_info}")
            else:
                md_lines.append("- *(Văn bản liền mạch không chia phân đoạn)*")

            md_lines.append("\n")

        return "\n".join(md_lines).strip()

    @staticmethod
    def generate_readme_txt(is_single_mode: bool, total_count: int, ready_count: int, failed_count: int) -> str:
        if is_single_mode:
            doc_mode_msg = "Chế độ: 1 tài liệu đơn lẻ (Single Document Mode)."
            upload_inst = "Upload file .md duy nhất trong thư mục 'upload_to_ai/'."
        else:
            doc_mode_msg = f"Chế độ: Knowledge Pack ({ready_count} tài liệu)."
            upload_inst = "Upload '00_Master_Index.md' và toàn bộ các file .md trong thư mục 'upload_to_ai/'."

        failed_msg = ""
        if failed_count > 0:
            failed_msg = f"\nLƯU Ý: Có {failed_count} file không đạt Quality Gate đã được chuyển sang 'technical/failed/'.\n"

        return f"""======================================================================
  HƯỚNG DẪN SỬ DỤNG KNOWLEDGE PACKAGE CHO AI (CHATGPT / RAG)
======================================================================

{doc_mode_msg}
Tổng tài liệu đã xử lý: {total_count}
Số tài liệu sẵn sàng nạp AI: {ready_count}{failed_msg}

CÁCH SỬ DỤNG:
1. Mở thư mục 'upload_to_ai/'.
2. Chọn TOÀN BỘ file trong thư mục 'upload_to_ai/'.
3. Upload trực tiếp vào Knowledge/File Library của ChatGPT hoặc hệ thống RAG.
   {upload_inst}

KHÔNG CẦN UPLOAD CÁC THƯ MỤC SAU:
- source/    : Lưu trữ file nguồn gốc (.docx, .pdf, .xlsx, .doc, .xls...).
- technical/ : Chứa manifest.json, conversion_report.md và file lỗi nếu có.
- assets/    : Lưu trữ hình ảnh trích xuất từ tài liệu.

QUY TẮC:
Mọi file trong 'upload_to_ai/' đều đã qua Quality Gate, chuẩn hóa UTF-8 NFC,
có YAML metadata trung thực, bảo toàn Heading và định danh Section ID.
"""

    @staticmethod
    def generate_manifest(documents: List[ConvertResponse], failed_documents: List[ConvertResponse] = None, kb_name: str = "VNPT-AI-Knowledge-Base") -> Dict[str, Any]:
        now_iso = datetime.now().astimezone().isoformat()
        failed_documents = failed_documents or []
        
        doc_list = []
        for doc in documents:
            meta = doc.metadata
            doc_item = {
                "document_id": meta.document_id if meta else doc.document_id,
                "source_file": doc.filename,
                "markdown_file": f"upload_to_ai/{Path(doc.filename).stem}.md",
                "sha256": meta.source_sha256 if meta else doc.source_sha256,
                "title": meta.title if meta else doc.filename,
                "document_type": meta.document_type if meta else "Other",
                "version": meta.version if meta else "",
                "status": meta.document_status if meta else "",
                "issued_date": meta.issued_date if meta else "",
                "effective_date": meta.effective_date if meta else "",
                "page_count": doc.pages_total,
                "word_count": doc.word_count,
                "character_count": doc.character_count,
                "retention_ratio": meta.text_retention_ratio if meta else 1.0,
                "validation_status": doc.validation.status if doc.validation else "PASS",
                "is_safe_for_ai": True,
                "sections": [
                    {
                        "id": sec.id,
                        "heading": sec.heading,
                        "level": sec.level,
                        "page_start": sec.source_page_start,
                        "page_end": sec.source_page_end
                    } for sec in doc.sections
                ]
            }
            doc_list.append(doc_item)

        failed_list = []
        for doc in failed_documents:
            meta = doc.metadata
            failed_list.append({
                "source_file": doc.filename,
                "markdown_file": f"technical/failed/{Path(doc.filename).stem}.md",
                "sha256": meta.source_sha256 if meta else doc.source_sha256,
                "validation_status": "FAIL",
                "is_safe_for_ai": False,
                "errors": doc.validation.errors if doc.validation else ["Validation failed"]
            })

        return {
            "schema_version": "1.0",
            "knowledge_base": kb_name,
            "generated_at": now_iso,
            "total_documents": len(documents) + len(failed_documents),
            "ready_for_ai_count": len(documents),
            "failed_count": len(failed_documents),
            "documents": doc_list,
            "failed_documents": failed_list
        }

    @staticmethod
    def generate_conversion_report(documents: List[ConvertResponse], failed_documents: List[ConvertResponse] = None) -> str:
        failed_documents = failed_documents or []
        all_docs = documents + failed_documents

        md_lines = [
            "# CONVERSION QUALITY REPORT",
            "",
            "Báo cáo kiểm định chất lượng chuyển đổi tài liệu sang Markdown phục vụ AI Knowledge Base.",
            "",
            "## 1. Ma trận tổng quan",
            "",
            "| Tệp nguồn | Kết quả | Số trang | Số đề mục | Text Retention | Thư mục lưu | Cảnh báo |",
            "|---|---|---:|---:|---:|---|---|"
        ]

        for doc in all_docs:
            meta = doc.metadata
            v_status = doc.validation.status if doc.validation else "PASS"
            if v_status == "PASS":
                status_badge = "✅ PASS"
                target_dir = "`upload_to_ai/`"
            elif v_status == "WARNING":
                status_badge = "⚠️ WARNING"
                target_dir = "`upload_to_ai/`"
            else:
                status_badge = "❌ FAIL"
                target_dir = "`technical/failed/`"

            retention_str = f"{int(meta.text_retention_ratio * 100)}%" if meta else "100%"
            warn_count = len(doc.warnings) + (len(doc.validation.warnings) if doc.validation else 0)
            warn_str = f"{warn_count} cảnh báo" if warn_count > 0 else "0"

            md_lines.append(
                f"| `{doc.filename}` | {status_badge} | {doc.pages_total} | {len(doc.sections)} | {retention_str} | {target_dir} | {warn_str} |"
            )

        md_lines.append("\n---\n")
        md_lines.append("## 2. Chi tiết kiểm định từng tài liệu\n")

        for doc in all_docs:
            md_lines.append(f"### 📋 `{doc.filename}`")
            if doc.validation:
                for check in doc.validation.checks:
                    icon = "✅" if check.passed else ("⚠️" if doc.validation.is_safe_for_ai else "❌")
                    md_lines.append(f"- {icon} **{check.name}:** {check.message}")

            all_warns = list(set(doc.warnings + (doc.validation.warnings if doc.validation else []) + (doc.validation.errors if doc.validation else [])))
            if all_warns:
                md_lines.append("\n**Ghi chú & Cảnh báo:**")
                for w in all_warns:
                    md_lines.append(f"  - ⚠️ {w}")
            md_lines.append("\n")

        return "\n".join(md_lines).strip()

index_generator = IndexGenerator()
