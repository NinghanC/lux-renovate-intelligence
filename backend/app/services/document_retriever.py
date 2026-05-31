import json
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.core.paths import PROCESSED_DIR, PROCESSED_UPLOADS_DIR
from app.models.schemas import EvidenceObject, EvidenceType, PlanningChunk, RetrievedEvidence
from app.services.embedding_provider import EmbeddingProvider, cosine_similarity
from app.services.json_store import read_jsonl
from app.services.rerank_provider import RerankProvider


PLANNING_CHUNKS_PATH = PROCESSED_DIR / "planning_chunks.jsonl"
PLANNING_EMBEDDINGS_PATH = PROCESSED_DIR / "planning_embeddings.jsonl"


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return [token for token in re.findall(r"[a-z0-9_]{3,}", normalized) if token]


class DocumentRetriever:
    def __init__(
        self,
        chunks_path: Path = PLANNING_CHUNKS_PATH,
        uploads_dir: Path = PROCESSED_UPLOADS_DIR,
        embeddings_path: Path = PLANNING_EMBEDDINGS_PATH,
        embedding_provider: EmbeddingProvider | None = None,
        rerank_provider: RerankProvider | None = None,
    ):
        self.chunks_path = chunks_path
        self.uploads_dir = uploads_dir
        self.embeddings_path = embeddings_path
        self.embedding_provider = embedding_provider or EmbeddingProvider()
        self.rerank_provider = rerank_provider or RerankProvider()

    def load_chunks(self, include_uploaded: bool = True) -> list[PlanningChunk]:
        chunks = read_jsonl(self.chunks_path, PlanningChunk)
        if include_uploaded and self.uploads_dir.exists():
            for path in sorted(self.uploads_dir.glob("*.jsonl")):
                chunks.extend(read_jsonl(path, PlanningChunk))
        return chunks

    def _load_embeddings(self) -> dict[str, list[float]]:
        if not self.embeddings_path.exists():
            return {}
        embeddings: dict[str, list[float]] = {}
        with self.embeddings_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    embeddings[row["chunk_id"]] = row["embedding"]
        return embeddings

    def retrieve(
        self,
        *,
        commune: str,
        query: str,
        limit: int = 8,
        include_uploaded: bool = True,
        site_id: str | None = None,
    ) -> RetrievedEvidence:
        chunks = self.load_chunks(include_uploaded=include_uploaded)
        filtered = [
            chunk
            for chunk in chunks
            if chunk.commune.lower() == commune.lower()
            or chunk.metadata.get("site_id") in {site_id, "global"}
            or chunk.document_type == "uploaded"
        ]
        if not filtered:
            return RetrievedEvidence(
                query=query,
                results=[],
                limitations=[f"No indexed planning or uploaded evidence found for commune '{commune}'."],
            )

        return self.retrieve_from_chunks(
            chunks=filtered,
            commune=commune,
            query=query,
            limit=limit,
            use_precomputed_embeddings=True,
        )

    def retrieve_from_chunks(
        self,
        *,
        chunks: list[PlanningChunk],
        commune: str,
        query: str,
        limit: int = 8,
        use_precomputed_embeddings: bool = False,
    ) -> RetrievedEvidence:
        filtered = [
            chunk
            for chunk in chunks
            if chunk.commune.lower() == commune.lower() or chunk.document_type == "uploaded"
        ]
        if not filtered:
            return RetrievedEvidence(
                query=query,
                results=[],
                limitations=[f"No planning or uploaded evidence was available for commune '{commune}'."],
            )

        keyword_scores = self._keyword_scores(query, filtered)
        embedding_scores = self._embedding_scores(
            query,
            filtered,
            use_precomputed=use_precomputed_embeddings,
        )
        scored: list[tuple[float, PlanningChunk]] = []
        for chunk in filtered:
            keyword_score = keyword_scores.get(chunk.chunk_id, 0.0)
            embedding_score = embedding_scores.get(chunk.chunk_id, 0.0)
            combined = keyword_score if not embedding_scores else 0.65 * keyword_score + 0.35 * embedding_score
            if combined > 0:
                scored.append((combined, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)

        limitations = []
        if not scored:
            limitations.append("No relevant evidence matched the query; no planning facts should be inferred.")
            return RetrievedEvidence(query=query, results=[], limitations=limitations)
        if not embedding_scores:
            limitations.append("Embedding retrieval is not configured or failed; keyword retrieval was used.")
        rerank_scores = self._rerank_scores(query, [chunk for _, chunk in scored[: max(limit * 4, 20)]], top_n=limit)
        if rerank_scores:
            reranked: list[tuple[float, PlanningChunk]] = []
            for original_score, chunk in scored[: max(limit * 4, 20)]:
                rerank_score = rerank_scores.get(chunk.chunk_id)
                if rerank_score is not None:
                    reranked.append((0.25 * original_score + 0.75 * rerank_score, chunk))
            reranked.sort(key=lambda item: item[0], reverse=True)
            scored = reranked + [item for item in scored if item[1].chunk_id not in rerank_scores]
        else:
            limitations.append("Rerank retrieval is not configured or failed; hybrid keyword/embedding scores were used.")

        results = [self._chunk_to_evidence(chunk, score=round(score, 4)) for score, chunk in scored[:limit]]
        return RetrievedEvidence(query=query, results=results, limitations=limitations)

    def _keyword_scores(self, query: str, chunks: list[PlanningChunk]) -> dict[str, float]:
        query_tokens = Counter(tokenize(query))
        if not query_tokens:
            return {}
        document_frequency: Counter[str] = Counter()
        chunk_tokens: dict[str, Counter[str]] = {}
        for chunk in chunks:
            tokens = Counter(tokenize(f"{chunk.document_name} {chunk.text}"))
            chunk_tokens[chunk.chunk_id] = tokens
            for token in tokens:
                document_frequency[token] += 1
        total_docs = max(len(chunks), 1)
        scores: dict[str, float] = {}
        for chunk in chunks:
            tokens = chunk_tokens[chunk.chunk_id]
            score = 0.0
            for token, query_weight in query_tokens.items():
                if token not in tokens:
                    continue
                idf = math.log(1 + (total_docs / (1 + document_frequency[token])))
                score += query_weight * tokens[token] * idf
            if score:
                scores[chunk.chunk_id] = score
        if scores:
            max_score = max(scores.values())
            scores = {key: value / max_score for key, value in scores.items()}
        return scores

    def _embedding_scores(
        self,
        query: str,
        chunks: list[PlanningChunk],
        *,
        use_precomputed: bool,
    ) -> dict[str, float]:
        if not self.embedding_provider.configured:
            return {}
        try:
            query_embedding = self.embedding_provider.embed_texts([query])[0]
            if use_precomputed:
                embeddings = self._load_embeddings()
            else:
                chunk_embeddings = self._embed_chunks_on_demand(chunks)
                embeddings = dict(zip([chunk.chunk_id for chunk in chunks], chunk_embeddings))
        except Exception:
            return {}
        if not embeddings:
            return {}
        scores: dict[str, float] = {}
        for chunk in chunks:
            embedding = embeddings.get(chunk.chunk_id)
            if not embedding:
                continue
            score = cosine_similarity(query_embedding, embedding)
            if score > 0:
                scores[chunk.chunk_id] = score
        if scores:
            min_score = min(scores.values())
            max_score = max(scores.values())
            if max_score > min_score:
                scores = {key: (value - min_score) / (max_score - min_score) for key, value in scores.items()}
        return scores

    def _embed_chunks_on_demand(self, chunks: list[PlanningChunk]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        batch_size = max(settings.embedding_batch_size, 1)
        for index in range(0, len(chunks), batch_size):
            batch = chunks[index : index + batch_size]
            embeddings.extend(self.embedding_provider.embed_texts([chunk.text for chunk in batch]))
        return embeddings

    def _rerank_scores(self, query: str, chunks: list[PlanningChunk], top_n: int) -> dict[str, float]:
        if not chunks:
            return {}
        try:
            return self.rerank_provider.rerank(
                query=query,
                chunks=chunks,
                top_n=min(top_n, settings.rerank_top_n),
            )
        except Exception:
            return {}

    def _chunk_to_evidence(self, chunk: PlanningChunk, score: float) -> EvidenceObject:
        evidence_type = EvidenceType.uploaded_document if chunk.document_type == "uploaded" else EvidenceType.planning_document
        return EvidenceObject(
            evidence_id=f"ev_{chunk.chunk_id}",
            evidence_type=evidence_type,
            source_name=chunk.document_name,
            source_path=chunk.source_path,
            source_url=chunk.source_url,
            page=chunk.page,
            chunk_id=chunk.chunk_id,
            content=chunk.text,
            metadata={"commune": chunk.commune, "document_type": chunk.document_type, **chunk.metadata},
            confidence="medium",
            score=score,
        )
