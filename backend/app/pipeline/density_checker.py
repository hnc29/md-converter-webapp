import io
from pathlib import Path
from typing import List, Tuple
from PIL import Image
import pymupdf  # PyMuPDF / fitz
from ..config import settings
from ..models import PageResult

class DensityChecker:
    @staticmethod
    def open_pdf(pdf_path: Path) -> pymupdf.Document:
        """
        Safely opens a PDF document using PyMuPDF.
        If the file has corrupted xrefs, appended PDF revisions, or returns 0 pages,
        automatically repairs it using pypdfium2 or multi-stream header recovery.
        """
        try:
            doc = pymupdf.open(str(pdf_path))
            if not doc.is_closed and doc.page_count > 0:
                # Test whether all pages can be loaded
                # In corrupted PDFs, doc.page_count can be > 0 but page tree fails on deeper pages
                try:
                    for i in range(len(doc)):
                        _ = doc.load_page(i)
                    return doc
                except Exception:
                    doc.close()
            elif not doc.is_closed:
                doc.close()
        except Exception:
            pass

        # 1. Recovery via pypdfium2 rewrite
        try:
            import pypdfium2 as pdfium
            pdfium_doc = pdfium.PdfDocument(str(pdf_path))
            try:
                if len(pdfium_doc) > 0:
                    buf = io.BytesIO()
                    pdfium_doc.save(buf)
                    buf.seek(0)
                    repaired_doc = pymupdf.open(stream=buf.getvalue(), filetype="pdf")
                    if repaired_doc.page_count > 0:
                        return repaired_doc
                    repaired_doc.close()
            finally:
                pdfium_doc.close()
        except Exception:
            pass

        # 2. Recovery via searching for %PDF- markers (for concatenated/appended PDFs)
        try:
            data = pdf_path.read_bytes()
            import re
            pdf_starts = [m.start() for m in re.finditer(b"%PDF-", data)]
            if len(pdf_starts) > 1:
                for offset in reversed(pdf_starts):
                    try:
                        sub_doc = pymupdf.open(stream=data[offset:], filetype="pdf")
                        if sub_doc.page_count > 0:
                            return sub_doc
                        sub_doc.close()
                    except Exception:
                        continue
        except Exception:
            pass

        # Final fallback
        return pymupdf.open(str(pdf_path))

    @classmethod
    def check_pdf_health(cls, pdf_path: Path) -> bool:
        """
        Verifies if PyMuPDF can cleanly open, traverse all pages, and render content.
        Returns True if fully healthy, False if damaged/needs repair.
        """
        try:
            doc = pymupdf.open(str(pdf_path))
            if doc.is_closed or doc.page_count == 0:
                return False
            # Check every page can be loaded
            for i in range(len(doc)):
                _ = doc.load_page(i)
            # Check if first page render works (detects stream syntax corruptions that produce blank pages)
            p0 = doc.load_page(0)
            images = p0.get_images()
            if images:
                pix = p0.get_pixmap(dpi=72)
                if pix.samples:
                    import numpy as np
                    arr = np.frombuffer(pix.samples, dtype=np.uint8)
                    if arr.min() == 255 and arr.max() == 255:
                        doc.close()
                        return False
            doc.close()
            return True
        except Exception:
            return False

    @classmethod
    def ensure_valid_pdf(cls, pdf_path: Path, output_dir: Path) -> Path:
        """
        Checks if the PDF opens cleanly and can load/render all pages in PyMuPDF.
        If it has 0 pages, unreadable pages, or syntax stream corruption,
        writes a repaired version to output_dir via pypdfium2 rewrite.
        """
        if cls.check_pdf_health(pdf_path):
            return pdf_path

        repaired_file = output_dir / f"repaired_{pdf_path.name}"

        # 1. Try pypdfium2 rewrite (Standardizes page tree and cleans corrupted streams)
        try:
            import pypdfium2 as pdfium
            pdfium_doc = pdfium.PdfDocument(str(pdf_path))
            try:
                if len(pdfium_doc) > 0:
                    with open(repaired_file, "wb") as f:
                        pdfium_doc.save(f)
                    if cls.check_pdf_health(repaired_file):
                        return repaired_file
            finally:
                pdfium_doc.close()
        except Exception:
            pass

        # 2. Try slice from last valid %PDF- header (for concatenated/appended PDFs)
        try:
            data = pdf_path.read_bytes()
            import re
            pdf_starts = [m.start() for m in re.finditer(b"%PDF-", data)]
            if len(pdf_starts) > 1:
                for offset in reversed(pdf_starts):
                    try:
                        sub_data = data[offset:]
                        check_doc = pymupdf.open(stream=sub_data, filetype="pdf")
                        if check_doc.page_count > 0:
                            check_doc.close()
                            repaired_file.write_bytes(sub_data)
                            if cls.check_pdf_health(repaired_file):
                                return repaired_file
                        check_doc.close()
                    except Exception:
                        continue
        except Exception:
            pass

        # If repaired_file was created and has non-zero size, use it
        if repaired_file.exists() and repaired_file.stat().st_size > 0:
            return repaired_file

        return pdf_path

    @staticmethod
    def strip_watermark(text: str) -> str:
        """
        Strips common security watermarks (VNPT email, user id, and export timestamps)
        to evaluate the true character density of the underlying document.
        """
        if not text:
            return ""
        # Match email + optional date/timestamp format: user@domain_HH:MM DD/MM/YYYY
        import re
        cleaned = re.sub(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+(?:\.[a-zA-Z0-9-]+)*(?:[_\s]*\d{1,2}:\d{2}(?:\s+\d{1,2}/\d{1,2}/\d{2,4})?)?",
            "",
            text,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(r"\b\d{1,2}:\d{2}\s+\d{1,2}/\d{1,2}/\d{2,4}\b", "", cleaned)
        cleaned = re.sub(r"hoangnc@vnpt\.vn[^\n]*", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @classmethod
    def inspect_pdf_pages(cls, pdf_path: Path) -> List[Tuple[int, str, bool]]:
        """
        Inspects each page of the PDF to extract text layer and determine
        whether local OCR is needed based on character density and scan detection.

        Returns:
            List of tuples: (page_number_1_based, text_layer, needs_ocr)
        """
        try:
            doc = cls.open_pdf(pdf_path)
            try:
                if doc.page_count == 0:
                    raise ValueError(f"Tệp PDF '{pdf_path.name}' không chứa trang nào.")

                results: List[Tuple[int, str, bool]] = []
                for idx in range(len(doc)):
                    page_num = idx + 1
                    page = doc.load_page(idx)
                    
                    # Extract raw text layer
                    text = page.get_text("text").strip()
                    meaningful_text = cls.strip_watermark(text)
                    clean_chars = len("".join(meaningful_text.split()))

                    # Check if page is predominantly a scanned image
                    page_rect = page.rect
                    page_area = page_rect.width * page_rect.height if page_rect else 1.0
                    images = page.get_images(full=True)
                    
                    is_scanned_image = False
                    if images and page_area > 0:
                        for img in images:
                            try:
                                bbox = page.get_image_bbox(img)
                                if bbox:
                                    img_area = (bbox.x1 - bbox.x0) * (bbox.y1 - bbox.y0)
                                    if img_area / page_area > 0.60:
                                        is_scanned_image = True
                                        break
                            except Exception:
                                is_scanned_image = True
                                break

                    if is_scanned_image:
                        import re
                        viet_chars = len(re.findall(r'[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵĐ]', meaningful_text, re.IGNORECASE))
                        alpha_chars = len(re.findall(r'[a-zA-ZàáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵĐ]', meaningful_text))
                        has_corrupt_layer = (alpha_chars > 20 and (viet_chars / alpha_chars) < 0.05)
                        needs_ocr = (clean_chars < settings.MIN_DENSITY_CHARS_PER_PAGE) or has_corrupt_layer or (clean_chars == 0)
                    else:
                        needs_ocr = (clean_chars < settings.MIN_DENSITY_CHARS_PER_PAGE)

                    results.append((page_num, text, needs_ocr))
                return results
            finally:
                doc.close()
        except Exception:
            # Fallback to inspecting via pypdfium2 if PyMuPDF encounters unhandled page errors
            import pypdfium2 as pdfium
            pdfium_doc = pdfium.PdfDocument(str(pdf_path))
            try:
                total_pages = len(pdfium_doc)
                if total_pages == 0:
                    raise ValueError(f"Tệp PDF '{pdf_path.name}' không chứa trang nào.")
                
                pdfium_results: List[Tuple[int, str, bool]] = []
                for idx in range(total_pages):
                    page_num = idx + 1
                    page = pdfium_doc.get_page(idx)
                    try:
                        textpage = page.get_textpage()
                        text = textpage.get_text_range().strip()
                    except Exception:
                        text = ""
                    finally:
                        page.close()
                    
                    meaningful_text = cls.strip_watermark(text)
                    clean_chars = len("".join(meaningful_text.split()))

                    import re
                    viet_chars = len(re.findall(r'[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵĐ]', meaningful_text, re.IGNORECASE))
                    alpha_chars = len(re.findall(r'[a-zA-ZàáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵĐ]', meaningful_text))
                    has_corrupt_layer = (alpha_chars > 20 and (viet_chars / alpha_chars) < 0.05)

                    needs_ocr = (clean_chars < settings.MIN_DENSITY_CHARS_PER_PAGE) or has_corrupt_layer or (clean_chars == 0)
                    pdfium_results.append((page_num, text, needs_ocr))
                return pdfium_results
            finally:
                pdfium_doc.close()

    @classmethod
    def rasterize_page(cls, pdf_path: Path, page_number: int, dpi: int = 200) -> Image.Image:
        """
        Renders a specific PDF page (1-based) to a PIL Image at specified DPI.
        Uses PyMuPDF first, but falls back seamlessly to pypdfium2 if PyMuPDF
        fails or produces an empty/all-white image on a page with content.
        """
        try:
            doc = cls.open_pdf(pdf_path)
            try:
                page_index = page_number - 1
                if page_index < 0 or page_index >= len(doc):
                    raise ValueError(f"Page number {page_number} out of range (1..{len(doc)})")
                
                page = doc.load_page(page_index)
                pix = page.get_pixmap(dpi=dpi)
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                # Check if rendered image is abnormally blank/all-white
                # when page actually contains images or objects
                if page.get_images():
                    import numpy as np
                    arr = np.array(img.convert("L"))
                    if arr.min() >= 254:
                        # Blank image detected due to MuPDF rendering glitch -> Fallback to pypdfium2
                        raise ValueError("PyMuPDF rendered blank page on scanned content")

                return img
            finally:
                doc.close()
        except Exception:
            # Fallback to pypdfium2 rendering
            import pypdfium2 as pdfium
            pdfium_doc = pdfium.PdfDocument(str(pdf_path))
            try:
                page_index = page_number - 1
                if page_index < 0 or page_index >= len(pdfium_doc):
                    raise ValueError(f"Page number {page_number} out of range (1..{len(pdfium_doc)})")
                page = pdfium_doc.get_page(page_index)
                scale = dpi / 72.0
                bitmap = page.render(scale=scale)
                img = bitmap.to_pil()
                page.close()
                return img
            finally:
                pdfium_doc.close()

density_checker = DensityChecker()
