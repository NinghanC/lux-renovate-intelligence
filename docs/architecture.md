# Architecture

## Local MVP Flow

1. Demo site selection loads a fixed `SiteContext`.
2. The UI waits; it does not pre-retrieve evidence.
3. When the user clicks Generate, planning chunks are loaded from a source-hash checked local cache when possible. Cache misses parse raw planning PDFs with PyMuPDF, and pages with too little extracted text can fall back to AWS Textract OCR.
4. Retrieval runs purpose-based queries for planning context, documentation gaps, technical risk, site inspection, and renovation constraints. Each query scores chunks with multilingual BM25 keyword relevance and optional embeddings.
5. Optional rerank reranks the strongest retrieval candidates when configured. The recommended local setup uses AWS Bedrock Cohere Rerank 3.5.
6. Retrieved chunks become source-aware `EvidenceObject` records. Site profile and lightweight GeoJSON context are also added as low-risk context evidence.
7. The LLM receives site context, evidence, and taxonomy, then returns a `DossierDraft`.
8. Validators check schema, required evidence refs for user-facing findings/checklists, source registry links, page ranges, taxonomy completeness, source-type support, and forbidden claims.
9. Evidence coverage score is calculated by code and the validated dossier is saved locally.

## Services

- `SiteResolver`: loads demo sites and creates site context.
- `DocumentParser`: extracts PDF/text and chunks it.
- `OCRProvider`: AWS Textract fallback for scanned PDF pages, with an optional Databricks vision endpoint path.
- `SourceRegistry`: registers planning PDFs, site profiles, uploaded documents, GeoJSON, and system-derived evidence.
- `GeoJsonService`: reads lightweight GeoJSON and calculates coordinate distances.
- `DocumentRetriever`: purpose-based multilingual BM25 + optional embedding retrieval and rerank orchestration.
- `RerankProvider`: optional AWS Bedrock Cohere Rerank 3.5 adapter.
- `LLMProvider`: OpenAI-compatible chat completion adapter for Databricks Serving Endpoints.
- `DossierGenerator`: prompt assembly, LLM call, and dossier assembly.
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

The model layer is configured through environment variables. The local MVP uses Databricks for LLM and embedding calls and AWS for rerank and OCR:

```env
LLM_PROVIDER=databricks
LLM_BASE_URL=https://dbc-c760812f-3e1e.cloud.databricks.com/serving-endpoints
LLM_MODEL=databricks-meta-llama-3-3-70b-instruct
EMBEDDING_BASE_URL=https://dbc-c760812f-3e1e.cloud.databricks.com/serving-endpoints
EMBEDDING_MODEL=your-databricks-embedding-endpoint
```

Real API tokens belong only in a local `.env` file.

AWS Bedrock rerank can be enabled with:

```env
RERANK_PROVIDER=aws_bedrock
RERANK_MODEL=cohere.rerank-v3-5:0
RERANK_AWS_REGION=us-east-1
OCR_PROVIDER=aws_textract
OCR_MODEL=aws-textract-detect-document-text
OCR_AWS_REGION=us-east-1
```
