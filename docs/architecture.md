# Architecture

## Local MVP Flow

1. Demo site selection loads a fixed `SiteContext`.
2. The UI waits; it does not pre-retrieve evidence.
3. When the user clicks Generate, raw planning PDFs for the selected commune are parsed and chunked in memory. Text PDFs use PyMuPDF extraction; pages with too little extracted text can fall back to Qwen-OCR.
4. Retrieval scores chunks with keyword relevance and DashScope embeddings.
5. DashScope `qwen3-rerank` reranks the strongest retrieval candidates.
6. Retrieved chunks become `EvidenceObject` records.
7. The LLM receives site context, evidence, and taxonomy, then returns a `DossierDraft`.
8. Validators check schema, evidence refs, taxonomy completeness, and forbidden claims.
9. Evidence coverage score is calculated by code and the validated dossier is saved locally.

## Services

- `SiteResolver`: loads demo sites and creates site context.
- `DocumentParser`: extracts PDF/text and chunks it.
- `OCRProvider`: Qwen-OCR fallback for scanned PDF pages.
- `DocumentRetriever`: keyword + embedding retrieval and rerank orchestration.
- `RerankProvider`: DashScope text rerank adapter.
- `LLMProvider`: Alibaba Cloud Bailian/DashScope OpenAI-compatible chat completion adapter.
- `DossierGenerator`: prompt assembly, LLM call, and dossier assembly.
- `EvidenceValidator`: guardrails and reference checks.
- `CoverageCalculator`: deterministic evidence-coverage metric based on matrix statuses.

## Storage

Local MVP storage is file-based:

- `data/sample/*.json` for static sample definitions.
- `data/raw/planning/*.pdf` for public PDFs.
- `data/raw/uploads/` and `data/processed/uploads/` for local sample uploads.
- `data/processed/dossiers/` for generated dossiers.

`data/processed/planning_chunks.jsonl` and `data/processed/planning_embeddings.jsonl` are optional debugging artifacts only. The product Generate flow parses raw PDFs on demand.
