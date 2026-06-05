import json
import os
from pathlib import Path

from app.services import document_upload, planning_ingestion
from app.services.document_parser import PageText
from app.services.evidence_metadata import read_upload_metadata
from app.services.evidence_metadata import write_upload_metadata
from app.services.planning_ingestion import PlanningIngestionService


def test_upload_subtype_metadata_is_used_by_generate_ingestion(tmp_path, monkeypatch):
    raw_uploads = tmp_path / "uploads"
    monkeypatch.setattr(document_upload, "RAW_UPLOADS_DIR", raw_uploads)
    monkeypatch.setattr(planning_ingestion, "RAW_UPLOADS_DIR", raw_uploads)
    monkeypatch.setattr(
        planning_ingestion,
        "parse_document",
        lambda path: [PageText(page=1, text="Fire strategy document with evacuation notes.")],
    )

    response = document_upload.save_and_chunk_upload(
        filename="fire_note.txt",
        content=b"Fire strategy document with evacuation notes.",
        site_id="demo_site",
        commune="Luxembourg",
        source_subtype="fire_safety_dossier",
    )
    uploaded_path = next(path for path in raw_uploads.iterdir() if path.suffix == ".txt")

    assert response.source_subtype == "fire_safety_dossier"
    assert read_upload_metadata(uploaded_path)["source_subtype"] == "fire_safety_dossier"

    chunks = PlanningIngestionService().load_uploaded_chunks(site_id="demo_site", commune="Luxembourg")

    assert chunks
    assert chunks[0].metadata["source_subtype"] == "fire_safety_dossier"


def test_load_uploaded_chunks_uses_latest_upload_per_original_filename(tmp_path, monkeypatch):
    raw_uploads = tmp_path / "uploads"
    monkeypatch.setattr(document_upload, "RAW_UPLOADS_DIR", raw_uploads)
    monkeypatch.setattr(planning_ingestion, "RAW_UPLOADS_DIR", raw_uploads)

    parsed_texts: list[str] = []

    def fake_parse(path: Path) -> list[PageText]:
        text = path.read_text(encoding="utf-8")
        parsed_texts.append(text)
        return [PageText(page=1, text=text)]

    monkeypatch.setattr(planning_ingestion, "parse_document", fake_parse)

    old_response = document_upload.save_and_chunk_upload(
        filename="condition_notes.txt",
        content=b"old upload should not be used",
        site_id="demo_site",
        commune="Luxembourg",
    )
    old_path = next(path for path in raw_uploads.iterdir() if old_response.document_id in path.name and path.suffix == ".txt")
    os.utime(old_path, (1, 1))
    os.utime(Path(f"{old_path}.meta.json"), (1, 1))

    new_response = document_upload.save_and_chunk_upload(
        filename="condition_notes.txt",
        content=b"new upload should be used",
        site_id="demo_site",
        commune="Luxembourg",
    )
    new_path = next(path for path in raw_uploads.iterdir() if new_response.document_id in path.name and path.suffix == ".txt")
    os.utime(new_path, (2, 2))
    os.utime(Path(f"{new_path}.meta.json"), (2, 2))

    other_site_response = document_upload.save_and_chunk_upload(
        filename="condition_notes.txt",
        content=b"other site should not be used",
        site_id="other_site",
        commune="Luxembourg",
    )
    other_path = next(path for path in raw_uploads.iterdir() if other_site_response.document_id in path.name and path.suffix == ".txt")
    os.utime(other_path, (3, 3))
    os.utime(Path(f"{other_path}.meta.json"), (3, 3))

    service = PlanningIngestionService()

    chunks = service.load_uploaded_chunks(site_id="demo_site", commune="Luxembourg")
    signature = service.uploaded_signature(site_id="demo_site", include_uploaded_documents=True)

    assert [chunk.text for chunk in chunks] == ["new upload should be used"]
    assert parsed_texts == ["new upload should be used"]
    assert [item["filename"] for item in signature] == [new_path.name]


def test_new_active_upload_manifest_ignores_stale_files_not_uploaded_in_current_case(tmp_path, monkeypatch):
    raw_uploads = tmp_path / "uploads"
    raw_uploads.mkdir()
    monkeypatch.setattr(document_upload, "RAW_UPLOADS_DIR", raw_uploads)
    monkeypatch.setattr(planning_ingestion, "RAW_UPLOADS_DIR", raw_uploads)

    stale_path = raw_uploads / "demo_site_upload_stale_preliminary_site_visit_notes.txt"
    stale_path.write_text("stale preliminary notes should not be used", encoding="utf-8")
    write_upload_metadata(
        stale_path,
        {
            "original_filename": "preliminary_site_visit_notes.txt",
            "site_id": "demo_site",
            "commune": "Luxembourg",
        },
    )

    monkeypatch.setattr(
        planning_ingestion,
        "parse_document",
        lambda path: [PageText(page=1, text=path.read_text(encoding="utf-8"))],
    )

    response = document_upload.save_and_chunk_upload(
        filename="sample_condition_observations.txt",
        content=b"fresh condition observations should be used",
        site_id="demo_site",
        commune="Luxembourg",
    )
    active_path = next(path for path in raw_uploads.iterdir() if response.document_id in path.name and path.suffix == ".txt")

    chunks = PlanningIngestionService().load_uploaded_chunks(site_id="demo_site", commune="Luxembourg")
    signature = PlanningIngestionService().uploaded_signature(site_id="demo_site", include_uploaded_documents=True)

    assert [chunk.document_name for chunk in chunks] == [active_path.name]
    assert [item["filename"] for item in signature] == [active_path.name]


