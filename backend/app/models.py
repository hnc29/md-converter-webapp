from typing import List, Optional
from pydantic import BaseModel, Field

class PageResult(BaseModel):
    page_number: int
    text: str
    is_ocr: bool = False
    confidence: Optional[float] = None
    char_count: int = 0

class ConvertResponse(BaseModel):
    filename: str
    converted_via_legacy: bool = False
    markdown: str
    pages_total: int = 1
    pages_ocr: List[int] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    duration_ms: int = 0
    word_count: int = 0
    character_count: int = 0

class HealthResponse(BaseModel):
    status: str
    version: str
    libreoffice_available: bool
    tesseract_available: bool
    density_threshold: int
