"""
PyMuPDF (fitz) Spatial Text & Coordinate Extractor for DocuLedger PH.
Extracts high-resolution text blocks, word bounding boxes, and document geometry
without requiring heavy OCR libraries.
"""

import pymupdf as fitz  # PyMuPDF
from typing import Dict, List, Any, Optional, Tuple, Union


class SpatialPDFParser:
    """Parser to extract raw text, spatial blocks, and coordinate bounding boxes."""

    def __init__(self, pdf_source: Union[str, bytes]):
        """
        Initialize with either a filesystem path or raw PDF bytes.
        """
        if isinstance(pdf_source, bytes):
            self.doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            self.doc = fitz.open(pdf_source)
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.doc:
            self.doc.close()

    @property
    def page_count(self) -> int:
        return len(self.doc)

    def get_page_dimensions(self, page_num: int = 0) -> Tuple[float, float]:
        """Returns (width, height) in PDF points."""
        page = self.doc[page_num]
        rect = page.rect
        return (rect.width, rect.height)

    def extract_full_text(self) -> str:
        """Extracts complete sequential text across all pages."""
        text_parts = []
        for i, page in enumerate(self.doc):
            text = page.get_text("text")
            text_parts.append(text)
        return "\n--- Page Break ---\n".join(text_parts)

    def extract_spatial_blocks(self, page_num: int = 0) -> List[Dict[str, Any]]:
        """
        Extracts structured text blocks with coordinates:
        [
            {
                "bbox": [x0, y0, x1, y1],
                "text": "...",
                "lines": [...]
            }
        ]
        """
        page = self.doc[page_num]
        blocks = page.get_text("blocks")
        structured_blocks = []
        for b in blocks:
            # fitz block format: (x0, y0, x1, y1, text, block_no, block_type)
            if len(b) >= 5 and b[4].strip():
                structured_blocks.append({
                    "bbox": [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)],
                    "text": b[4].strip(),
                    "block_no": b[5] if len(b) > 5 else 0,
                    "type": b[6] if len(b) > 6 else 0
                })
        return structured_blocks

    def search_phrase_bbox(self, phrase: str, page_num: int = 0) -> Optional[List[float]]:
        """
        Searches for a phrase or word on a specific page and returns its bounding box [x0, y0, x1, y1].
        """
        if not phrase:
            return None
        page = self.doc[page_num]
        rects = page.search_for(phrase)
        if rects:
            r = rects[0]
            return [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]
        return None

    def extract_all_page_words(self, page_num: int = 0) -> List[Dict[str, Any]]:
        """Extracts individual words and their bounding boxes."""
        page = self.doc[page_num]
        words = page.get_text("words")
        # (x0, y0, x1, y1, word, block_no, line_no, word_no)
        return [
            {
                "text": w[4],
                "bbox": [round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2)],
                "line": w[6],
                "block": w[5]
            }
            for w in words
        ]

    def render_page_to_png(self, page_num: int = 0, zoom: float = 1.5) -> bytes:
        """Renders a page to PNG bytes for high-res web preview."""
        page = self.doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")


def parse_pdf_document(pdf_source: Union[str, bytes]) -> Dict[str, Any]:
    """Convenience helper to extract comprehensive spatial data from PDF."""
    with SpatialPDFParser(pdf_source) as parser:
        full_text = parser.extract_full_text()
        page_count = parser.page_count
        pages_data = []
        for i in range(page_count):
            width, height = parser.get_page_dimensions(i)
            blocks = parser.extract_spatial_blocks(i)
            pages_data.append({
                "page_index": i,
                "width": width,
                "height": height,
                "blocks": blocks,
            })
        return {
            "page_count": page_count,
            "raw_text": full_text,
            "pages": pages_data,
        }
