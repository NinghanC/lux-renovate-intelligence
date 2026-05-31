import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import fitz

from app.models.schemas import PlanningChunk


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pdf(path: Path) -> list[PageText]:
    doc = fitz.open(path)
    pages: list[PageText] = []
    for page_index, page in enumerate(doc, start=1):
        text = normalize_text(page.get_text("text"))
        if text:
            pages.append(PageText(page=page_index, text=text))
    return pages


def parse_text_file(path: Path) -> list[PageText]:
    text = normalize_text(path.read_text(encoding="utf-8", errors="replace"))
    return [PageText(page=1, text=text)] if text else []


def parse_document(path: Path) -> list[PageText]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix in {".txt", ".md", ".markdown"}:
        return parse_text_file(path)
    raise ValueError(f"Unsupported document type: {suffix}")


def split_text(text: str, max_chars: int = 1200, overlap_chars: int = 150) -> list[str]:
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
    document_name: str,
    document_type: str,
    commune: str,
    source_path: Path,
    source_url: str | None,
    pages: list[PageText],
    max_chars: int = 1200,
) -> list[PlanningChunk]:
    chunks: list[PlanningChunk] = []
    for page in pages:
        for chunk_index, text in enumerate(split_text(page.text, max_chars=max_chars), start=1):
            chunk_id = f"{document_id}_p{page.page:03d}_c{chunk_index:03d}"
            chunks.append(
                PlanningChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    document_name=document_name,
                    document_type=document_type,
                    commune=commune,
                    page=page.page,
                    text=text,
                    source_path=str(source_path),
                    source_url=source_url,
                    metadata={"parser": "pymupdf", "max_chars": max_chars},
                )
            )
    return chunks

