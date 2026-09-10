import os
import subprocess
import shutil
from pathlib import Path
from ..config import settings

class LegacyConversionError(Exception):
    """Raised when legacy format conversion fails."""

def _convert_xls_to_xlsx_python(input_path: Path, output_path: Path) -> Path:
    """Converts legacy .xls to .xlsx using pandas + xlrd + openpyxl."""
    try:
        import pandas as pd
        excel_file = pd.ExcelFile(input_path, engine="xlrd")
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)
        return output_path
    except Exception as e:
        raise LegacyConversionError(f"Lỗi chuyển đổi file Excel cũ (.xls) qua engine Python (xlrd): {str(e)}")

def convert_legacy_document(input_path: Path, output_dir: Path) -> tuple[Path, bool]:
    """
    Converts binary .doc -> .docx or .xls -> .xlsx using:
    1. Headless LibreOffice (if installed)
    2. macOS textutil for .doc -> .docx
    3. Python xlrd + openpyxl for .xls -> .xlsx
    
    Returns:
        tuple (converted_path, is_legacy)
    """
    ext = input_path.suffix.lower()
    if ext not in settings.LEGACY_EXTENSIONS:
        return input_path, False

    target_ext = "docx" if ext == ".doc" else "xlsx"
    expected_output = output_dir / f"{input_path.stem}.{target_ext}"
    libreoffice_bin = settings.find_libreoffice_bin()

    # 1. Try LibreOffice if available
    if libreoffice_bin:
        cmd = [
            libreoffice_bin,
            "--headless",
            "--convert-to",
            target_ext,
            "--outdir",
            str(output_dir),
            str(input_path)
        ]
        try:
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=settings.LIBREOFFICE_TIMEOUT_SECONDS,
                check=False
            )
            if process.returncode == 0 and expected_output.exists() and expected_output.stat().st_size > 0:
                return expected_output, True
        except (subprocess.TimeoutExpired, Exception):
            pass

    # 2. Fallbacks when LibreOffice is not installed or failed
    if ext == ".doc":
        # Check for macOS native textutil
        textutil_bin = settings.resolve_textutil_bin()
        if textutil_bin:
            cmd = [
                textutil_bin,
                "-convert",
                "docx",
                "-output",
                str(expected_output),
                str(input_path)
            ]
            try:
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=settings.LIBREOFFICE_TIMEOUT_SECONDS,
                    check=False
                )
                if process.returncode == 0 and expected_output.exists() and expected_output.stat().st_size > 0:
                    return expected_output, True
                else:
                    err = process.stderr or process.stdout or "textutil failed"
                    raise LegacyConversionError(f"Không thể chuyển đổi file .doc qua textutil: {err}")
            except Exception as e:
                raise LegacyConversionError(f"Lỗi khi thực thi textutil cho file .doc: {str(e)}")

        raise LegacyConversionError(
            "Không tìm thấy công cụ chuyển đổi định dạng .doc (LibreOffice hoặc textutil trên macOS). "
            "Vui lòng cài đặt LibreOffice hoặc lưu file dưới dạng .docx."
        )

    elif ext == ".xls":
        # Native Python conversion for .xls -> .xlsx
        return _convert_xls_to_xlsx_python(input_path, expected_output), True

    return input_path, False

