import re
from typing import List
from ..models import PageResult

class MarkdownMerger:
    @staticmethod
    def merge_pages(pages: List[PageResult]) -> str:
        """
        Merges individual page results in exact page order into final Markdown.
        """
        if not pages:
            return ""

        if len(pages) == 1:
            return pages[0].text.strip()

        merged_sections: List[str] = []
        for page in pages:
            ocr_badge = " *(Trang đã qua OCR)*" if page.is_ocr else ""
            header = f"<!-- Page {page.page_number}{ocr_badge} -->"
            
            body = page.text.strip()
            if not body:
                body = "*(Trang trống hoặc không có nội dung văn bản)*"

            merged_sections.append(f"{header}\n\n{body}")

        return "\n\n---\n\n".join(merged_sections).strip()

    @staticmethod
    def calculate_stats(markdown: str) -> tuple[int, int]:
        """Returns (word_count, char_count)."""
        clean_text = re.sub(r"[#*`_~\[\]()><!|]", " ", markdown)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        words = len(clean_text.split()) if clean_text else 0
        chars = len(markdown)
        return words, chars

markdown_merger = MarkdownMerger()
