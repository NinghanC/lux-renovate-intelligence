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
- Retrieves evidence with keyword search + DashScope embeddings + DashScope rerank.
- Adds derived missing-information evidence to the evidence panel after dossier generation.
- Exposes FastAPI endpoints for sites, uploads, retrieval, dossier generation, and saved dossier lookup.
- Uses Alibaba Cloud Bailian/DashScope through its OpenAI-compatible API for structured dossier generation and optional embeddings.
- Validates schema, evidence references, taxonomy completeness, and forbidden final engineering claims.
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

The MVP also includes `data/sample/geospatial_context.json` for public-data-style site context. It explicitly marks building footprints as not verified, so the system does not infer cadastral or engineering facts from approximate coordinates.

## AI And Guardrails

The LLM is a bounded generation layer, not the source of truth. The backend sends site context, retrieved evidence, and a fixed 12-category taxonomy to the model and requires JSON output.

Validation checks:

- Pydantic schema validation;
- all `evidence_refs` must point to real evidence IDs;
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

Then edit `.env` with your Alibaba Cloud Bailian/DashScope API key. Defaults use:

- `LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `LLM_MODEL=qwen3.6-flash`
- `EMBEDDING_MODEL=text-embedding-v4`
- `RERANK_MODEL=qwen3-rerank`

Embedding and rerank settings are optional for startup, but required for the full Hybrid RAG + rerank flow.

## Data Pipeline

Download the planning PDFs:

```powershell
python -X utf8 pipelines\download_planning_documents.py
```

This creates:

- `data/raw/planning/*.pdf`

Generate now parses and chunks the raw PDFs on demand. The product flow does not depend on pre-chunked files.

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
- `POST /api/documents/upload`
- `GET /api/evidence?site_id=...&query=...`
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
- Keyword retrieval is the default because it works without external services.
- Embedding retrieval is abstracted behind `EmbeddingProvider`.
- Rerank is handled by DashScope `qwen3-rerank` through `RerankProvider`.
- The Generate endpoint runs the full pipeline on demand instead of reading a prebuilt chunk index.
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
- Add a managed vector index and retrieval evaluation set.
- Integrate SECO historical inspection reports, defect observations, photos, measurements, and project metadata.

## Three-Month Direction

The next version would add an internal Building Intelligence Layer: historical case retrieval, recurring defect pattern analytics, experience-enhanced inspection checklist generation, photo and measurement evidence ingestion, and human-reviewed report draft assistance.
