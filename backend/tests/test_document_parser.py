from pathlib import Path

import fitz

from app.services.document_parser import chunk_document, parse_document
from app.services.document_parser import parse_pdf


class FakeOCRProvider:
    configured = True

    def extract_text_from_png(self, image_bytes: bytes) -> str:
        assert image_bytes.startswith(b"\x89PNG")
        return "OCR extracted basement humidity note."


def test_pdf_parser_and_chunker(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Planning evidence for a renovation dossier.\nFire documents are missing.")
    doc.save(pdf_path)
    doc.close()

    pages = parse_document(pdf_path)
    chunks = chunk_document(
        document_id="test_doc",
        document_name="Test Document",
        document_type="PAG",
        commune="Luxembourg",
        source_path=pdf_path,
        source_url="https://example.test/doc.pdf",
        pages=pages,
        max_chars=200,
    )

    assert pages
    assert chunks[0].document_id == "test_doc"
    assert chunks[0].page == 1
    assert "Planning evidence" in chunks[0].text


def test_pdf_parser_uses_ocr_fallback_for_scanned_pages(tmp_path: Path):
    pdf_path = tmp_path / "scanned.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    pages = parse_pdf(pdf_path, ocr_provider=FakeOCRProvider())

    assert pages[0].text == "OCR extracted basement humidity note."
    assert pages[0].parser == "aws-textract-detect-document-text"
