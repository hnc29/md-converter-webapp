import os
import shutil
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "MD Converter (MarkItDown + Local OCR)"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8088"))

    # Paths
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    STORAGE_TMP_DIR: Path = PROJECT_ROOT / "storage" / "tmp"

    # File Constraints
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
    LEGACY_EXTENSIONS: set[str] = {".doc", ".xls"}

    # OCR & Density Configuration
    # Minimum valid characters per PDF page to consider text layer sufficient.
    # If a page has fewer characters than this threshold, it triggers local OCR.
    MIN_DENSITY_CHARS_PER_PAGE: int = int(os.getenv("OCR_DENSITY_THRESHOLD", "50"))
    RASTERIZE_DPI: int = int(os.getenv("OCR_RASTERIZE_DPI", "200"))
    
    # Tesseract settings
    TESSERACT_BIN: str = os.getenv("TESSERACT_BIN", "/opt/homebrew/bin/tesseract")
    TESSERACT_LANG: str = os.getenv("TESSERACT_LANG", "vie+eng")
    TESSERACT_PSM: int = int(os.getenv("TESSERACT_PSM", "3"))
    TESSERACT_TIMEOUT_SECONDS: int = int(os.getenv("TESSERACT_TIMEOUT", "60"))

    # LibreOffice settings
    LIBREOFFICE_BIN: str = os.getenv("LIBREOFFICE_BIN", "")
    LIBREOFFICE_TIMEOUT_SECONDS: int = int(os.getenv("LIBREOFFICE_TIMEOUT", "120"))

    # Timeout
    CONVERSION_TIMEOUT_SECONDS: int = int(os.getenv("CONVERSION_TIMEOUT", "300"))

    def find_libreoffice_bin(self) -> str | None:
        """Finds LibreOffice executable across Linux and macOS paths, returns None if not found."""
        if self.LIBREOFFICE_BIN and (shutil.which(self.LIBREOFFICE_BIN) or Path(self.LIBREOFFICE_BIN).exists()):
            return self.LIBREOFFICE_BIN

        candidates = [
            "libreoffice",
            "soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/usr/bin/libreoffice",
            "/usr/bin/soffice",
            "/opt/homebrew/bin/soffice",
            "/opt/homebrew/bin/libreoffice",
        ]
        for candidate in candidates:
            if shutil.which(candidate) or (Path(candidate).exists() and os.access(candidate, os.X_OK)):
                return candidate
        return None

    def resolve_libreoffice_bin(self) -> str:
        """Finds LibreOffice executable or defaults to 'libreoffice'."""
        found = self.find_libreoffice_bin()
        return found if found else "libreoffice"

    def resolve_textutil_bin(self) -> str | None:
        """Finds macOS textutil tool if available."""
        if shutil.which("textutil"):
            return "textutil"
        if Path("/usr/bin/textutil").exists():
            return "/usr/bin/textutil"
        return None

    def resolve_tesseract_bin(self) -> str:
        """Finds Tesseract executable."""
        if self.TESSERACT_BIN and (shutil.which(self.TESSERACT_BIN) or Path(self.TESSERACT_BIN).exists()):
            return self.TESSERACT_BIN
        found = shutil.which("tesseract")
        if found:
            return found
        return "/usr/bin/tesseract"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
settings.STORAGE_TMP_DIR.mkdir(parents=True, exist_ok=True)
