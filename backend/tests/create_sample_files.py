import io
from pathlib import Path
from docx import Document
import openpyxl
import pymupdf
from PIL import Image, ImageDraw, ImageFont

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

def create_sample_docx():
    doc_path = FIXTURES_DIR / "sample_table.docx"
    doc = Document()
    doc.add_heading("Bao Cao Du An Doc2MD", level=1)
    doc.add_paragraph("Day la tai lieu Word thu nghiem chuyen doi sang Markdown voi MarkItDown.")
    
    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Ma Module'
    hdr_cells[1].text = 'Ten Module'
    hdr_cells[2].text = 'Trang Thai'

    items = [
        ('M01', 'Legacy Converter', 'Completed'),
        ('M02', 'MarkItDown Core', 'Completed'),
        ('M03', 'Local OCR Adapter', 'Completed')
    ]
    for m_id, name, status in items:
        row_cells = table.add_row().cells
        row_cells[0].text = m_id
        row_cells[1].text = name
        row_cells[2].text = status

    doc.save(doc_path)
    return doc_path

def create_sample_xlsx():
    xlsx_path = FIXTURES_DIR / "sample_multisheet.xlsx"
    wb = openpyxl.Workbook()
    
    # Sheet 1
    ws1 = wb.active
    ws1.title = "NhanSu"
    ws1.append(["ID", "Ho va Ten", "Phong Ban", "Chuc Vu"])
    ws1.append(["NS01", "Nguyen Van A", "Ky Thuat", "Tech Lead"])
    ws1.append(["NS02", "Tran Thi B", "San Pham", "Product Manager"])

    # Sheet 2
    ws2 = wb.create_sheet(title="DoanhThu")
    ws2.append(["Thang", "Doanh Thu", "Tang Truong"])
    ws2.append(["Thang 1", "150000000", "+12%"])
    ws2.append(["Thang 2", "185000000", "+23%"])

    wb.save(xlsx_path)
    return xlsx_path

def create_sample_digital_pdf():
    pdf_path = FIXTURES_DIR / "sample_digital.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842) # A4
    text = (
        "CONG HOA XA HOI CHU NGHIA VIET NAM\n"
        "Doc lap - Tu do - Hanh phuc\n\n"
        "BAO CAO KET QUA TRIEN KHAI HE THONG DOC2MD CONVERTER\n\n"
        "Tai lieu nay chua text layer so ro rang va day du.\n"
        "He thong se trich xuat truc tiep text layer ma khong can kich hoat OCR cuc bo.\n"
        "Kiem tra mat do ky tu tren trang dam bao tren nguong toi thieu 50 ky tu."
    )
    page.insert_text((50, 72), text, fontsize=11)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path

def create_sample_scanned_pdf():
    """Creates a PDF containing purely an image rendered from text with NO text layer."""
    pdf_path = FIXTURES_DIR / "sample_scanned.pdf"
    
    # Render an image with text using Pillow
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "TAI LIEU SCAN QUET ANH (OCR REQUIRED)", fill=(0, 0, 0))
    draw.text((50, 100), "Doc2MD Local Tesseract OCR Test Page", fill=(0, 0, 0))
    draw.text((50, 150), "Nguyen Van A - Phong Nghien Cuu AI", fill=(0, 0, 0))

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    rect = pymupdf.Rect(50, 50, 545, 420)
    page.insert_image(rect, stream=img_bytes.getvalue())
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path

def create_sample_mixed_pdf():
    """Page 1: Digital text (well above threshold), Page 2: Scanned image."""
    pdf_path = FIXTURES_DIR / "sample_mixed.pdf"
    doc = pymupdf.open()

    # Page 1: Digital
    p1 = doc.new_page(width=595, height=842)
    long_text = (
        "Trang 1: Day la van ban so co Text Layer day du va ro net.\n"
        "He thong tu dong phan tich mat do ky tu tren trang nay va xac dinh chat luong tot.\n"
        "Trang nay se duoc giu nguyen text layer va khong can qua OCR local."
    )
    p1.insert_text((50, 72), long_text, fontsize=12)

    # Page 2: Scanned Image
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Trang 2: Noi dung anh scan can chay qua OCR Local", fill=(0, 0, 0))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")

    p2 = doc.new_page(width=595, height=842)
    rect = pymupdf.Rect(50, 50, 545, 420)
    p2.insert_image(rect, stream=img_bytes.getvalue())

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path

def create_sample_doc():
    doc_path = FIXTURES_DIR / "sample_legacy.doc"
    import subprocess
    txt_path = FIXTURES_DIR / "temp_sample.txt"
    txt_path.write_text("Tai lieu Word cu dinh dang DOC thu nghiem chuyen doi Markdown.")
    subprocess.run(["textutil", "-convert", "doc", "-output", str(doc_path), str(txt_path)], check=True)
    if txt_path.exists():
        txt_path.unlink()
    return doc_path

def create_sample_xls():
    xls_path = FIXTURES_DIR / "sample_legacy.xls"
    import xlwt
    wb = xlwt.Workbook()
    ws1 = wb.add_sheet("BangGia")
    ws1.write(0, 0, "San Pham")
    ws1.write(0, 1, "Gia Ban")
    ws1.write(1, 0, "Goi Cuoc 4G")
    ws1.write(1, 1, "120000")
    wb.save(str(xls_path))
    return xls_path

if __name__ == "__main__":
    print("Generating sample fixtures...")
    print("DOCX:", create_sample_docx())
    print("XLSX:", create_sample_xlsx())
    print("DOC:", create_sample_doc())
    print("XLS:", create_sample_xls())
    print("PDF Digital:", create_sample_digital_pdf())
    print("PDF Scanned:", create_sample_scanned_pdf())
    print("PDF Mixed:", create_sample_mixed_pdf())
    print("Done!")
