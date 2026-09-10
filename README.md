# MD Converter Webapp (MarkItDown + Local OCR Pipeline) 🚀

Ứng dụng Web chuyển đổi tài liệu **PDF, DOC/DOCX, XLS/XLSX** sang định dạng **Markdown** (.md) chuẩn, sử dụng **Microsoft MarkItDown** làm bộ chuyển đổi chính kết hợp hệ thống **OCR nội bộ (Local Tesseract & Marker Adapter)** cho tài liệu dạng quét ảnh/scan.

---

## 🌟 Tính Năng Nổi Bật

1. **Hỗ trợ định dạng văn bản & bảng biểu phong phú**:
   - Word (`.docx`, `.doc` - tự động chuyển đổi qua LibreOffice headless).
   - Excel (`.xlsx`, `.xls` - tự động chuyển đổi qua LibreOffice headless).
   - PDF (tự động nhận diện lớp văn bản và quét ảnh).
2. **Hệ thống OCR Nội bộ Thông minh (Adapter Pattern)**:
   - Đo mật độ ký tự/trang PDF tự động (`density_checker.py`).
   - Nếu mật độ < ngưỡng cấu hình (mặc định 50 ký tự/trang), hệ thống tự động rasterize trang và kích hoạt OCR qua `ocr_adapter.py`.
   - Sử dụng Tesseract OCR nội bộ (`vie+eng`), hoàn toàn không phụ thuộc dịch vụ Cloud.
3. **Giao diện Web Trực quan (UI/UX)**:
   - Kéo thả (Drag & Drop) tệp tải lên.
   - Hiển thị chi tiết metadata: số trang, trang nào đã chạy qua OCR, thời gian xử lý, cảnh báo.
   - Chia đôi màn hình (Split-View): Trình soạn thảo Markdown và Bản xem trước Rendered HTML.
   - Sao chép nhanh vào clipboard & Tải tệp `.md`.
   - Chuyển đổi Dark Mode / Light Mode mượt mà.
4. **Đóng gói chuẩn Docker**: Chuyển giao toàn bộ dự án để người khác có thể khởi chạy ngay chỉ bằng 1 lệnh `docker compose up`.

---

## 🐳 Khởi Chạy Bằng Docker (Khuyến nghị cho chuyển giao)

Không cần cài đặt thủ công Python, LibreOffice hay Tesseract trên máy:

```bash
cd md-converter-webapp
docker compose up --build
```

Mở trình duyệt tại: **`http://localhost:8000`**

---

## 💻 Khởi Chạy Thủ Công (Không dùng Docker)

### 1. Yêu cầu hệ thống:
- Python 3.10+
- Tesseract OCR (với gói ngôn ngữ `vie` và `eng`):
  - macOS: `brew install tesseract tesseract-lang`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng`
- LibreOffice (cho định dạng cũ `.doc`, `.xls`):
  - macOS: `brew install --cask libreoffice`
  - Ubuntu/Debian: `sudo apt install libreoffice`

### 2. Cài đặt và khởi chạy:

```bash
cd md-converter-webapp/backend

# Tạo và kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt

# Khởi chạy server
python -m app.main
```

Truy cập **`http://localhost:8000`** để sử dụng.

---

## 📡 Đặc Tả API

### `POST /api/convert`
- **Body**: `multipart/form-data` với trường `file` (.pdf, .doc, .docx, .xls, .xlsx).
- **Phản hồi**:
```json
{
  "filename": "bao-cao.pdf",
  "converted_via_legacy": false,
  "markdown": "# Tiêu Đề Báo Cáo\n\nNội dung văn bản...",
  "pages_total": 5,
  "pages_ocr": [2, 4],
  "warnings": [],
  "duration_ms": 1250,
  "word_count": 480,
  "character_count": 3200
}
```

### `GET /api/health`
Kiểm tra tính sẵn sàng của hệ thống, LibreOffice và Tesseract OCR.

---

## ⚙️ Cấu Hình Môi Trường (.env)

| Biến môi trường | Mặc định | Mô tả |
| :--- | :--- | :--- |
| `PORT` | `8000` | Cổng dịch vụ web |
| `OCR_DENSITY_THRESHOLD` | `50` | Ngưỡng số ký tự tối thiểu mỗi trang PDF để kích hoạt OCR |
| `OCR_RASTERIZE_DPI` | `200` | Độ phân giải rasterize ảnh trang PDF để OCR |
| `TESSERACT_LANG` | `vie+eng` | Ngôn ngữ OCR (Tiếng Việt + Tiếng Anh) |
| `MAX_FILE_SIZE_MB` | `50` | Giới hạn dung lượng tệp tải lên (MB) |
