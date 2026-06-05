import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.core.config import settings
from app.models.schemas import PlanningChunk
from app.services.ocr_provider import OCRProvider


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    parser: str = "pymupdf"


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pdf(path: Path, ocr_provider: OCRProvider | None = None) -> list[PageText]:
    ocr = ocr_provider or OCRProvider()
    pages: list[PageText] = []
    with fitz.open(path) as doc:
        for page_index, page in enumerate(doc, start=1):
            text = normalize_text(page.get_text("text"))
            parser = "pymupdf"
            if len(text) < settings.ocr_min_text_chars and ocr.configured:
                ocr_text = normalize_text(ocr.extract_text_from_png(render_page_png(page)))
                if len(ocr_text) > len(text):
                    text = ocr_text
                    parser = settings.ocr_model or "ocr"
            if text:
                pages.append(PageText(page=page_index, text=text, parser=parser))
    return pages


def parse_text_file(path: Path) -> list[PageText]:
    text = normalize_text(path.read_text(encoding="utf-8", errors="replace"))
    return [PageText(page=1, text=text, parser="text")] if text else []


def parse_document(path: Path) -> list[PageText]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in {".txt", ".md", ".markdown"}:
        return parse_text_file(path)
    raise ValueError(f"Unsupported document type: {suffix}")


def render_page_png(page: fitz.Page) -> bytes:
    scale = max(settings.ocr_render_dpi, 72) / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    return pixmap.tobytes("png")


def split_text(text: str, max_chars: int = 1200, overlap_chars: int = 150) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero.")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be zero or greater.")
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars.")

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + max_chars].strip())
                start += max_chars - overlap_chars
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current.strip())
            current = paragraph
    if current:
        chunks.append(current.strip())
    return chunks


def chunk_document(
    *,
    document_id: str,
    source_id: str | None = None,
    document_name: str,
    document_type: str,
    commune: str,
    source_path: Path,
    source_url: str | None,
    pages: list[PageText],
    max_chars: int = 1200,
) -> list[PlanningChunk]:
    chunks: list[PlanningChunk] = []
    resolved_source_id = source_id or f"src_{document_id}"
    for page in pages:
        for chunk_index, text in enumerate(split_text(page.text, max_chars=max_chars), start=1):
            chunk_id = f"{document_id}_p{page.page:03d}_c{chunk_index:03d}"
            chunks.append(
                PlanningChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    source_id=resolved_source_id,
                    document_name=document_name,
                    document_type=document_type,
                    commune=commune,
                    page=page.page,
                    text=text,
                    source_path=str(source_path),
                    source_url=source_url,
                    metadata={"parser": page.parser, "source_id": resolved_source_id, "max_chars": max_chars},
                )
            )
    return chunks
