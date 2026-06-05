import hashlib
import logging
from pathlib import Path

import fitz

from app.core.paths import PROCESSED_DIR, RAW_PLANNING_DIR, RAW_UPLOADS_DIR, SAMPLE_DIR
from app.models.schemas import PlanningChunk, SourceRecord
from app.services.evidence_metadata import (
    infer_upload_subtype,
    is_upload_metadata_path,
    modality_for_path,
    read_upload_metadata,
    upload_metadata_path,
)
from app.services.json_store import read_json, write_json


PLANNING_SOURCES_PATH = SAMPLE_DIR / "planning_sources.json"
DEMO_SITES_PATH = SAMPLE_DIR / "demo_sites.json"
SOURCE_REGISTRY_PATH = PROCESSED_DIR / "source_registry.json"
logger = logging.getLogger(__name__)


def source_id_for_document(document_id: str) -> str:
    return f"src_{document_id}"


def checksum_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def page_count(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    if path.suffix.lower() != ".pdf":
        return 1
    try:
        with fitz.open(path) as doc:
            return len(doc)
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("Could not read page count for %s: %s", path, exc)
        return None


def parser_name_for_path(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "pymupdf_or_ocr"
    if path.suffix.lower() in {".txt", ".md", ".markdown"}:
        return "text"
    return "unknown"


class SourceRegistry:
    def __init__(
        self,
        planning_sources_path: Path = PLANNING_SOURCES_PATH,
        raw_planning_dir: Path = RAW_PLANNING_DIR,
        raw_uploads_dir: Path = RAW_UPLOADS_DIR,
        registry_path: Path = SOURCE_REGISTRY_PATH,
    ):
        self.planning_sources_path = planning_sources_path
        self.raw_planning_dir = raw_planning_dir
        self.raw_uploads_dir = raw_uploads_dir
        self.registry_path = registry_path
        self._cached_signature: tuple[object, ...] | None = None
        self._cached_sources: list[SourceRecord] | None = None

    def list_sources(self) -> list[SourceRecord]:
        signature = self._source_signature()
        if self._cached_signature == signature and self._cached_sources is not None:
            return list(self._cached_sources)
        records = (
            self._planning_sources()
            + self._site_profile_sources()
            + self._uploaded_sources()
            + [self._geojson_source(), self._derived_source()]
        )
        records = sorted(records, key=lambda item: item.source_id)
        self._cached_signature = signature
        self._cached_sources = records
        return list(records)

    def refresh_snapshot(self) -> list[SourceRecord]:
        self._cached_signature = None
        self._cached_sources = None
        records = self.list_sources()
        write_json(self.registry_path, [record.model_dump(mode="json") for record in records])
        return records

    def get_by_id(self, source_id: str) -> SourceRecord | None:
        for source in self.list_sources():
            if source.source_id == source_id:
                return source
        return None

    def source_for_chunk(self, chunk: PlanningChunk) -> SourceRecord | None:
        return self.get_by_id(chunk.source_id or source_id_for_document(chunk.document_id))

    def _source_signature(self) -> tuple[object, ...]:
        return (
            self._file_signature(self.planning_sources_path),
            self._file_signature(DEMO_SITES_PATH),
            self._directory_signature(self.raw_planning_dir),
            self._directory_signature(self.raw_uploads_dir),
            self._file_signature(SAMPLE_DIR / "demo_geospatial.geojson"),
        )

    def _file_signature(self, path: Path) -> tuple[str, int, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return (str(path), stat.st_mtime_ns, stat.st_size)

    def _directory_signature(self, path: Path) -> tuple[tuple[str, int, int], ...]:
        if not path.exists():
            return ()
        signatures: list[tuple[str, int, int]] = []
        for item in sorted(path.iterdir()):
            if not item.is_file() or is_upload_metadata_path(item):
                continue
            file_signature = self._file_signature(item)
            if file_signature is not None:
                signatures.append(file_signature)
            metadata_signature = self._file_signature(upload_metadata_path(item))
            if metadata_signature is not None:
                signatures.append(metadata_signature)
        return tuple(signatures)

    def _planning_sources(self) -> list[SourceRecord]:
        if not self.planning_sources_path.exists():
            return []
        records: list[SourceRecord] = []
        for source in read_json(self.planning_sources_path):
            local_path = self.raw_planning_dir / source["local_filename"]
            records.append(
                SourceRecord(
                    source_id=source_id_for_document(source["document_id"]),
                    display_name=source["document_name"],
                    source_type="official_planning_pdf",
                    source_subtype=source.get("document_type", "planning_pdf").lower(),
                    modality=modality_for_path(local_path),
                    authority="municipal_official",
                    commune=source.get("commune"),
                    language=source.get("language", "fr"),
                    original_url=source.get("url"),
                    source_page_url=source.get("source_page"),
                    local_path=str(local_path),
                    checksum_sha256=checksum_sha256(local_path),
                    page_count=page_count(local_path),
                    parser=parser_name_for_path(local_path),
                    status="available" if local_path.exists() else "missing_local_file",
                    metadata={
                        "document_id": source["document_id"],
                        "document_type": source.get("document_type"),
                        "license_note": source.get("license_note"),
                    },
                )
            )
        return records

    def _site_profile_sources(self) -> list[SourceRecord]:
        if not DEMO_SITES_PATH.exists():
            return []
        records: list[SourceRecord] = []
        for site in read_json(DEMO_SITES_PATH):
            records.append(
                SourceRecord(
                    source_id=f"src_site_profile_{site['site_id']}",
                    display_name=f"Demo site profile - {site['display_name']}",
                    source_type="site_profile",
                    source_subtype="demo_site_profile",
                    modality="structured_profile",
                    authority="demo_data",
                    commune=site.get("commune"),
                    language="en",
                    parser="json",
                    status="available",
                    metadata={
                        "site_id": site["site_id"],
                        "purpose": "Demo site identity, approximate coordinate, and data-quality context.",
                    },
                )
            )
        return records

    def _uploaded_sources(self) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        if not self.raw_uploads_dir.exists():
            return records
        for path in sorted(self.raw_uploads_dir.iterdir()):
            if not path.is_file():
                continue
            if is_upload_metadata_path(path):
                continue
            document_id = f"upload_{path.stem}"
            upload_metadata = read_upload_metadata(path)
            modality = modality_for_path(path)
            records.append(
                SourceRecord(
                    source_id=source_id_for_document(document_id),
                    display_name=path.name,
                    source_type="uploaded_image" if modality == "image" else "uploaded_document",
                    source_subtype=upload_metadata.get("source_subtype") or infer_upload_subtype(path.name),
                    modality=modality,
                    authority="user_supplied",
                    commune=None,
                    language=None,
                    local_path=str(path),
                    checksum_sha256=checksum_sha256(path),
                    page_count=page_count(path),
                    parser=parser_name_for_path(path),
                    status="available",
                    metadata={"document_id": document_id, **upload_metadata},
                )
            )
        return records

    def _geojson_source(self) -> SourceRecord:
        local_path = SAMPLE_DIR / "demo_geospatial.geojson"
        return SourceRecord(
            source_id="src_demo_geospatial_geojson",
            display_name="Demo site coordinate GeoJSON",
            source_type="geojson",
            source_subtype="demo_coordinate_context",
            modality="geojson",
            authority="open_geospatial",
            commune=None,
            language="en",
            local_path=str(local_path),
            checksum_sha256=checksum_sha256(local_path),
            page_count=None,
            parser="geojson",
            status="available" if local_path.exists() else "missing_local_file",
            metadata={"purpose": "Lightweight coordinate and distance context for MVP demo sites."},
        )

    def _derived_source(self) -> SourceRecord:
        return SourceRecord(
            source_id="src_system_derived_missing_information",
            display_name="System-derived missing information evidence",
            source_type="derived",
            source_subtype="missing_information",
            modality="derived_text",
            authority="system_derived",
            commune=None,
            language="en",
            parser="rule_based",
            status="available",
            metadata={"purpose": "Derived evidence records that summarize missing information from validated dossier output."},
        )
