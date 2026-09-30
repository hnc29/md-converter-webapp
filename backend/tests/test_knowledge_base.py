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

def test_single_document_mode():
    """Tests Single Document Mode (1 file input): NO 00_Master_Index.md, direct upload_to_ai."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    with open(hld_path, "rb") as f:
        files = [("files", ("03.IMS_HLD.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
        res = client.post("/api/convert-knowledge-base", files=files)

    assert res.status_code == 200
    data = res.json()
    assert data["is_single_mode"] is True
    assert data["master_index_md"] == ""
    assert data["ready_count"] == 1
    assert len(data["upload_to_ai_documents"]) == 1
    assert "Single Document Mode" in data["readme_txt"]

def test_single_document_zip_layout():
    """Tests ZIP packaging for Single Document Mode."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    with open(hld_path, "rb") as f:
        files = [("files", ("03.IMS_HLD.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
        res = client.post("/api/convert-knowledge-base/zip", files=files)

    assert res.status_code == 200
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        names = zf.namelist()
        assert "upload_to_ai/03.IMS_HLD.md" in names
        assert "upload_to_ai/00_Master_Index.md" not in names  # MUST NOT generate Master Index for single doc
        assert "technical/manifest.json" in names
        assert "technical/conversion_report.md" in names
        assert "source/03.IMS_HLD.docx" in names
        assert "README.txt" in names

def test_knowledge_pack_mode_multi_files():
    """Tests Knowledge Pack Mode (>= 2 files input): WITH 00_Master_Index.md."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    lld_path = FIXTURES_DIR / "04.IMS_LLD.docx"
    excel_path = FIXTURES_DIR / "IMS_TEST_REPORT_PhiChucNang.xlsx"

    with open(hld_path, "rb") as f1, open(lld_path, "rb") as f2, open(excel_path, "rb") as f3:
        files = [
            ("files", ("03.IMS_HLD.docx", f1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("04.IMS_LLD.docx", f2, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("IMS_TEST_REPORT_PhiChucNang.xlsx", f3, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
        ]
        res = client.post("/api/convert-knowledge-base", files=files)

    assert res.status_code == 200
    data = res.json()
    assert data["is_single_mode"] is False
    assert data["master_index_md"] != ""
    assert "# MASTER INDEX" in data["master_index_md"]
    assert data["ready_count"] == 3
    assert len(data["upload_to_ai_documents"]) == 3
    assert "Knowledge Pack" in data["readme_txt"]

def test_knowledge_pack_zip_layout():
    """Tests ZIP packaging for Knowledge Pack Mode."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    lld_path = FIXTURES_DIR / "04.IMS_LLD.docx"

    with open(hld_path, "rb") as f1, open(lld_path, "rb") as f2:
        files = [
            ("files", ("03.IMS_HLD.docx", f1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("04.IMS_LLD.docx", f2, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        ]
        res = client.post("/api/convert-knowledge-base/zip", files=files)

    assert res.status_code == 200
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        names = zf.namelist()
        assert "upload_to_ai/00_Master_Index.md" in names
        assert "upload_to_ai/03.IMS_HLD.md" in names
        assert "upload_to_ai/04.IMS_LLD.md" in names
        assert "technical/manifest.json" in names
        assert "technical/conversion_report.md" in names
        assert "source/03.IMS_HLD.docx" in names
        assert "source/04.IMS_LLD.docx" in names
        assert "README.txt" in names

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
    assert "sec-3-3" in md
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

    assert "| STT |" in md
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

def test_streaming_batch_ocr_progress():
    """Tests the SSE streaming batch OCR progress endpoint."""
    hld_path = FIXTURES_DIR / "03.IMS_HLD.docx"
    lld_path = FIXTURES_DIR / "04.IMS_LLD.docx"

    with open(hld_path, "rb") as f1, open(lld_path, "rb") as f2:
        files = [
            ("files", ("03.IMS_HLD.docx", f1, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("04.IMS_LLD.docx", f2, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
        ]
        with client.stream("POST", "/api/convert-knowledge-base/stream", files=files) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            
            events = []
            for line in response.iter_lines():
                if line and line.startswith("data: "):
                    payload = json.loads(line[6:])
                    events.append(payload)

    # Check progress progression
    types = [e.get("type") for e in events]
    assert "init" in types
    assert "file_start" in types
    assert "file_done" in types
    assert "complete" in types

    # Check complete payload
    complete_event = next(e for e in events if e.get("type") == "complete")
    assert complete_event["completed_files"] == 2
    assert complete_event["remaining_files"] == 0
    assert complete_event["percent"] == 100
    assert "result" in complete_event
    assert complete_event["result"]["ready_count"] == 2

def test_vietnamese_administrative_metadata_and_cleaning():
    from app.pipeline.metadata_extractor import metadata_extractor
    from app.pipeline.vietnamese_processor import vietnamese_processor
    
    # 1. Test watermark stripping preserves legitimate text
    raw_ocr_line = "KT. TỔNG GIÁM ĐỐC hoangnc@vnpt.vn_00:04 27/09/2026\nPHÓ TỔNG GIÁM ĐỐC\nTô Mạnh Cường"
    cleaned = vietnamese_processor.clean_watermark_and_stray_artifacts(raw_ocr_line)
    assert "KT. TỔNG GIÁM ĐỐC" in cleaned
    assert "hoangnc@vnpt.vn" not in cleaned
    assert "Tô Mạnh Cường" in cleaned

    # 2. Test metadata extraction for Vietnamese legal decisions
    fn = "2016-12-21 2123-QĐ-VNPT-CNM Quy định tạm thời chỉ tiêu quản lý chất lượng mạng 4G-LTE của VNPT.PDF"
    sample_text = """TẬP ĐOÀN BƯU CHÍNH VIỄN THÔNG VIỆT NAM
Số: 2123 /QĐ-VNPT-CNM
Hà Nội, ngày 21 tháng 12 năm 2016

QUYẾT ĐỊNH
Về việc Ban hành “Quy định tạm thời chỉ tiêu quản lý chất lượng mạng 4G/LTE của VNPT”

TỔNG GIÁM ĐỐC
Căn cứ Quyết định số 06/2006/QĐ-TTg ngày 09/01/2006 của Thủ tướng Chính phủ;
Theo đề nghị của các Ông Trưởng Ban Công nghệ - Mạng,

QUYẾT ĐỊNH:
Điều 1. Ban hành “Quy định tạm thời chỉ tiêu quản lý chất lượng mạng 4G/LTE của VNPT” (kèm theo).
Điều 2. Quyết định này có hiệu lực thi hành kể từ ngày ký."""

    dummy_path = Path(__file__).parent / "fixtures" / "sample_digital.pdf"
    meta = metadata_extractor.build_metadata(
        filename=fn,
        source_path=dummy_path,
        raw_markdown=sample_text,
        source_text=sample_text,
        page_count=16
    )

    assert meta.document_number == "2123/QĐ-VNPT-CNM"
    assert meta.issued_date == "2016-12-21"
    assert meta.effective_date == "2016-12-21"
    assert meta.document_type == "QĐ"
    assert meta.unit == "Ban Công nghệ - Mạng"
    assert "Quy định tạm thời chỉ tiêu quản lý chất lượng" in meta.title
    
    # 3. Test front matter generation includes updated fields
    yaml_header = metadata_extractor.generate_yaml_front_matter(meta)
    assert 'document_number: "2123/QĐ-VNPT-CNM"' in yaml_header
    assert 'issued_date: "2016-12-21"' in yaml_header
    assert 'effective_date: "2016-12-21"' in yaml_header
    assert 'unit: "Ban Công nghệ - Mạng"' in yaml_header


