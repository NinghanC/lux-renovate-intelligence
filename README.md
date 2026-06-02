# LuxRenovate Intelligence

LuxRenovate Intelligence is a local MVP for the SECO take-home challenge. It generates an evidence-backed renovation readiness dossier for old-building renovation preparation in Luxembourg.

It is not a generic RAG chatbot. The system is site-centric and evidence-first: it retrieves public planning evidence and uploaded sample documents, asks an OpenAI-compatible LLM to produce structured JSON, validates the output, and shows the sources in a React UI.

## Problem And User

SECO engineers need to prepare for renovation, due diligence, or inspection work when old-building records are incomplete. The MVP helps an engineer understand:

- what public planning context is available;
- what project information is missing;
- which uncertainty signals need human review;
- what should be checked during the site inspection;
- which evidence supports each finding.

## What The MVP Does

- Provides 3 Luxembourg demo sites.
- Downloads and parses 4 official public planning PDFs from Luxembourg City, Diekirch, and Mamer.
- Runs document parsing, chunking, embedding retrieval, rerank, and generation when the user clicks Generate.
- Retrieves evidence with purpose-based multilingual BM25 keyword search, Databricks-compatible embeddings, and optional rerank.
- Maintains a source registry for planning PDFs, site profiles, uploaded documents, GeoJSON, and system-derived evidence.
- Adds source-aware evidence records with source ID, source subtype, modality, role, page locator, parser metadata, support categories, and retrieval score.
- Adds lightweight GeoJSON coordinate context and distance calculations without a full GIS stack.
- Adds derived missing-information evidence to the evidence panel after dossier generation.
- Exposes FastAPI endpoints for sites, uploads, retrieval, dossier generation, and saved dossier lookup.
- Uses Databricks Serving Endpoints for LLM and embedding calls, AWS Bedrock Cohere Rerank 3.5 for rerank, and AWS Textract for scanned-page OCR fallback.
- Validates schema, evidence references, source registry links, page ranges, taxonomy completeness, source-type support, and forbidden final engineering claims.
- Shows source type coverage so users can see whether a dossier is supported by official planning PDFs, uploads, site profile, geo context, or derived missing-information evidence.
- Shows the workflow in a React + TypeScript frontend.

## Out Of Scope

- No final structural safety decision.
- No final fire-safety approval.
- No legal or planning-compliance judgement.
- No energy certification.
- No SECO internal data.
- No customer confidential data.
- No production authentication, RBAC, audit logging, or enterprise vector database.

## Data Sources

The local MVP uses small public planning PDFs that are practical to download and parse:

- Ville de Luxembourg PAP Laangfur page: `https://www.vdl.lu/fr/la-ville/engagements-de-la-ville/developpement-urbain/pap/pap-laangfur`
- Diekirch PAG/PAP page: `https://diekirch.lu/fr/commune-de-diekirch/trouver-un-service/logement-propriete/plan-damenagement-general-pag`
- Mamer urbanisme page: `https://mamer.lu/urbanisme/`

The docs also reference larger production-grade sources such as data.public.lu PAG datasets, Geoportail API, BD-Adresses, and BD-L-BATI3D. The large PAG ZIP files are not required for the local MVP because some exceed hundreds of MB or more.

The MVP also includes `data/sample/geospatial_context.json` and `data/sample/demo_geospatial.geojson` for public-data-style site context. It explicitly marks building footprints as not verified, so the system does not infer cadastral or engineering facts from approximate coordinates.

## AI And Guardrails

The LLM is a bounded generation layer, not the source of truth. The backend sends site context, retrieved evidence, and a fixed 12-category taxonomy to the model and requires JSON output.

Validation checks:

- Pydantic schema validation;
- all `evidence_refs` must point to real evidence IDs;
- evidence must reference registered sources;
- evidence pages must stay inside registered source page ranges;
- planning claims must be backed by official planning sources;
- hard engineering categories cannot be marked available using only uploaded or derived evidence;
- all 12 taxonomy categories must be present;
- forbidden final claims are rejected;
- evidence coverage score is calculated by code from readiness-matrix statuses, not by the LLM;
- missing information checklist items are converted into `derived_missing_information` evidence for UI traceability.

Without `LLM_API_KEY`, dossier generation returns a clear configuration error. Retrieval, site context, uploads, and the UI still run.

## Setup

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm install
```

Create local environment variables:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your local Databricks token and AWS credentials. Defaults use Databricks + AWS:

- `LLM_BASE_URL=https://dbc-c760812f-3e1e.cloud.databricks.com/serving-endpoints`
- `LLM_MODEL=databricks-meta-llama-3-3-70b-instruct`
- `EMBEDDING_MODEL=your-databricks-embedding-endpoint`
- `RERANK_MODEL=cohere.rerank-v3-5:0`
- `OCR_MODEL=aws-textract-detect-document-text`

