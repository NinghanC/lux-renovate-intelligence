import argparse
from datetime import datetime, timezone
from pathlib import Path

from app.api.routes_dossiers import PURPOSE_QUERIES
from app.core.paths import DATA_DIR
from app.evaluation.metrics import compute_deterministic_metrics
from app.evaluation.report_writer import write_report
from app.evaluation.semantic_metrics import compute_semantic_metrics
from app.models.evaluation import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationMode,
    EvaluationRunReport,
    SemanticEvaluationCase,
)
from app.models.schemas import EvidenceObject
from app.services.context_evidence import build_context_evidence
from app.services.document_retriever import DocumentRetriever
from app.services.dossier_generator import DossierGenerator
from app.services.evidence_validator import validate_dossier
from app.services.geospatial import GeoJsonService
from app.services.json_store import read_json
from app.services.llm_provider import LLMProvider, MockLLMProvider
from app.services.planning_ingestion import PlanningIngestionService
from app.services.readiness_rule_engine import build_rule_matrix
from app.services.site_resolver import SiteResolver
from app.services.source_registry import SourceRegistry
from app.services.taxonomy import load_taxonomy


EVALUATION_DIR = DATA_DIR / "evaluation"
CASES_DIR = EVALUATION_DIR / "cases"
SEMANTIC_CASES_DIR = EVALUATION_DIR / "semantic_cases"


class DisabledProvider:
    configured = False

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding provider is disabled.")

    def rerank(self, *, query, chunks, top_n) -> dict[str, float]:
        return {}


def load_cases(cases_dir: Path = CASES_DIR) -> list[EvaluationCase]:
    return [EvaluationCase.model_validate(item) for item in _read_case_files(cases_dir)]


def load_semantic_cases(cases_dir: Path = SEMANTIC_CASES_DIR) -> list[SemanticEvaluationCase]:
    return [SemanticEvaluationCase.model_validate(item) for item in _read_case_files(cases_dir)]


def run_evaluation(
    *,
    mode: EvaluationMode = "mock",
    write_output: bool = True,
    cases_dir: Path = CASES_DIR,
    semantic_cases_dir: Path = SEMANTIC_CASES_DIR,
) -> EvaluationRunReport:
    results: list[EvaluationCaseResult] = []
    for case in load_cases(cases_dir):
        results.append(run_deterministic_case(case, mode=mode))
    for case in load_semantic_cases(semantic_cases_dir):
        results.append(run_semantic_case(case, mode=mode))

    passed = all(result.passed for result in results)
    report = EvaluationRunReport(
        run_id=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        passed=passed,
        summary={
            "cases_total": len(results),
            "cases_passed": sum(1 for result in results if result.passed),
            "cases_failed": sum(1 for result in results if not result.passed),
        },
        cases=results,
    )
    if write_output:
        write_report(report)
    return report


def run_deterministic_case(case: EvaluationCase, *, mode: EvaluationMode = "mock") -> EvaluationCaseResult:
    trace = generate_trace(case.inputs.site_id, query=case.inputs.query, include_uploaded=case.inputs.include_uploaded_documents, max_evidence=case.inputs.max_evidence, mode=mode)
    metrics, failures = compute_deterministic_metrics(
        case=case,
        retrieved_evidence=trace["retrieved_evidence"],
        evidence=trace["evidence"],
        rule_matrix=trace["rule_matrix"],
        dossier=trace["dossier"],
        source_registry=trace["source_registry"],
    )
    return EvaluationCaseResult(case_id=case.case_id, passed=not failures, failures=failures, metrics=metrics)


def run_semantic_case(case: SemanticEvaluationCase, *, mode: EvaluationMode = "mock") -> EvaluationCaseResult:
    trace = generate_trace(case.inputs.site_id, query=case.inputs.query, include_uploaded=case.inputs.include_uploaded_documents, max_evidence=case.inputs.max_evidence, mode=mode)
    metrics, failures = compute_semantic_metrics(case, trace["dossier"])
    return EvaluationCaseResult(case_id=case.case_id, passed=not failures, failures=failures, metrics=metrics)


def generate_trace(
    site_id: str,
    *,
    query: str | None,
    include_uploaded: bool,
    max_evidence: int,
    mode: EvaluationMode,
) -> dict[str, object]:
    source_registry = SourceRegistry()
    resolver = SiteResolver()
    ingestion = PlanningIngestionService()
    geojson_service = GeoJsonService()
    retriever = DocumentRetriever(
        embedding_provider=DisabledProvider(),
        rerank_provider=DisabledProvider(),
        source_registry=source_registry,
    )
    llm_provider = MockLLMProvider() if mode == "mock" else LLMProvider()
    generator = DossierGenerator(llm_provider=llm_provider, source_registry=source_registry)

    site_context = resolver.build_context(site_id)
    chunks = ingestion.load_generate_chunks(
        commune=site_context.commune,
        site_id=site_id,
        include_uploaded_documents=include_uploaded,
    )
    if query:
        retrieved = retriever.retrieve_from_chunks(
            chunks=chunks,
            commune=site_context.commune,
            query=query,
            limit=max_evidence,
            use_precomputed_embeddings=False,
        )
    else:
        retrieved = retriever.retrieve_for_purposes(
            chunks=chunks,
            commune=site_context.commune,
            purpose_queries=PURPOSE_QUERIES,
            limit_per_purpose=5,
            total_limit=max_evidence,
            use_precomputed_embeddings=False,
        )
    site_geojson = geojson_service.build_site_geojson(site_id=site_id, coordinates=site_context.coordinates)
    evidence: list[EvidenceObject] = [
        *retrieved.results,
        *build_context_evidence(site_context, site_geojson),
    ]
    taxonomy = load_taxonomy()
    rule_matrix = build_rule_matrix(site_context=site_context, evidence=evidence, taxonomy=taxonomy)
    dossier = generator.generate(site_context=site_context, evidence=evidence, taxonomy=taxonomy)
    validate_dossier(dossier, dossier.evidence, source_registry.list_sources())
    return {
        "site_context": site_context,
        "retrieved_evidence": retrieved.results,
        "evidence": evidence,
        "rule_matrix": rule_matrix,
        "dossier": dossier,
        "source_registry": source_registry,
    }


def _read_case_files(cases_dir: Path) -> list[dict]:
    if not cases_dir.exists():
        return []
    return [read_json(path) for path in sorted(cases_dir.glob("*.json"))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline dossier evaluation cases.")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    report = run_evaluation(mode=args.mode, write_output=not args.no_write_report)
    print(report.model_dump_json(indent=2))
    raise SystemExit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
