from pathlib import Path

from app.core.paths import PROCESSED_DIR, RAW_PLANNING_DIR, RAW_UPLOADS_DIR, SAMPLE_DIR
from app.models.schemas import PlanningChunk
from app.services.document_parser import chunk_document, parse_document
from app.services.evidence_metadata import (
    infer_upload_subtype,
    is_upload_metadata_path,
    read_upload_metadata,
    upload_metadata_path,
)
from app.services.json_store import read_json, read_jsonl, write_json, write_jsonl
from app.services.source_registry import checksum_sha256, source_id_for_document


SOURCES_PATH = SAMPLE_DIR / "planning_sources.json"
PLANNING_CACHE_DIR = PROCESSED_DIR / "planning_cache"


class PlanningIngestionService:
    def __init__(self, sources_path: Path = SOURCES_PATH):
        self.sources_path = sources_path

    def load_planning_chunks_for_commune(self, commune: str) -> list[PlanningChunk]:
        cached = self._load_cached_planning_chunks(commune)
        if cached is not None:
            return cached
        chunks: list[PlanningChunk] = []
        for source in self._planning_sources_for_commune(commune):
            path = RAW_PLANNING_DIR / source["local_filename"]
            if not path.exists():
                continue
            pages = parse_document(path)
            chunks.extend(
                chunk_document(
                    document_id=source["document_id"],
                    source_id=source_id_for_document(source["document_id"]),
                    document_name=source["document_name"],
                    document_type=source["document_type"],
                    commune=source["commune"],
                    source_path=path,
                    source_url=source["url"],
                    pages=pages,
                    max_chars=1100,
                )
            )
        self._write_cached_planning_chunks(commune, chunks)
        return chunks

    def load_uploaded_chunks(self, *, site_id: str, commune: str) -> list[PlanningChunk]:
        chunks: list[PlanningChunk] = []
        for path in sorted(RAW_UPLOADS_DIR.glob("*")):
            if not path.is_file():
                continue
            if is_upload_metadata_path(path):
                continue
            if not path.name.startswith(f"{site_id}_"):
                continue
            document_id = f"upload_{path.stem}"
            pages = parse_document(path)
            combined_text = "\n".join(page.text for page in pages)
            upload_metadata = read_upload_metadata(path)
            source_subtype = upload_metadata.get("source_subtype") or infer_upload_subtype(path.name, combined_text)
            parsed = chunk_document(
                document_id=document_id,
                source_id=source_id_for_document(document_id),
                document_name=path.name,
                document_type="uploaded",
                commune=commune,
                source_path=path,
                source_url=None,
                pages=pages,
                max_chars=1100,
            )
            chunks.extend(
                chunk.model_copy(
                    update={
                        "metadata": {
                            **chunk.metadata,
                            "site_id": site_id,
                            "uploaded": True,
                            "source_subtype": source_subtype,
                            "upload_metadata": upload_metadata,
                        }
                    }
                )
                for chunk in parsed
            )
        return chunks

    def load_generate_chunks(
        self,
        *,
        commune: str,
        site_id: str,
        include_uploaded_documents: bool,
    ) -> list[PlanningChunk]:
        chunks = self.load_planning_chunks_for_commune(commune)
        if include_uploaded_documents:
            chunks.extend(self.load_uploaded_chunks(site_id=site_id, commune=commune))
        return chunks

    def _planning_sources_for_commune(self, commune: str) -> list[dict]:
        return [
            source
            for source in read_json(self.sources_path)
            if source["commune"].lower() == commune.lower()
        ]

    def _cache_paths(self, commune: str) -> tuple[Path, Path]:
        safe_commune = "".join(ch.lower() if ch.isalnum() else "_" for ch in commune).strip("_")
        return (
            PLANNING_CACHE_DIR / f"{safe_commune}_planning_chunks.jsonl",
            PLANNING_CACHE_DIR / f"{safe_commune}_planning_chunks.meta.json",
        )

    def _planning_signature(self, commune: str) -> list[dict[str, str | None]]:
        signature = []
        for source in self._planning_sources_for_commune(commune):
            path = RAW_PLANNING_DIR / source["local_filename"]
            signature.append(
                {
                    "document_id": source["document_id"],
                    "local_filename": source["local_filename"],
                    "checksum_sha256": checksum_sha256(path),
                }
            )
        return signature

    def planning_signature(self, commune: str) -> list[dict[str, str | None]]:
        return self._planning_signature(commune)

    def uploaded_signature(self, *, site_id: str, include_uploaded_documents: bool) -> list[dict[str, str | None]]:
        if not include_uploaded_documents:
            return []
        signature = []
        for path in sorted(RAW_UPLOADS_DIR.glob("*")):
            if not path.is_file():
                continue
            if is_upload_metadata_path(path):
                continue
            if not path.name.startswith(f"{site_id}_"):
                continue
            metadata_path = upload_metadata_path(path)
            signature.append(
                {
                    "filename": path.name,
                    "checksum_sha256": checksum_sha256(path),
                    "metadata_checksum_sha256": checksum_sha256(metadata_path),
                }
            )
        return signature

    def _load_cached_planning_chunks(self, commune: str) -> list[PlanningChunk] | None:
        chunks_path, meta_path = self._cache_paths(commune)
        if not chunks_path.exists() or not meta_path.exists():
            return None
        try:
            meta = read_json(meta_path)
        except Exception:
            return None
        if meta.get("signature") != self._planning_signature(commune):
            return None
        return read_jsonl(chunks_path, PlanningChunk)

    def _write_cached_planning_chunks(self, commune: str, chunks: list[PlanningChunk]) -> None:
        chunks_path, meta_path = self._cache_paths(commune)
        write_jsonl(chunks_path, chunks)
        write_json(
            meta_path,
            {
                "commune": commune,
                "signature": self._planning_signature(commune),
                "chunks": len(chunks),
            },
        )
