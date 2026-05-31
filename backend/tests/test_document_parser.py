from pathlib import Path

import fitz

from app.services.document_parser import chunk_document, parse_document


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

