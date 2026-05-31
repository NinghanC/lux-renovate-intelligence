from pathlib import Path

from app.core.paths import RAW_PLANNING_DIR, RAW_UPLOADS_DIR, SAMPLE_DIR
from app.models.schemas import PlanningChunk
from app.services.document_parser import chunk_document, parse_document
from app.services.json_store import read_json


SOURCES_PATH = SAMPLE_DIR / "planning_sources.json"


class PlanningIngestionService:
    def __init__(self, sources_path: Path = SOURCES_PATH):
        self.sources_path = sources_path

    def load_planning_chunks_for_commune(self, commune: str) -> list[PlanningChunk]:
        chunks: list[PlanningChunk] = []
        for source in read_json(self.sources_path):
            if source["commune"].lower() != commune.lower():
                continue
            path = RAW_PLANNING_DIR / source["local_filename"]
            if not path.exists():
                continue
            pages = parse_document(path)
            chunks.extend(
                chunk_document(
                    document_id=source["document_id"],
                    document_name=source["document_name"],
                    document_type=source["document_type"],
                    commune=source["commune"],
                    source_path=path,
                    source_url=source["url"],
                    pages=pages,
                    max_chars=1100,
                )
            )
        return chunks

    def load_uploaded_chunks(self, *, site_id: str, commune: str) -> list[PlanningChunk]:
        chunks: list[PlanningChunk] = []
        for path in sorted(RAW_UPLOADS_DIR.glob("*")):
            if not path.is_file():
                continue
            if not path.name.startswith(f"{site_id}_"):
                continue
            document_id = f"upload_{path.stem}"
            pages = parse_document(path)
            parsed = chunk_document(
                document_id=document_id,
                document_name=path.name,
                document_type="uploaded",
                commune=commune,
                source_path=path,
                source_url=None,
                pages=pages,
                max_chars=1100,
            )
            chunks.extend(
                chunk.model_copy(update={"metadata": {**chunk.metadata, "site_id": site_id, "uploaded": True}})
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

