import json
from pathlib import Path

from app.services import document_upload, planning_ingestion
from app.services.document_parser import PageText
from app.services.evidence_metadata import read_upload_metadata
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
        return [PageText(page=1, text="Planning constraints for renovation.")]

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
        lambda path: [PageText(page=1, text="Planning constraints for renovation.")],
    )

    chunks = PlanningIngestionService(sources_path=sources_path).load_planning_chunks_for_commune("Testville")

    assert chunks
