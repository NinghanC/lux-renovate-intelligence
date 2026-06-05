# Evaluation

The MVP includes an offline evaluation layer for deterministic regression checks and small semantic boundary checks. It is designed to run in mock mode without Databricks, AWS, OpenAI, or network access.

## Run

```powershell
$env:PYTHONPATH="backend"
.\.venv\Scripts\python.exe -m app.evaluation.runner --mode mock
```

The runner writes JSON reports to `data/evaluation/runs/`. Report outputs are ignored by git except for `.gitkeep`.

## Deterministic Layer

Deterministic cases live in `data/evaluation/cases/`.

The runner calls the same production services used by the app path:

- `SiteResolver`
- `PlanningIngestionService`
- `DocumentRetriever`
- `GeoJsonService`
- `build_context_evidence`
- `build_rule_matrix`
- `DossierGenerator`
- dossier validators and coverage calculation

Hard failures include:

- mock generation failure
- required source types missing
- required supports missing
- site or commune source mismatch above threshold
- expected matrix status mismatch
- locked matrix status or evidence refs changed
- available or partial matrix items without evidence refs
- coverage score inconsistent with the matrix
- ungrounded planning findings, risk signals, or checklist items
- forbidden final engineering/legal claims
- incomplete taxonomy
- incomplete derived missing-information evidence coverage

Soft metrics such as evidence count and source distribution are written to the report for inspection.

Evaluation reports also include generation usage fields from each dossier, including generation mode, whether an external LLM was called, token usage source, and total reported or estimated tokens. Mock-mode evaluation expects no external LLM call and zero external tokens.

The optional second-LLM semantic reviewer is disabled during the default mock evaluation run. Metrics still record semantic review status, whether the reviewer made an external LLM call, and reviewer token usage when enabled for real-LLM report-only runs.

## Semantic Layer

Semantic cases live in `data/evaluation/semantic_cases/`.

The first semantic regression checks that missing structural documentation is not converted into a risk or approval claim. Missing evidence may support wording such as requesting structural drawings or a survey. It must not become a statement that the building is unsafe, structurally sound, approved, or safe for occupancy.

The semantic layer starts with conservative phrase checks. The optional semantic reviewer can add report-only LLM review notes for overclaiming, unsupported interpretations, grounding issues, and absence-of-evidence-to-risk mistakes. It should be manually reviewed, not treated as an authoritative CI gate.

## Limitations

The MVP evaluation layer does not certify engineering correctness.
It does not validate legal or planning interpretation.
It does not replace SECO engineer review.
It does not measure production model drift.
It does not yet use human expert labels.
Real LLM evaluation is optional and should be reviewed manually, not used as a CI hard failure.

Token usage in real LLM evaluation, including optional semantic-review usage, is a soft observability metric. The MVP does not enforce token budgets or estimate provider cost.
