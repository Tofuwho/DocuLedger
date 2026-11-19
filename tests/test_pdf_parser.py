"""
Unit tests for PyMuPDF (fitz) Spatial PDF Parser.
Verifies spatial text extraction, coordinate bounding boxes, and image rendering.
"""

import pytest
from apps.ledger.models import Document
from apps.extractor.pdf_parser import SpatialPDFParser, parse_pdf_document


@pytest.mark.django_db
def test_spatial_pdf_parser_on_compliant_sample():
    doc = Document.objects.filter(file_name="PH_Sample_Invoice_Compliant.pdf").first()
    assert doc is not None, "Sample document must exist in database."

    doc.file.seek(0)
    pdf_bytes = doc.file.read()

    with SpatialPDFParser(pdf_bytes) as parser:
        assert parser.page_count >= 1
        width, height = parser.get_page_dimensions(0)
        assert width > 0 and height > 0

        # Full text extraction
        full_text = parser.extract_full_text()
        assert "MEGAWORLD TECH DISTRIBUTORS INC." in full_text
        assert "123-456-789-000" in full_text
        assert "SALES INVOICE" in full_text
        assert "150,000.00" in full_text
        assert "18,000.00" in full_text

        # Spatial blocks
        blocks = parser.extract_spatial_blocks(0)
        assert len(blocks) > 0
        for b in blocks:
            assert "bbox" in b
            assert len(b["bbox"]) == 4
            assert b["bbox"][0] <= b["bbox"][2]
            assert b["bbox"][1] <= b["bbox"][3]

        # Search phrase bbox
        bbox = parser.search_phrase_bbox("MEGAWORLD")
        assert bbox is not None
        assert len(bbox) == 4

        # Render page to PNG
        png_bytes = parser.render_page_to_png(0)
        assert png_bytes.startswith(b"\x89PNG")


@pytest.mark.django_db
def test_parse_pdf_document_helper():
    doc = Document.objects.filter(file_name="PH_Sample_Invoice_Compliant.pdf").first()
    doc.file.seek(0)
    res = parse_pdf_document(doc.file.read())
    assert res["page_count"] >= 1
    assert len(res["pages"]) >= 1
    assert len(res["pages"][0]["blocks"]) > 0
