import io
from pathlib import Path
from typing import List, Tuple
from PIL import Image
import pymupdf  # PyMuPDF / fitz
from ..config import settings
from ..models import PageResult

class DensityChecker:
    @staticmethod
    def inspect_pdf_pages(pdf_path: Path) -> List[Tuple[int, str, bool]]:
        """
        Inspects each page of the PDF to extract text layer and determine
        whether local OCR is needed based on character density and scan detection.

        Returns:
            List of tuples: (page_number_1_based, text_layer, needs_ocr)
        """
        doc = pymupdf.open(str(pdf_path))
        results: List[Tuple[int, str, bool]] = []

        try:
            for idx in range(len(doc)):
                page_num = idx + 1
                page = doc.load_page(idx)
                
                # Extract raw text layer
                text = page.get_text("text").strip()
                clean_chars = len("".join(text.split()))

                # Check if page is predominantly a scanned image
                page_rect = page.rect
                page_area = page_rect.width * page_rect.height if page_rect else 1.0
                images = page.get_images(full=True)
                
                is_scanned_image = False
                if images and page_area > 0:
                    for img in images:
                        xref = img[0]
                        try:
                            bbox = page.get_image_bbox(img)
                            if bbox:
                                img_area = (bbox.x1 - bbox.x0) * (bbox.y1 - bbox.y0)
                                if img_area / page_area > 0.60:
                                    is_scanned_image = True
                                    break
                        except Exception:
                            # Fallback check if full image is present on page
                            is_scanned_image = True
                            break

                # Evaluate text layer quality: check for Vietnamese diacritics / corrupt OCR signs
                has_corrupt_layer = False
                if clean_chars > 0 and is_scanned_image:
                    # Check ratio of standard Vietnamese diacritics in text vs total letters
                    import re
                    viet_chars = len(re.findall(r'[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵĐ]', text, re.IGNORECASE))
                    alpha_chars = len(re.findall(r'[a-zA-ZàáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵĐ]', text))
                    if alpha_chars > 30 and (viet_chars / alpha_chars) < 0.05:
                        has_corrupt_layer = True

                needs_ocr = (clean_chars < settings.MIN_DENSITY_CHARS_PER_PAGE) or (is_scanned_image and (has_corrupt_layer or clean_chars == 0))
                results.append((page_num, text, needs_ocr))
        finally:
            doc.close()

        return results

    @staticmethod
    def rasterize_page(pdf_path: Path, page_number: int, dpi: int = 200) -> Image.Image:
        """
        Renders a specific PDF page (1-based) to a PIL Image at specified DPI.
        """
        doc = pymupdf.open(str(pdf_path))
        try:
            page_index = page_number - 1
            if page_index < 0 or page_index >= len(doc):
                raise ValueError(f"Page number {page_number} out of range (1..{len(doc)})")
            
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            return img
        finally:
            doc.close()

density_checker = DensityChecker()
