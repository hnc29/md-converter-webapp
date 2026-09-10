import time
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from docx import Document
import openpyxl
from ..config import settings
from ..models import ConvertResponse, PageResult
from .legacy_converter import convert_legacy_document, LegacyConversionError
from .markitdown_service import markitdown_service
from .density_checker import density_checker
from .ocr_adapter import ocr_adapter, OCRAdapterError
from .markdown_merger import markdown_merger

class ConversionPipelineError(Exception):
    """General error in conversion pipeline."""

def fallback_docx_to_markdown(docx_path: Path) -> str:
    """Fallback converter using python-docx when MarkItDown fails on complex XML."""
    doc = Document(docx_path)
    md_lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name.lower() if para.style else ""
        if "heading 1" in style:
            md_lines.append(f"# {text}\n")
        elif "heading 2" in style:
            md_lines.append(f"## {text}\n")
        elif "heading 3" in style:
            md_lines.append(f"### {text}\n")
        else:
            md_lines.append(f"{text}\n")

    for table in doc.tables:
        rows_data = []
        for row in table.rows:
            row_cells = [c.text.replace("\n", " ").strip() for c in row.cells]
            rows_data.append(row_cells)
        if rows_data:
            hdr = rows_data[0]
            md_lines.append(f"\n| {' | '.join(hdr)} |")
            md_lines.append(f"| {' | '.join(['---'] * len(hdr))} |")
            for r in rows_data[1:]:
                md_lines.append(f"| {' | '.join(r)} |")
            md_lines.append("\n")

    return "\n".join(md_lines).strip()

def fallback_xlsx_to_markdown(xlsx_path: Path) -> str:
    """Fallback converter using openpyxl when MarkItDown fails."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    md_sheets = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        # Filter empty rows
        valid_rows = [[str(cell if cell is not None else '').strip() for cell in r] for r in rows if any(cell is not None for cell in r)]
        if not valid_rows:
            continue
        sheet_lines = [f"### Sheet: {sheet_name}\n"]
        hdr = valid_rows[0]
        sheet_lines.append(f"| {' | '.join(hdr)} |")
        sheet_lines.append(f"| {' | '.join(['---'] * len(hdr))} |")
        for r in valid_rows[1:]:
            sheet_lines.append(f"| {' | '.join(r)} |")
        md_sheets.append("\n".join(sheet_lines))
    return "\n\n---\n\n".join(md_sheets).strip()

class Orchestrator:
    """
    Coordinates the 7-step document to markdown conversion workflow.
    """

    def process_file(self, original_filename: str, source_path: Path) -> ConvertResponse:
        start_time = time.time()
        temp_dir = settings.STORAGE_TMP_DIR / f"job_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        warnings: List[str] = []
        converted_via_legacy = False
        final_markdown = ""
        pages_total = 1
        pages_ocr: List[int] = []

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
                    final_markdown = f"# {original_filename}\n\n> ⚠️ **Cảnh báo chuyển đổi định dạng cũ**: {str(e)}\n\n*Để chuyển đổi tệp nhị phân cũ (.doc, .xls), vui lòng cài đặt LibreOffice hoặc chạy qua Docker.*"
                    return ConvertResponse(
                        filename=original_filename,
                        converted_via_legacy=False,
                        markdown=final_markdown,
                        pages_total=1,
                        pages_ocr=[],
                        warnings=warnings,
                        duration_ms=int((time.time() - start_time) * 1000),
                        word_count=0,
                        character_count=len(final_markdown)
                    )

            # Step 2: DOCX / XLSX conversion via Microsoft MarkItDown with Fallback
            if ext in {".docx", ".xlsx"}:
                try:
                    final_markdown = markitdown_service.convert_file(current_path)
                except Exception as md_err:
                    warnings.append(f"MarkItDown warning: {str(md_err)}; Chuyển sang parser dự phòng.")
                    if ext == ".docx":
                        final_markdown = fallback_docx_to_markdown(current_path)
                    else:
                        final_markdown = fallback_xlsx_to_markdown(current_path)
                pages_total = 1

            # Steps 3, 4, 5, 6: PDF Processing (Text layer + Density check + Local OCR)
            elif ext == ".pdf":
                try:
                    pdf_inspection = density_checker.inspect_pdf_pages(current_path)
                except Exception as pdf_err:
                    warnings.append(f"Lỗi đọc PDF: {str(pdf_err)}")
                    pdf_inspection = [(1, "", True)]

                pages_total = max(1, len(pdf_inspection))
                page_results: List[PageResult] = []

                for page_num, text_layer, needs_ocr in pdf_inspection:
                    if needs_ocr:
                        pages_ocr.append(page_num)
                        try:
                            # Step 5: Rasterize & run local OCR
                            img = density_checker.rasterize_page(
                                current_path,
                                page_number=page_num,
                                dpi=settings.RASTERIZE_DPI
                            )
                            ocr_text, confidence = ocr_adapter.perform_ocr(img)
                            
                            if confidence is not None and confidence < 0.6:
                                warnings.append(
                                    f"Trang {page_num}: Độ tin cậy OCR tương đối thấp ({int(confidence * 100)}%)."
                                )

                            page_results.append(
                                PageResult(
                                    page_number=page_num,
                                    text=ocr_text,
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
                        # Good text layer: keep original text
                        page_results.append(
                            PageResult(
                                page_number=page_num,
                                text=text_layer,
                                is_ocr=False,
                                char_count=len(text_layer)
                            )
                        )

                # Step 6: Merge pages into single markdown document
                final_markdown = markdown_merger.merge_pages(page_results)

            else:
                # Direct fallback via MarkItDown
                try:
                    final_markdown = markitdown_service.convert_file(current_path)
                except Exception:
                    final_markdown = current_path.read_text(encoding="utf-8", errors="ignore")

            # Calculate stats
            word_count, character_count = markdown_merger.calculate_stats(final_markdown)
            duration_ms = int((time.time() - start_time) * 1000)

            return ConvertResponse(
                filename=original_filename,
                converted_via_legacy=converted_via_legacy,
                markdown=final_markdown,
                pages_total=pages_total,
                pages_ocr=pages_ocr,
                warnings=warnings,
                duration_ms=duration_ms,
                word_count=word_count,
                character_count=character_count
            )

        finally:
            # Step 7: Clean up temporary files in storage
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

orchestrator = Orchestrator()
