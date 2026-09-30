import os
import subprocess
import threading
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
from PIL import Image
import pytesseract
from ..config import settings
from .vietnamese_processor import vietnamese_processor

class OCRAdapterError(Exception):
    """Raised when local OCR execution fails."""

class OCRAdapter:
    """
    Adapter Pattern for Local OCR.
    Provides isolated integration points for multiple OCR engines:
    - Tesseract OCR (Fast, lightweight, local binary)
    - PaddleOCR (Deep learning based, high accuracy for Vietnamese/English complex layouts)
    """

    def __init__(self):
        self.tesseract_bin = settings.resolve_tesseract_bin()
        pytesseract.pytesseract.tesseract_cmd = self.tesseract_bin
        self.tesseract_lang = settings.TESSERACT_LANG
        self.tesseract_psm = settings.TESSERACT_PSM
        self._paddle_instance = None
        self._paddle_lock = threading.Lock()

    def _get_paddle_ocr(self):
        """Lazy initializer for PaddleOCR engine."""
        if self._paddle_instance is None:
            with self._paddle_lock:
                if self._paddle_instance is None:
                    try:
                        from paddleocr import PaddleOCR
                        # PaddleOCR initialization without heavy unwarping for faster and distortion-free processing
                        self._paddle_instance = PaddleOCR(
                            use_doc_unwarping=False,
                            use_doc_orientation_classify=settings.PADDLEOCR_USE_ANGLE_CLS,
                            use_textline_orientation=True,
                            lang=settings.PADDLEOCR_LANG
                        )
                    except Exception as e:
                        raise OCRAdapterError(f"Không thể khởi tạo PaddleOCR: {str(e)}")
        return self._paddle_instance

    def _preprocess_image_for_tesseract(self, image: Image.Image) -> Image.Image:
        """
        Applies grayscale binarization and thresholding to strip faint gray watermarks
        and boost dark text character edges.
        """
        try:
            # Convert to grayscale
            gray = image.convert("L")
            np_gray = np.array(gray)
            
            # Apply thresholding: watermark is light gray (> 165), text is dark ink (< 150)
            # Thresholding at 165 cleanly removes watermark while preserving Vietnamese diacritics
            import cv2
            _, thresh = cv2.threshold(np_gray, 165, 255, cv2.THRESH_BINARY)
            return Image.fromarray(thresh)
        except Exception:
            return image

    def _auto_rotate_image(self, image: Image.Image) -> Image.Image:
        """
        Detects orientation of scanned documents (e.g. landscape tables scanned in portrait)
        and rotates the image upright to ensure high-accuracy OCR.
        """
        try:
            w, h = image.size
            if max(w, h) > 1500:
                scale = 1500.0 / max(w, h)
                osd_img = image.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
            else:
                osd_img = image

            osd = pytesseract.image_to_osd(osd_img, output_type=pytesseract.Output.DICT)
            rotate_angle = osd.get("rotate", 0)
            conf = osd.get("orientation_conf", 0)

            if rotate_angle and rotate_angle in (90, 180, 270) and conf >= 2.0:
                pil_angle = (360 - rotate_angle) % 360
                return image.rotate(pil_angle, expand=True)
        except Exception:
            pass
        return image

    def _perform_tesseract(self, image: Image.Image) -> Tuple[str, Optional[float]]:
        """Executes Tesseract OCR on a PIL Image."""
        try:
            image = self._auto_rotate_image(image)
            proc_img = self._preprocess_image_for_tesseract(image)
            oem = getattr(settings, "TESSERACT_OEM", 1)
            custom_config = f"--oem {oem} --psm {self.tesseract_psm}"

            # 1. Get detailed OCR data including confidence scores
            data = pytesseract.image_to_data(
                proc_img,
                lang=self.tesseract_lang,
                config=custom_config,
                output_type=pytesseract.Output.DICT,
                timeout=settings.TESSERACT_TIMEOUT_SECONDS
            )

            # Calculate average confidence for valid words
            confidences = []
            for i in range(len(data['text'])):
                word = data['text'][i].strip()
                conf = int(data['conf'][i])
                if word and conf >= 0:
                    confidences.append(conf)

            avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 1.0

            # 2. Get full transcribed text
            raw_text = pytesseract.image_to_string(
                proc_img,
                lang=self.tesseract_lang,
                config=custom_config,
                timeout=settings.TESSERACT_TIMEOUT_SECONDS
            )

            # 3. Post-process Vietnamese text and strip watermark/stamps
            cleaned_text = vietnamese_processor.process_text(raw_text)

            return cleaned_text.strip(), round(avg_conf, 2)

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
            raise OCRAdapterError(f"Tesseract OCR processing error: {str(e)}")

    def _perform_paddleocr(self, image: Image.Image) -> Tuple[str, Optional[float]]:
        """Executes PaddleOCR on a PIL Image with spatial reading-order sorting."""
        try:
            paddle_engine = self._get_paddle_ocr()
            # Convert PIL image to RGB numpy array
            rgb_image = image.convert("RGB")
            img_np = np.array(rgb_image)

            # Use predict in 3.x if available, otherwise fallback to ocr
            if hasattr(paddle_engine, "predict"):
                result = paddle_engine.predict(img_np)
            else:
                result = paddle_engine.ocr(img_np)

            if not result:
                return "", 1.0

            line_items = []

            # 1. Handle PaddleOCR 3.x / PaddleX dictionary output
            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                for page_dict in result:
                    rec_texts = page_dict.get("rec_texts", [])
                    rec_scores = page_dict.get("rec_scores", [])
                    rec_boxes = page_dict.get("rec_boxes", [])

                    for i, (txt, score) in enumerate(zip(rec_texts, rec_scores)):
                        clean_txt = str(txt).strip()
                        if not clean_txt:
                            continue
                        
                        y_pos = 0
                        x_pos = 0
                        if i < len(rec_boxes):
                            box = rec_boxes[i]
                            if len(box) >= 4:
                                x_pos = float(box[0])
                                y_pos = float(box[1])

                        line_items.append((y_pos, x_pos, clean_txt, float(score)))

            # 2. Handle PaddleOCR 2.x list of tuples output
            elif isinstance(result, list) and len(result) > 0:
                first_elem = result[0]
                if isinstance(first_elem, list):
                    for line in first_elem:
                        if not line or len(line) < 2:
                            continue
                        box = line[0]
                        text_info = line[1]
                        if isinstance(text_info, (tuple, list)) and len(text_info) >= 2:
                            txt = str(text_info[0]).strip()
                            conf = float(text_info[1])
                            y_pos = float(box[0][1]) if box and len(box) > 0 else 0
                            x_pos = float(box[0][0]) if box and len(box) > 0 else 0
                            if txt:
                                line_items.append((y_pos, x_pos, txt, conf))

            if not line_items:
                return "", 1.0

            # Sort items by vertical position with 12px line tolerance, then horizontal position
            line_items.sort(key=lambda item: (round(item[0] / 14) * 14, item[1]))

            lines = [item[2] for item in line_items]
            confidences = [item[3] for item in line_items]

            extracted_text = "\n".join(lines).strip()
            extracted_text = vietnamese_processor.process_text(extracted_text)
            avg_conf = (sum(confidences) / len(confidences)) if confidences else 1.0

            return extracted_text.strip(), round(avg_conf, 2)

        except OCRAdapterError:
            raise
        except Exception as e:
            raise OCRAdapterError(f"PaddleOCR processing error: {str(e)}")

    def perform_ocr(self, image_input: Image.Image | Path, engine: str = "tesseract") -> Tuple[str, Optional[float]]:
        """
        Executes local OCR on the given PIL Image or image file path using specified engine.
        
        Args:
            image_input: PIL Image or Path to image
            engine: 'tesseract' or 'paddleocr' (defaults to 'tesseract')
            
        Returns:
            Tuple[extracted_text, average_confidence_score (0.0 - 1.0)]
        """
        try:
            image = image_input if isinstance(image_input, Image.Image) else Image.open(image_input)
            
            normalized_engine = (engine or "tesseract").lower().strip()
            if normalized_engine in ("paddle", "paddleocr"):
                return self._perform_paddleocr(image)
            else:
                return self._perform_tesseract(image)
        except OCRAdapterError:
            raise
        except Exception as e:
            raise OCRAdapterError(f"Local OCR processing error ({engine}): {str(e)}")

ocr_adapter = OCRAdapter()