def test_remove_active_upload_by_source_id_updates_manifest(tmp_path, monkeypatch):
    raw_uploads = tmp_path / "uploads"
    raw_uploads.mkdir()
    monkeypatch.setattr(document_upload, "RAW_UPLOADS_DIR", raw_uploads)
    monkeypatch.setattr(planning_ingestion, "RAW_UPLOADS_DIR", raw_uploads)

    first = document_upload.save_and_chunk_upload(
        filename="first.txt",
        content=b"first",
        site_id="demo_site",
        commune="Luxembourg",
    )
    second = document_upload.save_and_chunk_upload(
        filename="second.txt",
        content=b"second",
        site_id="demo_site",
        commune="Luxembourg",
    )

    removed = planning_ingestion.remove_active_upload_by_source_id(site_id="demo_site", source_id=first.source_id)

    assert removed is True
    assert [path.name for path in planning_ingestion.latest_upload_paths_for_site("demo_site")] == [
        next(path.name for path in raw_uploads.iterdir() if second.document_id in path.name and path.suffix == ".txt")
    ]


def test_update_active_upload_subtype_updates_metadata(tmp_path, monkeypatch):
    raw_uploads = tmp_path / "uploads"
    monkeypatch.setattr(document_upload, "RAW_UPLOADS_DIR", raw_uploads)
    monkeypatch.setattr(planning_ingestion, "RAW_UPLOADS_DIR", raw_uploads)

    response = document_upload.save_and_chunk_upload(
        filename="owner_note.txt",
        content=b"Owner says drawings may be available.",
        site_id="demo_site",
        commune="Luxembourg",
        source_subtype="owner_note",
    )
    active_path = next(path for path in raw_uploads.iterdir() if response.document_id in path.name and path.suffix == ".txt")

    updated = planning_ingestion.update_active_upload_subtype(
        site_id="demo_site",
        source_id=response.source_id or "",
        source_subtype="drawing_or_plan",
    )

    assert updated is True
    assert read_upload_metadata(active_path)["source_subtype"] == "drawing_or_plan"


def test_planning_cache_skips_second_pdf_parse(tmp_path, monkeypatch):
    raw_planning = tmp_path / "planning"
    cache_dir = tmp_path / "cache"
    sources_path = tmp_path / "planning_sources.json"
    raw_planning.mkdir()
    (raw_planning / "planning.pdf").write_bytes(b"%PDF-1.4\n% test placeholder")
    sources_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "test_pag",
                    "document_name": "Test PAG",
                    "document_type": "PAG",
                    "commune": "Testville",
                    "local_filename": "planning.pdf",
                    "url": "https://example.test/planning.pdf",
                }
            ]
        ),
        encoding="utf-8",
    )
    parse_calls: list[Path] = []

    def fake_parse(path: Path) -> list[PageText]:
        parse_calls.append(path)
        return [PageText(page=1, text="Planning constraints for mission preparation.")]

    monkeypatch.setattr(planning_ingestion, "RAW_PLANNING_DIR", raw_planning)
    monkeypatch.setattr(planning_ingestion, "PLANNING_CACHE_DIR", cache_dir)
    monkeypatch.setattr(planning_ingestion, "parse_document", fake_parse)

    service = PlanningIngestionService(sources_path=sources_path)
    first = service.load_planning_chunks_for_commune("Testville")
    second = service.load_planning_chunks_for_commune("Testville")

    assert len(parse_calls) == 1
    assert [chunk.chunk_id for chunk in second] == [chunk.chunk_id for chunk in first]


def test_planning_cache_ignores_corrupt_metadata(tmp_path, monkeypatch):
    raw_planning = tmp_path / "planning"
    cache_dir = tmp_path / "cache"
    sources_path = tmp_path / "planning_sources.json"
    raw_planning.mkdir()
    cache_dir.mkdir()
    (raw_planning / "planning.pdf").write_bytes(b"%PDF-1.4\n% test placeholder")
    (cache_dir / "testville_planning_chunks.jsonl").write_text("", encoding="utf-8")
    (cache_dir / "testville_planning_chunks.meta.json").write_text("{not json", encoding="utf-8")
    sources_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "test_pag",
                    "document_name": "Test PAG",
                    "document_type": "PAG",
                    "commune": "Testville",
                    "local_filename": "planning.pdf",
                    "url": "https://example.test/planning.pdf",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(planning_ingestion, "RAW_PLANNING_DIR", raw_planning)
    monkeypatch.setattr(planning_ingestion, "PLANNING_CACHE_DIR", cache_dir)
    monkeypatch.setattr(
        planning_ingestion,
        "parse_document",
        lambda path: [PageText(page=1, text="Planning constraints for mission preparation.")],
    )

    chunks = PlanningIngestionService(sources_path=sources_path).load_planning_chunks_for_commune("Testville")

    assert chunks
