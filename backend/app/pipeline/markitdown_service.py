from pathlib import Path
from markitdown import MarkItDown

class MarkItDownService:
    def __init__(self):
        # Initialize MarkItDown without Azure or third-party cloud plugins
        self._md = MarkItDown()

    def convert_file(self, file_path: Path) -> str:
        """
        Converts a document (DOCX, XLSX, etc.) to Markdown using MarkItDown.
        """
        result = self._md.convert(str(file_path))
        return result.text_content if hasattr(result, "text_content") else str(result)

markitdown_service = MarkItDownService()
