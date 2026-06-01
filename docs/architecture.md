# Architecture

## Local MVP Flow

1. Demo site selection loads a fixed `SiteContext`.
2. The UI waits; it does not pre-retrieve evidence.
3. When the user clicks Generate, raw planning PDFs for the selected commune are parsed and chunked in memory. Text PDFs use PyMuPDF extraction; pages with too little extracted text can fall back to AWS Textract OCR.
4. Retrieval scores chunks with multilingual BM25 keyword relevance and optional embeddings.
5. Optional rerank reranks the strongest retrieval candidates when configured. The recommended local setup uses AWS Bedrock Cohere Rerank 3.5.
6. Retrieved chunks become source-aware `EvidenceObject` records.
7. The LLM receives site context, evidence, and taxonomy, then returns a `DossierDraft`.
8. Validators check schema, evidence refs, source registry links, page ranges, taxonomy completeness, source-type support, and forbidden claims.
9. Evidence coverage score is calculated by code and the validated dossier is saved locally.

## Services

- `SiteResolver`: loads demo sites and creates site context.
- `DocumentParser`: extracts PDF/text and chunks it.
- `OCRProvider`: AWS Textract fallback for scanned PDF pages, with an optional Databricks vision endpoint path.
- `SourceRegistry`: registers planning PDFs, uploaded documents, GeoJSON, and system-derived evidence.
- `GeoJsonService`: reads lightweight GeoJSON and calculates coordinate distances.
- `DocumentRetriever`: multilingual BM25 + optional embedding retrieval and rerank orchestration.
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
- `data/sample/demo_geospatial.geojson` for lightweight coordinate and distance context.

`data/processed/planning_chunks.jsonl` and `data/processed/planning_embeddings.jsonl` are optional debugging artifacts only. The product Generate flow parses raw PDFs on demand.

## Provider Configuration

The model layer is configured through environment variables. The local MVP uses Databricks for LLM and embedding calls and AWS for rerank and OCR:

```env
LLM_PROVIDER=databricks
LLM_BASE_URL=https://dbc-c760812f-3e1e.cloud.databricks.com/serving-endpoints
LLM_MODEL=databricks-meta-llama-3-3-70b-instruct
EMBEDDING_BASE_URL=https://dbc-c760812f-3e1e.cloud.databricks.com/serving-endpoints
EMBEDDING_MODEL=databricks-qwen3-embedding-0-6b
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
