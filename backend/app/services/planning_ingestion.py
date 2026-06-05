import json
import logging
from pathlib import Path

from app.core.paths import PROCESSED_DIR, RAW_PLANNING_DIR, RAW_UPLOADS_DIR, SAMPLE_DIR
from app.models.schemas import PlanningChunk
from app.services.document_parser import chunk_document, parse_document
from app.services.evidence_metadata import (
    infer_upload_subtype,
    is_upload_metadata_path,
    normalize_upload_subtype,
    read_upload_metadata,
    upload_metadata_path,
    write_upload_metadata,
)
from app.services.json_store import read_json, read_jsonl, write_json, write_jsonl
from app.services.source_registry import checksum_sha256, source_id_for_document


SOURCES_PATH = SAMPLE_DIR / "planning_sources.json"
PLANNING_CACHE_DIR = PROCESSED_DIR / "planning_cache"
logger = logging.getLogger(__name__)


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
        for path in latest_upload_paths_for_site(site_id):
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
        for path in latest_upload_paths_for_site(site_id):
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
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Ignoring unreadable planning cache metadata at %s: %s", meta_path, exc)
            return None
        if not isinstance(meta, dict):
            logger.warning("Ignoring planning cache metadata with invalid shape at %s", meta_path)
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


def latest_upload_paths_for_site(site_id: str) -> list[Path]:
    """Return the active upload per original filename for one site."""
    if not RAW_UPLOADS_DIR.exists():
        return []
    manifest_paths = active_upload_manifest_paths_for_site(site_id)
    if manifest_paths is not None:
        return manifest_paths
    grouped: dict[str, Path] = {}
    for path in sorted(RAW_UPLOADS_DIR.glob("*")):
        if not path.is_file():
            continue
        if is_upload_metadata_path(path):
            continue
        if not path.name.startswith(f"{site_id}_"):
            continue
        metadata = read_upload_metadata(path)
        original_filename = str(metadata.get("original_filename") or _filename_without_upload_prefix(path, site_id))
        current = grouped.get(original_filename)
        if current is None or _upload_sort_key(path) > _upload_sort_key(current):
            grouped[original_filename] = path
    return sorted(grouped.values(), key=lambda path: path.name)


def register_active_upload(*, site_id: str | None, path: Path, replace_active: bool = False) -> None:
    site_key = site_id or "global"
    manifest = _read_active_upload_manifest()
    active = [] if replace_active else list(manifest.get(site_key, []))
    if path.name not in active:
        active.append(path.name)
    manifest[site_key] = active
    _write_active_upload_manifest(manifest)


def remove_active_upload_by_source_id(*, site_id: str, source_id: str) -> bool:
    manifest_path = _active_upload_manifest_path()
    if not manifest_path.exists():
        return False
    manifest = _read_active_upload_manifest()
    active = list(manifest.get(site_id, []))
    kept = []
    removed = False
    for filename in active:
        path = RAW_UPLOADS_DIR / filename
        document_source_id = None
        if path.exists() and path.is_file() and not is_upload_metadata_path(path):
            metadata = read_upload_metadata(path)
            document_source_id = str(metadata.get("source_id") or "")
        if not document_source_id:
            document_source_id = f"src_upload_{path.stem}"
        if document_source_id == source_id:
            removed = True
            continue
        kept.append(filename)
    manifest[site_id] = kept
    _write_active_upload_manifest(manifest)
    return removed


def update_active_upload_subtype(*, site_id: str, source_id: str, source_subtype: str) -> bool:
    path = _active_upload_path_by_source_id(site_id=site_id, source_id=source_id)
    if path is None:
        return False
    metadata = read_upload_metadata(path)
    metadata["source_subtype"] = normalize_upload_subtype(source_subtype, path.name)
    write_upload_metadata(path, metadata)
    return True


def active_upload_manifest_paths_for_site(site_id: str) -> list[Path] | None:
    manifest_path = _active_upload_manifest_path()
    if not manifest_path.exists():
        return None
    manifest = _read_active_upload_manifest()
    filenames = manifest.get(site_id, [])
    grouped: dict[str, Path] = {}
    for filename in filenames:
        path = RAW_UPLOADS_DIR / filename
        if not path.exists() or not path.is_file() or is_upload_metadata_path(path):
            continue
        metadata = read_upload_metadata(path)
        original_filename = str(metadata.get("original_filename") or _filename_without_upload_prefix(path, site_id))
        current = grouped.get(original_filename)
        if current is None or _upload_sort_key(path) > _upload_sort_key(current):
            grouped[original_filename] = path
    return sorted(grouped.values(), key=lambda path: path.name)


def _active_upload_path_by_source_id(*, site_id: str, source_id: str) -> Path | None:
    active_paths = active_upload_manifest_paths_for_site(site_id)
    if active_paths is None:
        active_paths = latest_upload_paths_for_site(site_id)
    for path in active_paths:
        document_source_id = None
        if path.exists() and path.is_file() and not is_upload_metadata_path(path):
            metadata = read_upload_metadata(path)
            document_source_id = str(metadata.get("source_id") or "")
        if not document_source_id:
            document_source_id = f"src_upload_{path.stem}"
        if document_source_id == source_id:
            return path
    return None


def _upload_sort_key(path: Path) -> tuple[float, str]:
    return (path.stat().st_mtime, path.name)


def _filename_without_upload_prefix(path: Path, site_id: str) -> str:
    prefix = f"{site_id}_upload_"
    if not path.name.startswith(prefix):
        return path.name
    remainder = path.name[len(prefix):]
    parts = remainder.split("_", 1)
    return parts[1] if len(parts) == 2 else path.name


def _active_upload_manifest_path() -> Path:
    return RAW_UPLOADS_DIR / ".active_uploads.json"


def _read_active_upload_manifest() -> dict[str, list[str]]:
    path = _active_upload_manifest_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable active upload manifest at %s: %s", path, exc)
        return {}
    if not isinstance(payload, dict):
        return {}
    manifest: dict[str, list[str]] = {}
    for site_id, filenames in payload.items():
        if isinstance(site_id, str) and isinstance(filenames, list):
            manifest[site_id] = [filename for filename in filenames if isinstance(filename, str)]
    return manifest


def _write_active_upload_manifest(manifest: dict[str, list[str]]) -> None:
    RAW_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    _active_upload_manifest_path().write_text(json.dumps(manifest, indent=2), encoding="utf-8")
