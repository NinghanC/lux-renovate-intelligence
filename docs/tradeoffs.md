# Tradeoffs

## Kept Simple

- JSON/JSONL instead of a database.
- On-demand parsing at Generate time instead of a prebuilt chunk index.
- Keyword + embedding retrieval with DashScope rerank, without a separate vector database.
- Local file uploads instead of object storage.
- Minimal React UI focused on the workflow.

## Why

The take-home challenge values a complete and practical MVP over heavy infrastructure. The goal is to demonstrate problem framing, evidence handling, bounded AI use, and a working product loop.

## Accepted Limitations

- Generate is slower because parsing, embedding, rerank, and LLM generation happen after the click.
- PDF extraction quality depends on source PDF text quality.
- Demo sites are approximate and not official cadastral records.
- The full AI flow depends on DashScope API availability.
- No production security or audit controls are implemented.
