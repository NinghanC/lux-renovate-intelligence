from pathlib import Path

import fitz
import pytest

from app.services import document_parser
from app.services.document_parser import PageText, chunk_document, parse_document
from app.services.document_parser import parse_pdf, split_text


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
    assert pages[0].parser == "ocr"


def test_pdf_parser_closes_document_handle(monkeypatch, tmp_path: Path):
    closed = False

    class FakePage:
        def get_text(self, mode: str) -> str:
            assert mode == "text"
            return "Test page text."

    class FakeDocument:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            nonlocal closed
            closed = True

        def __iter__(self):
            return iter([FakePage()])

    monkeypatch.setattr(document_parser.fitz, "open", lambda path: FakeDocument())

    pages = parse_pdf(tmp_path / "sample.pdf")

    assert pages == [PageText(page=1, text="Test page text.", parser="pymupdf")]
    assert closed is True


@pytest.mark.parametrize(
    ("max_chars", "overlap_chars", "message"),
    [
        (0, 0, "max_chars must be greater than zero."),
        (10, -1, "overlap_chars must be zero or greater."),
        (10, 10, "overlap_chars must be smaller than max_chars."),
        (10, 11, "overlap_chars must be smaller than max_chars."),
    ],
)
def test_split_text_rejects_non_advancing_overlap(max_chars: int, overlap_chars: int, message: str):
    with pytest.raises(ValueError, match=message):
        split_text("a" * 30, max_chars=max_chars, overlap_chars=overlap_chars)


def test_split_text_advances_when_overlap_is_valid():
    chunks = split_text("abcdefghij", max_chars=4, overlap_chars=1)

    assert chunks == ["abcd", "defg", "ghij", "j"]
