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
        whether local OCR is needed based on character density.

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
                
                # Calculate effective characters (excluding empty whitespace)
                clean_chars = len("".join(text.split()))

                needs_ocr = clean_chars < settings.MIN_DENSITY_CHARS_PER_PAGE
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
