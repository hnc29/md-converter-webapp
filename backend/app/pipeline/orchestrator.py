import time
import shutil
import uuid
import re
from pathlib import Path
from typing import List, Optional, Tuple
from docx import Document

from ..config import settings
from ..models import ConvertResponse, PageResult, KnowledgeBaseResponse
from .legacy_converter import convert_legacy_document, LegacyConversionError
from .markitdown_service import markitdown_service
from .density_checker import density_checker
from .ocr_adapter import ocr_adapter, OCRAdapterError
from .markdown_merger import markdown_merger
from .metadata_extractor import metadata_extractor
from .structure_normalizer import structure_normalizer
from .table_processor import table_processor
from .validator import validator
from .index_generator import index_generator

class ConversionPipelineError(Exception):
    """General error in conversion pipeline."""

def convert_docx_structured(docx_path: Path) -> Tuple[str, str]:
    """
    Parses DOCX document preserving headings hierarchy, tables, paragraphs,
    and lists without losing text or structure.
    Returns: (markdown_text, raw_source_text)
    """
    doc = Document(docx_path)
    md_lines: List[str] = []
    raw_text_parts: List[str] = []

    # Process paragraphs and tables in natural document flow
    for element in doc.element.body:
        # Check if element is a paragraph
        if element.tag.endswith('p'):
            for para in doc.paragraphs:
                if para._p == element:
                    text = para.text.strip()
                    if not text:
                        continue
                    raw_text_parts.append(text)
                    style_name = (para.style.name or "").lower() if para.style else ""

                    if "heading 1" in style_name or "tiêu đề 1" in style_name:
                        md_lines.append(f"\n# {text}\n")
                    elif "heading 2" in style_name or "tiêu đề 2" in style_name:
                        md_lines.append(f"\n## {text}\n")
                    elif "heading 3" in style_name or "tiêu đề 3" in style_name:
                        md_lines.append(f"\n### {text}\n")
                    elif "heading 4" in style_name or "tiêu đề 4" in style_name:
                        md_lines.append(f"\n#### {text}\n")
                    elif "heading 5" in style_name or "tiêu đề 5" in style_name:
                        md_lines.append(f"\n##### {text}\n")
                    elif "list" in style_name or "bullet" in style_name:
                        md_lines.append(f"- {text}")
                    else:
                        # Heuristic heading detection based on numbering pattern
                        if re.match(r"^\d+\.\s+[A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ]", text):
                            md_lines.append(f"\n## {text}\n")
                        elif re.match(r"^\d+\.\d+\.\s+", text):
                            md_lines.append(f"\n### {text}\n")
                        elif re.match(r"^\d+\.\d+\.\d+\.\s+", text):
                            md_lines.append(f"\n#### {text}\n")
                        else:
                            md_lines.append(f"{text}\n")
                    break

        # Check if element is a table
        elif element.tag.endswith('tbl'):
            for tbl in doc.tables:
                if tbl._tbl == element:
                    rows_data = []
                    for row in tbl.rows:
                        row_cells = [c.text.replace("\n", " ").strip() for c in row.cells]
                        raw_text_parts.extend(row_cells)
                        rows_data.append(row_cells)
                    if rows_data:
                        tbl_md = table_processor.format_markdown_table(rows_data)
                        md_lines.append(f"\n{tbl_md}\n")
                    break

    markdown_result = "\n".join(md_lines).strip()
    raw_source = "\n".join(raw_text_parts).strip()
    return markdown_result, raw_source

