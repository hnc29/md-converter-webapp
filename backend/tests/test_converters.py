import pytest
import io
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from tests.create_sample_files import (
    create_sample_docx,
    create_sample_xlsx,
    create_sample_doc,
    create_sample_xls,
    create_sample_digital_pdf,
    create_sample_scanned_pdf,
    create_sample_mixed_pdf,
)

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_sample_files():
    create_sample_docx()
    create_sample_xlsx()
    create_sample_doc()
    create_sample_xls()
    create_sample_digital_pdf()
    create_sample_scanned_pdf()
    create_sample_mixed_pdf()

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "tesseract_available" in data

def test_convert_docx_with_tables():
    fixtures_dir = Path(__file__).parent / "fixtures"
    docx_path = fixtures_dir / "sample_table.docx"
    
    with open(docx_path, "rb") as f:
        response = client.post(
            "/api/convert",
            files={"file": ("sample_table.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "Bao Cao Du An Doc2MD" in data["markdown"]
    assert "Legacy Converter" in data["markdown"]
    assert data["pages_ocr"] == []

def test_convert_legacy_doc():
    fixtures_dir = Path(__file__).parent / "fixtures"
    doc_path = fixtures_dir / "sample_legacy.doc"

    with open(doc_path, "rb") as f:
        response = client.post(
            "/api/convert",
            files={"file": ("sample_legacy.doc", f, "application/msword")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "Tai lieu Word cu dinh dang DOC" in data["markdown"]
    assert data["pages_ocr"] == []

def test_convert_legacy_xls():
    fixtures_dir = Path(__file__).parent / "fixtures"
    xls_path = fixtures_dir / "sample_legacy.xls"

    with open(xls_path, "rb") as f:
        response = client.post(
            "/api/convert",
            files={"file": ("sample_legacy.xls", f, "application/vnd.ms-excel")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "BangGia" in data["markdown"] or "Goi Cuoc 4G" in data["markdown"]
    assert data["pages_ocr"] == []

def test_convert_xlsx_multisheet():
    fixtures_dir = Path(__file__).parent / "fixtures"
    xlsx_path = fixtures_dir / "sample_multisheet.xlsx"

    with open(xlsx_path, "rb") as f:
        response = client.post(
            "/api/convert",
            files={"file": ("sample_multisheet.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "NhanSu" in data["markdown"] or "Nguyen Van A" in data["markdown"]
    assert data["pages_ocr"] == []

def test_convert_digital_pdf():
    fixtures_dir = Path(__file__).parent / "fixtures"
    pdf_path = fixtures_dir / "sample_digital.pdf"

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/convert",
            files={"file": ("sample_digital.pdf", f, "application/pdf")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "CONG HOA XA HOI CHU NGHIA VIET NAM" in data["markdown"]
    assert data["pages_total"] == 1
    assert data["pages_ocr"] == []

def test_convert_scanned_pdf_triggers_ocr():
    fixtures_dir = Path(__file__).parent / "fixtures"
    pdf_path = fixtures_dir / "sample_scanned.pdf"

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/convert",
            files={"file": ("sample_scanned.pdf", f, "application/pdf")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["pages_total"] == 1
    assert 1 in data["pages_ocr"]
    assert "SCAN" in data["markdown"].upper() or "OCR" in data["markdown"].upper()

def test_convert_batch_multiple_files():
    fixtures_dir = Path(__file__).parent / "fixtures"
    docx_path = fixtures_dir / "sample_table.docx"
    xlsx_path = fixtures_dir / "sample_multisheet.xlsx"
    pdf_path = fixtures_dir / "sample_digital.pdf"

    with open(docx_path, "rb") as f1, open(xlsx_path, "rb") as f2, open(pdf_path, "rb") as f3:
        files = [
            ("files", ("sample_table.docx", f1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("sample_multisheet.xlsx", f2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
            ("files", ("sample_digital.pdf", f3, "application/pdf"))
        ]
        response = client.post("/api/convert-batch", files=files)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["filename"] == "sample_table.docx"
    assert data[1]["filename"] == "sample_multisheet.xlsx"
    assert data[2]["filename"] == "sample_digital.pdf"

def test_convert_batch_zip():
    fixtures_dir = Path(__file__).parent / "fixtures"
    docx_path = fixtures_dir / "sample_table.docx"
    xlsx_path = fixtures_dir / "sample_multisheet.xlsx"

    with open(docx_path, "rb") as f1, open(xlsx_path, "rb") as f2:
        files = [
            ("files", ("sample_table.docx", f1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("sample_multisheet.xlsx", f2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        ]
        response = client.post("/api/convert-batch/zip", files=files)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    
    # Verify zip content
    zip_bytes = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "sample_table.md" in namelist
        assert "sample_multisheet.md" in namelist
