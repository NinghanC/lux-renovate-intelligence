import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.paths import PROCESSED_DIR  # noqa: E402
from app.models.schemas import PlanningChunk  # noqa: E402
from app.services.document_retriever import PLANNING_CHUNKS_PATH, PLANNING_EMBEDDINGS_PATH  # noqa: E402
from app.services.embedding_provider import EmbeddingProvider  # noqa: E402
from app.services.json_store import read_jsonl  # noqa: E402


def batched(items: list[PlanningChunk], size: int = settings.embedding_batch_size):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def main() -> None:
    provider = EmbeddingProvider()
    chunks = read_jsonl(PLANNING_CHUNKS_PATH, PlanningChunk)
    if not chunks:
        raise SystemExit(f"No chunks found at {PLANNING_CHUNKS_PATH}. Run ingestion first.")
    if not provider.configured:
        print("Embedding provider is not configured; skipping embedding index build.")
        print("Keyword retrieval works without this file.")
        return

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with PLANNING_EMBEDDINGS_PATH.open("w", encoding="utf-8") as handle:
        for batch in batched(chunks):
            embeddings = provider.embed_texts([chunk.text for chunk in batch])
            for chunk, embedding in zip(batch, embeddings):
                handle.write(json.dumps({"chunk_id": chunk.chunk_id, "embedding": embedding}) + "\n")
    print(f"Wrote embeddings to {PLANNING_EMBEDDINGS_PATH}")


if __name__ == "__main__":
    main()
