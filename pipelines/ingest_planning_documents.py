from pathlib import Path

from app.core.paths import PROCESSED_DIR, RAW_PLANNING_DIR, SAMPLE_DIR, ensure_runtime_dirs
from app.services.document_parser import chunk_document, parse_document
from app.services.json_store import read_json, write_jsonl


SOURCES_PATH = SAMPLE_DIR / "planning_sources.json"
OUTPUT_PATH = PROCESSED_DIR / "planning_chunks.jsonl"


def main() -> None:
    ensure_runtime_dirs()
    all_chunks = []
    for source in read_json(SOURCES_PATH):
        path = RAW_PLANNING_DIR / source["local_filename"]
        if not path.exists():
            print(f"WARN missing {path}; run download_planning_documents.py or add the file manually")
            continue
        print(f"PARSE {path}")
        pages = parse_document(path)
        chunks = chunk_document(
            document_id=source["document_id"],
            source_id=f"src_{source['document_id']}",
            document_name=source["document_name"],
            document_type=source["document_type"],
            commune=source["commune"],
            source_path=path,
            source_url=source["url"],
            pages=pages,
            max_chars=1100,
        )
        all_chunks.extend(chunks)
        print(f"  {len(pages)} pages -> {len(chunks)} chunks")
    write_jsonl(OUTPUT_PATH, all_chunks)
    print(f"Wrote {len(all_chunks)} chunks to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

