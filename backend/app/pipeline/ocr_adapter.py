import os
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
import pytesseract
from ..config import settings

class OCRAdapterError(Exception):
    """Raised when local OCR execution fails."""

class OCRAdapter:
    """
    Adapter Pattern for Local OCR.
    Isolated single integration point for local OCR capabilities (Tesseract / Marker).
    """

    def __init__(self):
        self.tesseract_bin = settings.resolve_tesseract_bin()
        pytesseract.pytesseract.tesseract_cmd = self.tesseract_bin
        self.lang = settings.TESSERACT_LANG
        self.psm = settings.TESSERACT_PSM

    def perform_ocr(self, image_input: Image.Image | Path) -> Tuple[str, Optional[float]]:
        """
        Executes local OCR on the given PIL Image or image file path.
        
        Returns:
            Tuple[extracted_text, average_confidence_score (0.0 - 1.0)]
        """
        try:
            image = image_input if isinstance(image_input, Image.Image) else Image.open(image_input)
            
            # Custom Tesseract configuration
            custom_config = f"--psm {self.psm}"

            # 1. Get detailed OCR data including confidence scores
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                config=custom_config,
                output_type=pytesseract.Output.DICT,
                timeout=settings.TESSERACT_TIMEOUT_SECONDS
            )

            # Calculate average confidence for valid words
            confidences = []
            words = []
            for i in range(len(data['text'])):
                word = data['text'][i].strip()
                conf = int(data['conf'][i])
                if word and conf >= 0:
                    words.append(word)
                    confidences.append(conf)

            avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 1.0

            # 2. Get full transcribed text
            text = pytesseract.image_to_string(
                image,
                lang=self.lang,
                config=custom_config,
                timeout=settings.TESSERACT_TIMEOUT_SECONDS
            )

            return text.strip(), round(avg_conf, 2)

        except pytesseract.TesseractNotFoundError:
            raise OCRAdapterError(
                f"Tesseract binary not found at '{self.tesseract_bin}'. "
                "Please verify Tesseract installation."
            )
        except subprocess.TimeoutExpired:
            raise OCRAdapterError(
                f"Tesseract OCR timed out after {settings.TESSERACT_TIMEOUT_SECONDS}s."
            )
        except Exception as e:
            raise OCRAdapterError(f"Local OCR processing error: {str(e)}")

ocr_adapter = OCRAdapter()