class Orchestrator:
    """
    Coordinates the 7-step AI Knowledge Base document conversion pipeline.
    """

    def process_file(self, original_filename: str, source_path: Path, ocr_engine: str = "tesseract") -> ConvertResponse:
        start_time = time.time()
        temp_dir = settings.STORAGE_TMP_DIR / f"job_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        warnings: List[str] = []
        converted_via_legacy = False
        body_markdown = ""
        source_raw_text = ""
        pages_total = 1
        pages_ocr: List[int] = []
        is_paginated = False
        is_pure_ocr = False

        try:
            # Step 1: Validate Extension
            ext = Path(original_filename).suffix.lower()
            if ext not in settings.ALLOWED_EXTENSIONS:
                raise ConversionPipelineError(
                    f"Định dạng '{ext}' không được hỗ trợ. Các định dạng cho phép: {', '.join(settings.ALLOWED_EXTENSIONS)}"
                )

            # Step 0: Check Legacy (.doc / .xls)
            current_path = source_path
            if ext in settings.LEGACY_EXTENSIONS:
                try:
                    current_path, converted_via_legacy = convert_legacy_document(
                        input_path=source_path,
                        output_dir=temp_dir
                    )
                    ext = current_path.suffix.lower()
                except LegacyConversionError as e:
                    warnings.append(str(e))
                    err_md = f"# {original_filename}\n\n> ⚠️ **Lỗi chuyển đổi định dạng cũ (.doc/.xls)**: {str(e)}"
                    return ConvertResponse(
                        filename=original_filename,
                        document_id=metadata_extractor.generate_document_id(original_filename),
                        converted_via_legacy=False,
                        markdown=err_md,
                        warnings=warnings,
                        ocr_engine_used=ocr_engine,
                        duration_ms=int((time.time() - start_time) * 1000)
                    )

            # Step 2: DOCX Structured Conversion
            if ext == ".docx":
                try:
                    body_markdown, source_raw_text = convert_docx_structured(current_path)
                    if not body_markdown:
                        body_markdown = markitdown_service.convert_file(current_path)
                        source_raw_text = body_markdown
                except Exception as docx_err:
                    warnings.append(f"DOCX native parser warning: {str(docx_err)}; Using MarkItDown fallback.")
                    body_markdown = markitdown_service.convert_file(current_path)
                    source_raw_text = body_markdown
                pages_total = 1

            # Step 3: Excel Spreadsheet Conversion
            elif ext == ".xlsx":
                try:
                    body_markdown = table_processor.convert_excel_to_markdown(current_path)
                    source_raw_text = body_markdown
                except Exception as xl_err:
                    warnings.append(f"Excel parser warning: {str(xl_err)}")
                    body_markdown = markitdown_service.convert_file(current_path)
                    source_raw_text = body_markdown
                pages_total = 1

            # Step 4: PDF Processing (Page by Page with Markers & OCR)
            elif ext == ".pdf":
                is_paginated = True
                try:
                    pdf_inspection = density_checker.inspect_pdf_pages(current_path)
                except Exception as pdf_err:
                    warnings.append(f"Lỗi đọc PDF: {str(pdf_err)}")
                    pdf_inspection = [(1, "", True)]

                pages_total = max(1, len(pdf_inspection))
                page_results: List[PageResult] = []
                raw_parts: List[str] = []

                for page_num, text_layer, needs_ocr in pdf_inspection:
                    if text_layer:
                        raw_parts.append(text_layer)

                    if needs_ocr:
                        pages_ocr.append(page_num)
                        try:
                            img = density_checker.rasterize_page(
                                current_path,
                                page_number=page_num,
                                dpi=settings.RASTERIZE_DPI
                            )
                            ocr_text, confidence = ocr_adapter.perform_ocr(img, engine=ocr_engine)
                            
                            if confidence is not None and confidence < 0.6:
                                warnings.append(
                                    f"Trang {page_num}: Độ tin cậy OCR ({int(confidence * 100)}%)."
                                )

                            raw_parts.append(ocr_text)
                            page_results.append(
                                PageResult(
                                    page_number=page_num,
                                    text=f"> [Extracted from image via {ocr_engine.upper()}]\n{ocr_text}" if ocr_text else "*(Trang quét ảnh trống)*",
                                    is_ocr=True,
                                    confidence=confidence,
                                    char_count=len(ocr_text)
                                )
                            )
                        except (OCRAdapterError, Exception) as ocr_err:
                            warnings.append(f"Lỗi OCR tại trang {page_num}: {str(ocr_err)}")
                            page_results.append(
                                PageResult(
                                    page_number=page_num,
                                    text=text_layer or "*(Lỗi khi nhận diện hình ảnh/OCR)*",
                                    is_ocr=False,
                                    char_count=len(text_layer)
                                )
                            )
                    else:
                        page_results.append(
                            PageResult(
                                page_number=page_num,
                                text=text_layer,
                                is_ocr=False,
                                char_count=len(text_layer)
                            )
                        )

                if len(pages_ocr) == pages_total:
                    is_pure_ocr = True

                # Merge pages with explicit source_page markers
                body_parts: List[str] = []
                for p in page_results:
                    body_parts.append(f"<!-- source_page: {p.page_number} -->\n\n{p.text.strip()}")
                body_markdown = "\n\n---\n\n".join(body_parts)
                source_raw_text = "\n".join(raw_parts)

            else:
                body_markdown = markitdown_service.convert_file(current_path)
                source_raw_text = body_markdown

            # Step 5: Normalize Encoding (Unicode NFC, remove NULL bytes, BOM)
            body_markdown = structure_normalizer.normalize_encoding(body_markdown)
            source_raw_text = structure_normalizer.normalize_encoding(source_raw_text)

            # Step 6: Process Headings & Inject Stable Section IDs (<a id="..."></a>)
            normalized_body, sections = structure_normalizer.process_headings_and_sections(body_markdown)
            normalized_body = structure_normalizer.clean_markdown_boundaries(normalized_body)

            # Step 7: Build Metadata & YAML Front Matter
            doc_meta = metadata_extractor.build_metadata(
                filename=original_filename,
                source_path=source_path,
                raw_markdown=normalized_body,
                source_text=source_raw_text,
                page_count=pages_total
            )
            yaml_header = metadata_extractor.generate_yaml_front_matter(doc_meta)

            final_markdown = f"{yaml_header}\n{normalized_body}"

            # Step 8: Quality Gate Automated Validation
            val_result = validator.validate(final_markdown, doc_meta, is_paginated=is_paginated, is_ocr=is_pure_ocr)
            if val_result.warnings:
                warnings.extend(val_result.warnings)

            # Stats
            word_count, character_count = markdown_merger.calculate_stats(final_markdown)
            duration_ms = int((time.time() - start_time) * 1000)

            return ConvertResponse(
                filename=original_filename,
                document_id=doc_meta.document_id,
                converted_via_legacy=converted_via_legacy,
                markdown=final_markdown,
                metadata=doc_meta,
                sections=sections,
                validation=val_result,
                pages_total=pages_total,
                pages_ocr=pages_ocr,
                ocr_engine_used=ocr_engine,
                warnings=list(set(warnings)),
                duration_ms=duration_ms,
                word_count=word_count,
                character_count=character_count,
                source_sha256=doc_meta.source_sha256
            )

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def process_knowledge_base(self, files_data: List[Tuple[str, Path]], kb_name: str = "VNPT-AI-Knowledge-Base", ocr_engine: str = "tesseract") -> KnowledgeBaseResponse:
        """
        Builds the complete Knowledge Package:
        - Single Document Mode: 1 file -> upload_to_ai/<doc>.md (NO 00_Master_Index.md)
        - Knowledge Pack Mode: >= 2 files -> upload_to_ai/00_Master_Index.md, upload_to_ai/*.md
        - Separates ready documents from failed documents via Quality Gate
        - Generates technical/manifest.json, technical/conversion_report.md, README.txt
        """
        all_converted: List[ConvertResponse] = []
        for filename, temp_path in files_data:
            res = self.process_file(original_filename=filename, source_path=temp_path, ocr_engine=ocr_engine)
            all_converted.append(res)

        ready_docs = [d for d in all_converted if d.validation and d.validation.is_safe_for_ai]
        failed_docs = [d for d in all_converted if d.validation and not d.validation.is_safe_for_ai]

        is_single_mode = (len(ready_docs) == 1)

        # 00_Master_Index.md: ONLY generated when >= 2 ready documents
        if len(ready_docs) >= 2:
            master_index = index_generator.generate_master_index(ready_docs, kb_name=kb_name)
        else:
            master_index = ""

        manifest = index_generator.generate_manifest(ready_docs, failed_documents=failed_docs, kb_name=kb_name)
        report = index_generator.generate_conversion_report(ready_docs, failed_documents=failed_docs)
        readme = index_generator.generate_readme_txt(
            is_single_mode=is_single_mode,
            total_count=len(all_converted),
            ready_count=len(ready_docs),
            failed_count=len(failed_docs)
        )

        overall_status = "PASS"
        if failed_docs:
            overall_status = "FAIL"
        elif any(d.validation and d.validation.status == "WARNING" for d in ready_docs):
            overall_status = "WARNING"

        warning_count = sum(1 for d in ready_docs if d.validation and d.validation.status == "WARNING")

        return KnowledgeBaseResponse(
            is_single_mode=is_single_mode,
            master_index_md=master_index,
            manifest_json=manifest,
            conversion_report_md=report,
            readme_txt=readme,
            upload_to_ai_documents=ready_docs,
            failed_documents=failed_docs,
            total_documents=len(all_converted),
            ready_count=len(ready_docs),
            warning_count=warning_count,
            failed_count=len(failed_docs),
            overall_status=overall_status,
            documents=all_converted
        )

orchestrator = Orchestrator()
