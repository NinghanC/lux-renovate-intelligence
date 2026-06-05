# Tradeoffs

## Kept Simple

- JSON/JSONL instead of a database.
- Source-hash checked local planning chunk cache instead of a managed ingestion store.
- Purpose-based multilingual BM25 + optional embedding retrieval, without a separate vector database.
- A managed rerank provider can be used as an external rerank step instead of migrating the whole retrieval stack into a hosted vector-search product immediately.
- Local file uploads instead of object storage.
- Lightweight GeoJSON with coordinate distance only, not full GIS.
- First-pass deterministic readiness rules instead of a configurable policy engine.
- Minimal React UI focused on the workflow.

## Why

The take-home challenge values a complete and practical MVP over heavy infrastructure. The goal is to demonstrate problem framing, evidence handling, bounded AI use, and a working product loop.

## Accepted Limitations

- Generate can still be slower than a production stack because retrieval, embedding, rerank, and LLM generation happen after the click.
- PDF extraction quality depends on source PDF text quality.
- Demo sites are approximate and not official cadastral records.
- Readiness rules are intentionally simple and should be expanded with versioned policies before production use.
- The full AI flow depends on the configured LLM provider availability.
- Rerank depends on the selected provider's credentials, permissions, and model access when enabled.
- No production security or audit controls are implemented.
