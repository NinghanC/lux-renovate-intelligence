# Architecture

## Local MVP Flow

1. Demo site selection loads a fixed `SiteContext`.
2. The UI waits; it does not pre-retrieve evidence.
3. When the user clicks Generate, planning chunks are loaded from a source-hash checked local cache when possible. Cache misses parse raw planning PDFs with PyMuPDF. Optional OCR can be configured for scanned PDFs, but the public demo does not require cloud OCR.
4. Retrieval runs purpose-based queries for public authorization context, documentation gaps, technical systems, expert validation, and mission preparation. Each query scores chunks with multilingual BM25 keyword relevance and optional embeddings.
5. Optional rerank reranks the strongest retrieval candidates when configured. The public demo keeps rerank disabled and uses local keyword retrieval by default.
6. Retrieved chunks become source-aware `EvidenceObject` records. Site profile and lightweight GeoJSON context are also added as low-risk context evidence.
7. A deterministic readiness rule engine assigns matrix statuses and evidence references from the evidence objects before generation.
8. The default mock generator, or the configured LLM, receives site context, evidence, taxonomy, and the locked rule-derived matrix, then returns a `DossierDraft`.
9. Validators check schema, required evidence refs for user-facing findings/checklists, source registry links, page ranges, taxonomy completeness, source-type support, rule-derived matrix consistency, and forbidden claims.
10. Evidence coverage score is calculated by code and the validated dossier is saved locally.

## Services

- `SiteResolver`: loads demo sites and creates site context.
- `DocumentParser`: extracts PDF/text and chunks it.
- `OCRProvider`: optional OCR adapter for scanned PDF pages; disabled in the public demo.
- `SourceRegistry`: registers planning PDFs, site profiles, uploaded documents, GeoJSON, and system-derived evidence.
- `GeoJsonService`: reads lightweight GeoJSON and calculates coordinate distances.
- `DocumentRetriever`: purpose-based multilingual BM25 + optional embedding retrieval and rerank orchestration.
- `RerankProvider`: optional managed rerank adapter; disabled in the public demo.
- `MockLLMProvider`: deterministic demo generator for reviewer-friendly local runs without API keys.
- `LLMProvider`: OpenAI-compatible chat completion adapter for externally configured model endpoints.
- `ReadinessRuleEngine`: deterministic mission-readiness matrix status assignment and missing-information seeding.
- `DossierGenerator`: rule-matrix assembly, prompt assembly, LLM call, and dossier assembly.
- `EvidenceValidator`: guardrails, source integrity checks, and reference checks.
- `CoverageCalculator`: deterministic evidence-coverage metric based on matrix statuses.

## Storage

Local MVP storage is file-based:

- `data/sample/*.json` for static sample definitions.
- `data/raw/planning/*.pdf` for public PDFs.
- `data/raw/uploads/` and `data/processed/uploads/` for local sample uploads.
- `data/processed/dossiers/` for generated dossiers.
- `data/processed/source_registry.json` for the latest source registry snapshot.
- `data/processed/planning_cache/` for source-hash checked planning chunk caches.
- `data/sample/demo_geospatial.geojson` for lightweight coordinate and distance context.

`data/processed/planning_chunks.jsonl` and `data/processed/planning_embeddings.jsonl` are optional debugging artifacts only. The product Generate flow uses the planning cache above and refreshes it when raw source files change.

## Provider Configuration

The model layer is configured through environment variables. The default local and Docker Compose setup uses mock LLM generation so the Generate flow works without credentials:

```env
LLM_PROVIDER=mock
LLM_MOCK_MODE=true
```

For real external generation, use any OpenAI-compatible endpoint for LLM and optional embedding calls. Keep actual workspace hosts, model IDs, tokens, and cloud account details only in a local `.env`:

```env
LLM_PROVIDER=<your-openai-compatible-provider>
LLM_MOCK_MODE=false
LLM_BASE_URL=https://<your-provider-host>/<openai-compatible-path>
LLM_MODEL=<your-chat-model-or-serving-endpoint-name>
EMBEDDING_BASE_URL=https://<your-provider-host>/<embedding-path>
EMBEDDING_MODEL=<your-embedding-model-or-serving-endpoint-name>
```

Real API tokens belong only in a local `.env` file.

Optional cloud rerank and OCR providers can be enabled with provider-specific values:

```env
RERANK_PROVIDER=<your-rerank-provider>
RERANK_MODEL=<your-rerank-model-id-or-arn>
RERANK_AWS_REGION=<your-region-if-applicable>
OCR_PROVIDER=<your-ocr-provider>
OCR_MODEL=<your-ocr-model-or-provider-label>
OCR_AWS_REGION=<your-region-if-applicable>
```
