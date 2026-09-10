import pytest
import io
import json
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from tests.create_sample_files import setup_all_fixtures, FIXTURES_DIR

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def init_fixtures():
    setup_all_fixtures()

def test_knowledge_base_conversion_bundle():
    """Tests the full batch Knowledge Base conversion API."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    lld_path = FIXTURES_DIR / "04.IMS_LLD.docx"
    excel_path = FIXTURES_DIR / "IMS_TEST_REPORT_PhiChucNang.xlsx"

    with open(hld_path, "rb") as f1, open(lld_path, "rb") as f2, open(excel_path, "rb") as f3:
        files = [
            ("files", ("03.IMS_HLD.docx", f1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("04.IMS_LLD.docx", f2, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("IMS_TEST_REPORT_PhiChucNang.xlsx", f3, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        ]
        response = client.post("/api/convert-knowledge-base", files=files)

    assert response.status_code == 200
    data = response.json()

    # 1. Verify Structure
    assert data["total_documents"] == 3
    assert "master_index_md" in data
    assert "manifest_json" in data
    assert "conversion_report_md" in data

    # 2. Verify 00_Master_Index.md
    master_index = data["master_index_md"]
    assert "# MASTER INDEX" in master_index
    assert "IMS-HLD" in master_index
    assert "03.IMS_HLD.docx" in master_index
    assert "Quản lý kế hoạch vốn" in master_index
    assert "Kiến trúc tích hợp" in master_index

    # 3. Verify manifest.json
    manifest = data["manifest_json"]
    assert manifest["schema_version"] == "1.0"
    assert len(manifest["documents"]) == 3
    hld_doc = next(d for d in manifest["documents"] if d["source_file"] == "03.IMS_HLD.docx")
    assert hld_doc["document_id"] == "IMS-HLD"
    assert hld_doc["sha256"] != ""
    assert any("kế hoạch vốn" in s["heading"].lower() for s in hld_doc["sections"])

    # 4. Verify conversion_report.md
    report = data["conversion_report_md"]
    assert "CONVERSION QUALITY REPORT" in report
    assert "03.IMS_HLD.docx" in report

def test_acceptance_test_case_1_function_search():
    """Test Case 1: Hỏi 'IMS có chức năng quản lý kế hoạch vốn không?'"""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    with open(hld_path, "rb") as f:
        res = client.post("/api/convert", files={"file": ("03.IMS_HLD.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res.status_code == 200
    data = res.json()
    md = data["markdown"]

    # Must contain section 3.3 and keyword
    assert "Quản lý kế hoạch vốn" in md
    assert "<a id=\"sec-3-3-quan-ly-ke-hoach-von\"></a>" in md or "sec-3-3" in md
    assert "vốn đầu tư trung hạn và hàng năm" in md

def test_acceptance_test_case_2_document_comparison():
    """Test Case 2: HLD IMS mô tả kiến trúc tích hợp như thế nào?"""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    with open(hld_path, "rb") as f:
        res = client.post("/api/convert", files={"file": ("03.IMS_HLD.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res.status_code == 200
    md = res.json()["markdown"]

    assert "Kiến trúc tích hợp" in md
    assert "Enterprise Service Bus" in md or "ESB" in md

def test_acceptance_test_case_3_traceability():
    """Test Case 3: Truy vết nguồn & Marker trang."""
    pdf_path = FIXTURES_DIR / "sample_digital.pdf"
    with open(pdf_path, "rb") as f:
        res = client.post("/api/convert", files={"file": ("sample_digital.pdf", f, "application/pdf")})
    assert res.status_code == 200
    data = res.json()
    md = data["markdown"]

    # Must contain page marker
    assert "<!-- source_page: 1 -->" in md or "<!-- Page 1" in md
    assert data["metadata"]["source_sha256"] != ""

def test_acceptance_test_case_4_version_metadata():
    """Test Case 4: Quản lý phiên bản & không bịa đặt metadata."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    with open(hld_path, "rb") as f:
        res = client.post("/api/convert", files={"file": ("03.IMS_HLD.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res.status_code == 200
    meta = res.json()["metadata"]

    assert meta["version"] == "1.0"
    assert meta["document_status"] == "Đã ban hành"
    assert meta["issued_date"] == "26/08/2026"
    assert meta["organization"] == "VNPT"

def test_acceptance_test_case_5_searchable_tables():
    """Test Case 5: Bảng có thể tìm kiếm theo giá trị ô (cell text)."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    with open(hld_path, "rb") as f:
        res = client.post("/api/convert", files={"file": ("03.IMS_HLD.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res.status_code == 200
    md = res.json()["markdown"]

    # Verify table structure & cell contents
    assert "| STT | Chức năng |" in md or "| STT |" in md
    assert "Nghiệm thu quyết toán" in md
    assert "Ban QLDA" in md

def test_acceptance_test_case_6_excel_multi_sheet():
    """Test Case 6: Excel tìm kiếm testcase và chỉ tiêu hiệu năng theo Sheet."""
    excel_path = FIXTURES_DIR / "IMS_TEST_REPORT_PhiChucNang.xlsx"
    with open(excel_path, "rb") as f:
        res = client.post("/api/convert", files={"file": ("IMS_TEST_REPORT_PhiChucNang.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert res.status_code == 200
    md = res.json()["markdown"]

    assert "## Sheet: TongHop" in md
    assert "Kiem thu tai tong the" in md
    assert "## Sheet: Performance" in md
    assert "1250 TPS" in md
    assert "< 200ms" in md

def test_knowledge_base_zip_package():
    """Test Case: Tải toàn bộ gói Knowledge Base (.zip) với cấu trúc thư mục chuẩn."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    excel_path = FIXTURES_DIR / "IMS_TEST_REPORT_PhiChucNang.xlsx"

    with open(hld_path, "rb") as f1, open(excel_path, "rb") as f2:
        files = [
            ("files", ("03.IMS_HLD.docx", f1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("IMS_TEST_REPORT_PhiChucNang.xlsx", f2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        ]
        res = client.post("/api/convert-knowledge-base/zip", files=files)

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"

    # Inspect zip contents
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        names = zf.namelist()
        assert "00_Master_Index.md" in names
        assert "manifest.json" in names
        assert "conversion_report.md" in names
        assert "documents/03.IMS_HLD.md" in names
        assert "documents/IMS_TEST_REPORT_PhiChucNang.md" in names
        assert "source/03.IMS_HLD.docx" in names
