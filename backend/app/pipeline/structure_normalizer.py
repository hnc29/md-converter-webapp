import re
import unicodedata
from typing import List, Tuple
from ..models import SectionInfo

VIETNAMESE_SLUG_MAP = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'đ': 'd', 'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y'
}

class StructureNormalizer:
    """
    Normalizes encoding (Unicode NFC, NULL bytes, BOM removal)
    and injects stable Section IDs into Markdown headings.
    """

    @staticmethod
    def normalize_encoding(text: str) -> str:
        """
        Ensures strict UTF-8 Unicode NFC normalization,
        removes NULL bytes, BOM, and standardizes line endings.
        """
        if not text:
            return ""

        # Remove BOM and NULL bytes
        text = text.replace("\ufeff", "").replace("\x00", "")

        # Standardize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Canonical Unicode NFC decomposition
        text = unicodedata.normalize("NFC", text)

        return text

    @staticmethod
    def slugify(text: str) -> str:
        """Generates deterministic ASCII slug for stable anchor tags."""
        s = text.lower().strip()
        for k, v in VIETNAMESE_SLUG_MAP.items():
            s = s.replace(k, v)
        # Replace non-alphanumeric with hyphen
        s = re.sub(r"[^\w]+", "-", s)
        s = re.sub(r"-+", "-", s).strip("-")
        return s or "section"

    @staticmethod
    def format_document_structure(text: str) -> str:
        """
        Detects standard Vietnamese legal/administrative headers, chapters, articles,
        and converts them to appropriate Markdown heading hierarchies (#, ##, ###).
        """
        if not text:
            return ""

        lines = text.split("\n")
        output: List[str] = []

        for line in lines:
            s = line.strip()
            # Preserve existing Markdown headings or comments
            if s.startswith("#") or s.startswith("<!--") or s.startswith(">") or not s:
                output.append(line)
                continue

            # Check for Chapter heading (e.g. CHƯƠNG I, CHƯƠNG II...)
            if re.match(r"^CHƯƠNG\s+[IVXLCDM]+", s, re.IGNORECASE):
                output.append(f"\n## {s}\n")
            # Check for Article heading (e.g. Điều 1., Điều 2:...)
            elif re.match(r"^Điều\s+\d+[\.:]", s, re.IGNORECASE):
                output.append(f"\n### {s}\n")
            # Check for Major Heading (QUYẾT ĐỊNH, QUY CHẾ PHÂN CẤP...)
            elif re.match(r"^(QUYẾT ĐỊNH|QUY CHẾ PHÂN CẤP|HỘI ĐỒNG THÀNH VIÊN)\b", s):
                output.append(f"\n# {s}\n")
            else:
                output.append(line)

        formatted = "\n".join(output)
        return re.sub(r"\n{3,}", "\n\n", formatted)

    def process_headings_and_sections(self, markdown: str) -> Tuple[str, List[SectionInfo]]:
        """
        Processes headings in Markdown:
        1. Formats administrative structural elements (Chapters, Articles)
        2. Injects stable anchor tags: <a id="sec-..."></a>
        3. Tracks page boundaries (from <!-- source_page: X -->)
        4. Extracts hierarchical SectionInfo list for Master Index & manifest.json.
        """
        markdown = self.format_document_structure(markdown)
        lines = markdown.split("\n")
        output_lines: List[str] = []
        sections: List[SectionInfo] = []
        used_ids: set[str] = set()

        current_page = 1
        page_pattern = re.compile(r"<!--\s*(?:source_page|Page)\s*[:\s]*(\d+)[^>]*-->", re.IGNORECASE)
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            # Check for page marker
            p_match = page_pattern.search(line)
            if p_match:
                try:
                    current_page = int(p_match.group(1))
                except ValueError:
                    pass

            h_match = heading_pattern.match(line)
            if h_match:
                hashes, title = h_match.groups()
                level = len(hashes)
                clean_title = re.sub(r"<[^>]+>", "", title).strip()

                # Generate base slug
                slug = self.slugify(clean_title)
                sec_id = f"sec-{slug}"

                # Ensure uniqueness within document
                counter = 1
                unique_sec_id = sec_id
                while unique_sec_id in used_ids:
                    counter += 1
                    unique_sec_id = f"{sec_id}-{counter}"
                used_ids.add(unique_sec_id)

                # Add anchor tag before heading
                anchor_tag = f'<a id="{unique_sec_id}"></a>'
                output_lines.append(anchor_tag)
                output_lines.append(f"{hashes} {clean_title}")

                sections.append(
                    SectionInfo(
                        id=unique_sec_id,
                        heading=clean_title,
                        level=level,
                        source_page_start=current_page,
                        source_page_end=current_page
                    )
                )
            else:
                output_lines.append(line)

        # Update source_page_end for sections based on the start of the next section
        for i in range(len(sections) - 1):
            sections[i].source_page_end = max(sections[i].source_page_start or 1, sections[i + 1].source_page_start or 1)
        if sections and sections[-1].source_page_start:
            sections[-1].source_page_end = max(sections[-1].source_page_start, current_page)

        processed_markdown = "\n".join(output_lines)
        return processed_markdown, sections

    @staticmethod
    def clean_markdown_boundaries(markdown: str) -> str:
        """Removes excessive empty lines, ensures neat spacing around headers and tables."""
        # Normalize multiple newlines
        cleaned = re.sub(r"\n{4,}", "\n\n\n", markdown)
        return cleaned.strip()

structure_normalizer = StructureNormalizer()
