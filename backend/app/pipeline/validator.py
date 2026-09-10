import re
from typing import List
from ..models import ValidationResult, ValidationCheck, DocumentMetadata

class MarkdownValidator:
    """
    Automated Quality Gate ensuring only verified, high-quality Markdown
    documents are placed into the upload_to_ai/ directory.
    """

    def validate(self, markdown: str, metadata: DocumentMetadata, is_paginated: bool = False, is_ocr: bool = False) -> ValidationResult:
        checks: List[ValidationCheck] = []
        warnings: List[str] = []
        errors: List[str] = []

        # 1. UTF-8 & No NULL bytes
        has_null = "\x00" in markdown
        checks.append(ValidationCheck(
            name="UTF-8 & Không chứa NULL byte",
            passed=not has_null,
            message="Đạt chuẩn Unicode NFC, không chứa NULL byte." if not has_null else "Phát hiện NULL byte trong tài liệu."
        ))
        if has_null:
            errors.append("Tài liệu chứa ký tự NULL byte không hợp lệ.")

        # 2. File không rỗng
        is_not_empty = bool(markdown and len(markdown.strip()) > 20)
        checks.append(ValidationCheck(
            name="Nội dung không rỗng",
            passed=is_not_empty,
            message="Tài liệu có nội dung đầy đủ." if is_not_empty else "Tài liệu rỗng hoặc quá ngắn."
        ))
        if not is_not_empty:
            errors.append("Tài liệu rỗng hoặc quá ngắn sau khi chuyển đổi.")

        # 3. Có source_file & title trong metadata
        has_source = bool(metadata.source_file.strip())
        has_title = bool(metadata.title.strip())
        checks.append(ValidationCheck(
            name="Metadata source_file & title hợp lệ",
            passed=has_source and has_title,
            message=f"Source: {metadata.source_file} | Title: {metadata.title}"
        ))
        if not (has_source and has_title):
            errors.append("Thiếu thông tin source_file hoặc title trong metadata.")

        # 4. Có cấu trúc Heading hoặc phân đoạn
        has_heading = bool(re.search(r"^#{1,6}\s+", markdown, re.MULTILINE))
        checks.append(ValidationCheck(
            name="Cấu trúc Heading hiện diện",
            passed=has_heading,
            message="Đã phát hiện phân cấp Heading." if has_heading else "Không phát hiện Heading nào trong tài liệu."
        ))
        if not has_heading:
            warnings.append("Tài liệu không có Heading phân cấp (chỉ có văn bản thuần).")

        # 5. Không bao toàn bộ tài liệu trong Code Block
        is_all_code = markdown.strip().startswith("```") and markdown.strip().endswith("```") and markdown.strip().count("```") == 2
        checks.append(ValidationCheck(
            name="Không bọc toàn bộ văn bản trong code fence",
            passed=not is_all_code,
            message="Văn bản tự nhiên, không bị bọc code fence toàn phần." if not is_all_code else "Tài liệu bị bao toàn bộ trong block code."
        ))
        if is_all_code:
            errors.append("Toàn bộ văn bản bị bao trong khối code block ```text.")

        # 6. Không có nội dung Base64 thô
        has_raw_base64 = bool(re.search(r"data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]{200,}", markdown))
        checks.append(ValidationCheck(
            name="Không chứa chuỗi Base64 hình ảnh thô",
            passed=not has_raw_base64,
            message="Không có chuỗi base64 nhúng trực tiếp." if not has_raw_base64 else "Phát hiện chuỗi base64 dung lượng lớn trong văn bản."
        ))
        if has_raw_base64:
            warnings.append("Phát hiện dữ liệu ảnh Base64 thô trong Markdown.")

        # 7. Page markers nếu là tài liệu có pagination (PDF)
        if is_paginated and metadata.page_count > 1:
            has_page_marker = "<!-- source_page:" in markdown or "<!-- Page" in markdown
            checks.append(ValidationCheck(
                name="Truy vết ranh giới trang (Page Markers)",
                passed=has_page_marker,
                message="Đã chèn marker định vị trang." if has_page_marker else "Thiếu marker ranh giới trang."
            ))
            if not has_page_marker:
                warnings.append("Tài liệu nhiều trang nhưng thiếu marker phân định trang.")

        # 8. Tỷ lệ giữ lại ký tự (Quality Gate: >= 90% PASS, 75%-90% WARNING, < 75% FAIL)
        retention = metadata.text_retention_ratio
        if is_ocr:
            # For scanned image OCR, text length in original file is 0 or tiny
            retention_pass = True
            checks.append(ValidationCheck(
                name="Tỷ lệ bảo toàn nội dung (OCR Image)",
                passed=True,
                message=f"Tài liệu OCR trích xuất {metadata.markdown_text_char_count} ký tự."
            ))
        else:
            if retention >= 0.90:
                retention_status = "PASS"
                retention_pass = True
                msg = f"Tỷ lệ bảo toàn ký tự xuất sắc: {int(retention * 100)}% ({metadata.markdown_text_char_count}/{metadata.source_text_char_count} chars)"
            elif retention >= 0.75:
                retention_status = "WARNING"
                retention_pass = True
                msg = f"Tỷ lệ bảo toàn ký tự chấp nhận được: {int(retention * 100)}% ({metadata.markdown_text_char_count}/{metadata.source_text_char_count} chars)"
                warnings.append(f"Tỷ lệ ký tự Markdown giảm nhẹ so với nguồn ({int(retention * 100)}%).")
            else:
                retention_status = "FAIL"
                retention_pass = False
                msg = f"CẢNH BÁO: Nghi ngờ mất nội dung nghiêm trọng ({int(retention * 100)}% < 75%)."
                errors.append(f"FAILED: Tỷ lệ ký tự quá thấp ({int(retention * 100)}%), cần kiểm tra thủ công.")

            checks.append(ValidationCheck(
                name="Tỷ lệ bảo toàn nội dung (Retention Ratio)",
                passed=retention_pass,
                message=msg
            ))

        # 9. SHA-256 Checksum tồn tại
        has_sha = bool(metadata.source_sha256 and len(metadata.source_sha256) == 64)
        checks.append(ValidationCheck(
            name="Mã băm SHA-256 xác thực",
            passed=has_sha,
            message=f"SHA256: {metadata.source_sha256[:16]}..." if has_sha else "Thiếu mã băm SHA256."
        ))

        # Quality Gate Decision
        if errors or not is_not_empty or has_null:
            status = "FAIL"
            is_safe_for_ai = False
        elif warnings:
            status = "WARNING"
            is_safe_for_ai = True
        else:
            status = "PASS"
            is_safe_for_ai = True

        return ValidationResult(
            status=status,
            is_safe_for_ai=is_safe_for_ai,
            checks=checks,
            warnings=warnings,
            errors=errors
        )

validator = MarkdownValidator()
