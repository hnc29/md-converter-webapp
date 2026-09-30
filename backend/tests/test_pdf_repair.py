import io
import pytest
from pathlib import Path
import pymupdf
from app.pipeline.density_checker import density_checker
from app.pipeline.validator import validator
from app.models import DocumentMetadata

def test_validator_detects_empty_body_with_frontmatter():
    meta = DocumentMetadata(
        document_id="TEST-EMPTY",
        source_file="test.pdf",
        title="Test Document",
        document_type="QĐ",
        organization="VNPT",
        unit="",
        version="",
        document_status="",
        document_number="",
        issued_date="",
        effective_date="",
        supersedes="",
        superseded_by="",
        scope="",
        language="vi",
        conversion_date="2026-09-24",
        converter_version="1.0.0",
        source_sha256="a" * 64,
        page_count=1,
        source_text_char_count=0,
        markdown_text_char_count=0,
        text_retention_ratio=0.0
    )

    empty_body_md = """---
document_id: "TEST-EMPTY"
source_file: "test.pdf"
title: "Test Document"
document_type: "QĐ"
organization: "VNPT"
page_count: 1
source_text_char_count: 0
markdown_text_char_count: 0
text_retention_ratio: 0.0
---
"""
    val_result = validator.validate(empty_body_md, meta, is_paginated=True, is_ocr=True)
    assert not val_result.is_safe_for_ai
    assert val_result.status == "FAIL"
    assert any("không có nội dung" in e or "rỗng" in e for e in val_result.errors)

def test_density_checker_repairs_concatenated_pdf(tmp_path):
    # Create two valid 1-page PDFs
    doc1 = pymupdf.open()
    p1 = doc1.new_page()
    p1.insert_text((50, 50), "First PDF page text content here")
    b1 = doc1.tobytes()
    doc1.close()

    doc2 = pymupdf.open()
    p2 = doc2.new_page()
    p2.insert_text((50, 50), "Second PDF page text content here")
    b2 = doc2.tobytes()
    doc2.close()

    # Concatenate them naively like cat doc1.pdf doc2.pdf
    concat_file = tmp_path / "concatenated.pdf"
    concat_file.write_bytes(b1 + b2)

    # density_checker.open_pdf should handle it cleanly without crashing
    doc = density_checker.open_pdf(concat_file)
    assert doc.page_count >= 1
    doc.close()

    # ensure_valid_pdf should produce a valid PDF
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    valid_path = density_checker.ensure_valid_pdf(concat_file, out_dir)
    assert valid_path.exists()
    inspected = density_checker.inspect_pdf_pages(valid_path)
    assert len(inspected) >= 1