Embedding, rerank, and OCR settings are optional for startup. OCR is used only as a PDF fallback when normal text extraction returns too little text, which keeps ordinary text PDFs cheap to parse while supporting scanned sample documents.

Databricks Serving Endpoint example:

```env
LLM_PROVIDER=databricks
LLM_API_KEY=
LLM_BASE_URL=https://dbc-c760812f-3e1e.cloud.databricks.com/serving-endpoints
LLM_MODEL=databricks-meta-llama-3-3-70b-instruct
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=https://dbc-c760812f-3e1e.cloud.databricks.com/serving-endpoints
EMBEDDING_MODEL=your-databricks-embedding-endpoint
```

Do not commit real API tokens.
`EMBEDDING_API_KEY` can be left empty when embeddings use the same Databricks endpoint root as `LLM_BASE_URL`; the backend reuses `LLM_API_KEY` in that case.

AWS rerank and OCR example:

```env
RERANK_PROVIDER=aws_bedrock
RERANK_MODEL=cohere.rerank-v3-5:0
RERANK_AWS_REGION=us-east-1
OCR_PROVIDER=aws_textract
OCR_MODEL=aws-textract-detect-document-text
OCR_AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
```

## Data Pipeline

Download the planning PDFs:

```powershell
python -X utf8 pipelines\download_planning_documents.py
```

This creates:

- `data/raw/planning/*.pdf`

Generate uses a source-hash checked planning chunk cache when available. If the cache is missing or stale, the backend parses and chunks the raw planning PDFs and writes a fresh local cache.

The optional ingestion script can still generate `data/processed/planning_chunks.jsonl` as an audit/debug artifact:

```powershell
python -X utf8 pipelines\ingest_planning_documents.py
```

Synthetic upload examples are available in `data/sample/upload_examples/` for testing the local upload flow without real client data. Upload one of those files from the UI, then click Generate and inspect the uploaded-document evidence.

## Run Locally

Start backend:

```powershell
uvicorn app.main:app --app-dir backend --reload --port 8000
```

Start frontend:

```powershell
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

## API

- `GET /health`
- `GET /api/sites`
- `GET /api/sites/{site_id}/context`
- `GET /api/sites/{site_id}/geojson`
- `POST /api/documents/upload`
- `GET /api/evidence?site_id=...&query=...`
- `GET /api/sources`
- `GET /api/sources/{source_id}/file`
- `POST /api/dossiers/generate`
- `GET /api/dossiers/{dossier_id}`

## Tests

```powershell
pytest
cd frontend
npm run build
```

## Technical Decisions

- FastAPI and Pydantic keep the API typed and easy to validate.
- Local JSON/JSONL keeps the MVP reproducible and reviewable.
- PyMuPDF is enough for public PDF text extraction.
- AWS Textract is used as a scanned-PDF fallback, not as the default parser for every document.
- Multilingual BM25 keyword retrieval is the default because it works without external services and handles mixed French, German, Dutch, and English terminology better than plain English keyword matching.
- Embedding retrieval is abstracted behind `EmbeddingProvider`.
- Rerank is handled through `RerankProvider`. The local recommended setup uses AWS Bedrock Cohere Rerank 3.5 after multilingual BM25 + Databricks embedding retrieval.
- Source registry and source-aware evidence schema make citations auditable before moving to database-backed infrastructure. Public source APIs use `source_id`, not local filesystem paths.
- GeoJSON distance context is intentionally lightweight: coordinates and Haversine distance only, not cadastral or engineering inference.
- The Generate endpoint runs the full retrieval/generation/validation flow on demand while reusing validated planning chunk caches when source files are unchanged.
- The evidence coverage score is not a regulatory, risk, safety, or compliance score.
- The UI is a product workspace, not a landing page.

## What Would Be Kept In Production

- Site-centric workflow.
- Evidence object model.
- Fixed readiness taxonomy.
- Bounded AI generation.
- Evidence and forbidden-claim validators.
- Human-in-the-loop positioning.

## What Would Be Rebuilt In Production

- Replace local JSON with PostgreSQL/PostGIS and object storage.
- Replace local upload storage with governed document storage.
- Add RBAC, audit logs, prompt/evidence logging, and data retention.
- Use production OCR for scanned drawings and reports.
- Add a managed vector index and a dedicated evaluation layer for retrieval quality, generation regression checks, and golden dossier comparisons.
- Integrate SECO historical inspection reports, defect observations, photos, measurements, and project metadata.

## Three-Month Direction

The next version would add an internal Building Intelligence Layer: historical case retrieval, recurring defect pattern analytics, experience-enhanced inspection checklist generation, photo and measurement evidence ingestion, and human-reviewed report draft assistance. A dedicated evaluation layer is deferred to this roadmap rather than included in the current MVP.
