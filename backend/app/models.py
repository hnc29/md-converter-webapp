from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class PageResult(BaseModel):
    page_number: int
    text: str
    is_ocr: bool = False
    confidence: Optional[float] = None
    char_count: int = 0

class SectionInfo(BaseModel):
    id: str
    heading: str
    level: int
    source_page_start: Optional[int] = None
    source_page_end: Optional[int] = None

class DocumentMetadata(BaseModel):
    document_id: str
    source_file: str
    title: str = ""
    document_type: str = ""
    organization: str = "VNPT"
    unit: str = ""
    version: str = ""
    document_status: str = ""
    document_number: str = ""
    issued_date: str = ""
    effective_date: str = ""
    supersedes: str = ""
    superseded_by: str = ""
    scope: str = ""
    language: str = "vi"
    conversion_date: str = ""
    converter_version: str = "2.0.0"
    source_sha256: str = ""
    page_count: int = 1
    source_text_char_count: int = 0
    markdown_text_char_count: int = 0
    text_retention_ratio: float = 1.0

class ValidationCheck(BaseModel):
    name: str
    passed: bool
    message: str = ""

class ValidationResult(BaseModel):
    status: str = "PASS"  # PASS, WARNING, FAIL
    is_safe_for_ai: bool = True  # True if passes quality gate, False if failed/quarantine
    checks: List[ValidationCheck] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

class ConvertResponse(BaseModel):
    filename: str
    document_id: str = ""
    converted_via_legacy: bool = False
    markdown: str
    metadata: Optional[DocumentMetadata] = None
    sections: List[SectionInfo] = Field(default_factory=list)
    validation: Optional[ValidationResult] = None
    pages_total: int = 1
    pages_ocr: List[int] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    duration_ms: int = 0
    word_count: int = 0
    character_count: int = 0
    source_sha256: str = ""

class KnowledgeBaseResponse(BaseModel):
    is_single_mode: bool = False
    master_index_md: str = ""
    manifest_json: Dict[str, Any]
    conversion_report_md: str
    readme_txt: str = ""
    upload_to_ai_documents: List[ConvertResponse] = Field(default_factory=list)
    failed_documents: List[ConvertResponse] = Field(default_factory=list)
    total_documents: int = 0
    ready_count: int = 0
    warning_count: int = 0
    failed_count: int = 0
    overall_status: str = "PASS"
    documents: List[ConvertResponse] = Field(default_factory=list)

class HealthResponse(BaseModel):
    status: str
    version: str
    libreoffice_available: bool
    tesseract_available: bool
    density_threshold: int
