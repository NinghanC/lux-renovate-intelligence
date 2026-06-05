from collections import Counter

from app.models.evaluation import EvaluationCase, EvaluationFailure
from app.models.schemas import Dossier, EvidenceObject
from app.services.coverage_calculator import calculate_coverage
from app.services.evidence_validator import FORBIDDEN_PATTERNS
from app.services.readiness_rule_engine import RuleMatrixItem
from app.services.source_registry import SourceRegistry
from app.services.taxonomy import taxonomy_ids


def compute_deterministic_metrics(
    *,
    case: EvaluationCase,
    retrieved_evidence: list[EvidenceObject],
    evidence: list[EvidenceObject],
    rule_matrix: list[RuleMatrixItem],
    dossier: Dossier,
    source_registry: SourceRegistry,
) -> tuple[dict[str, object], list[EvaluationFailure]]:
    failures: list[EvaluationFailure] = []
    source_type_counts = dict(Counter(item.source_type or "unknown" for item in evidence))
    source_types = set(source_type_counts)
    matrix_by_category = {item.category_id: item for item in dossier.readiness_matrix}
    rule_by_category = {item.category_id: item for item in rule_matrix}
    metrics: dict[str, object] = {
        "retrieved_evidence_count": len(retrieved_evidence),
        "evidence_count": len(evidence),
        "source_type_counts": source_type_counts,
        "checklist_grounding_rate": grounding_rate([item.evidence_refs for item in dossier.inspection_checklist]),
        "risk_signal_grounding_rate": grounding_rate([item.evidence_refs for item in dossier.technical_risk_signals]),
        "planning_finding_grounding_rate": grounding_rate([item.evidence_refs for item in dossier.planning_findings]),
        "forbidden_claim_count": forbidden_claim_count(dossier),
        "taxonomy_complete": set(matrix_by_category) == taxonomy_ids(),
        "coverage_score_consistent": dossier.coverage_score == calculate_coverage(dossier.readiness_matrix),
        "missing_information_evidence_coverage": missing_information_evidence_coverage(dossier),
        "site_mismatch_count": site_mismatch_count(evidence, dossier.site_context.commune, source_registry),
    }

    retrieval = case.expectations.retrieval
    if len(retrieved_evidence) < retrieval.min_evidence:
        failures.append(
            failure("min_evidence", retrieval.min_evidence, len(retrieved_evidence), "Retrieved evidence count is below expectation.")
        )
    for source_type in retrieval.required_source_types:
        if source_type not in source_types:
            failures.append(
                failure("required_source_types", retrieval.required_source_types, sorted(source_types), f"Missing required source type: {source_type}")
            )
    supports = {support for item in evidence for support in item.supports}
    for support in retrieval.required_supports:
        if support not in supports:
            failures.append(failure("required_supports", retrieval.required_supports, sorted(supports), f"Missing required support: {support}"))
    if metrics["site_mismatch_count"] > retrieval.max_site_mismatch_count:
        failures.append(
            failure(
                "site_mismatch_count",
                retrieval.max_site_mismatch_count,
                metrics["site_mismatch_count"],
                "Evidence source commune mismatch count is too high.",
            )
        )

    for category_id, expectation in case.expectations.matrix.items():
        item = matrix_by_category.get(category_id)
        rule_item = rule_by_category.get(category_id)
        if item is None:
            failures.append(failure("matrix_category", category_id, None, f"Missing matrix category: {category_id}"))
            continue
        if expectation.status and item.status != expectation.status:
            failures.append(failure("matrix_status", expectation.status, item.status, f"Matrix status mismatch for {category_id}."))
        if expectation.forbidden_statuses and item.status in expectation.forbidden_statuses:
            failures.append(
                failure("matrix_forbidden_status", expectation.forbidden_statuses, item.status, f"Forbidden matrix status for {category_id}.")
            )
        if expectation.requires_evidence and not item.evidence_refs:
            failures.append(failure("matrix_evidence_refs", "non-empty", [], f"Matrix category {category_id} requires evidence refs."))
        if expectation.requires_next_action and not item.recommended_next_action.strip():
            failures.append(failure("matrix_next_action", "non-empty", "", f"Matrix category {category_id} requires next action."))
        if case.expectations.generation.locked_matrix_statuses and rule_item and item.status != rule_item.status:
            failures.append(failure("locked_matrix_status", rule_item.status, item.status, f"Locked matrix status changed for {category_id}."))
        if rule_item and item.evidence_refs != rule_item.evidence_refs:
            failures.append(
                failure("locked_matrix_evidence_refs", rule_item.evidence_refs, item.evidence_refs, f"Locked matrix evidence refs changed for {category_id}.")
            )

    generation = case.expectations.generation
    if len(dossier.inspection_checklist) < generation.min_inspection_items:
        failures.append(
            failure("min_inspection_items", generation.min_inspection_items, len(dossier.inspection_checklist), "Inspection checklist is too short.")
        )
    if generation.require_evidence_refs:
        require_grounding("checklist_grounding_rate", metrics["checklist_grounding_rate"], failures)
        require_grounding("risk_signal_grounding_rate", metrics["risk_signal_grounding_rate"], failures)
        require_grounding("planning_finding_grounding_rate", metrics["planning_finding_grounding_rate"], failures)
    if generation.forbid_final_claims and metrics["forbidden_claim_count"] != 0:
        failures.append(failure("forbidden_claim_count", 0, metrics["forbidden_claim_count"], "Forbidden final claim detected."))
    if generation.limitations_required and not dossier.limitations:
        failures.append(failure("limitations_required", "non-empty", [], "Dossier limitations are required."))
    if not metrics["taxonomy_complete"]:
        failures.append(failure("taxonomy_complete", True, False, "Readiness matrix does not match taxonomy."))
    if case.expectations.dossier.coverage_score_matches_matrix and not metrics["coverage_score_consistent"]:
        failures.append(failure("coverage_score_consistent", True, False, "Coverage score does not match matrix."))
    expected_missing_coverage = case.expectations.dossier.missing_information_evidence_coverage
    if float(metrics["missing_information_evidence_coverage"]) < expected_missing_coverage:
        failures.append(
            failure(
                "missing_information_evidence_coverage",
                expected_missing_coverage,
                metrics["missing_information_evidence_coverage"],
                "Missing matrix categories are not fully represented by derived missing-information evidence.",
            )
        )

    return metrics, failures


def grounding_rate(ref_lists: list[list[str]]) -> float:
    if not ref_lists:
        return 1.0
    return round(sum(1 for refs in ref_lists if refs) / len(ref_lists), 4)


def forbidden_claim_count(dossier: Dossier) -> int:
    import re

    text = dossier.model_dump_json()
    return sum(1 for pattern in FORBIDDEN_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE))


def missing_information_evidence_coverage(dossier: Dossier) -> float:
    missing_categories = {item.category_id for item in dossier.readiness_matrix if item.status in {"missing", "unknown"}}
    if not missing_categories:
        return 1.0
    derived_categories = {
        str(item.metadata.get("category_id"))
        for item in dossier.evidence
        if item.evidence_type == "derived_missing_information" and item.metadata.get("category_id")
    }
    return round(len(missing_categories & derived_categories) / len(missing_categories), 4)


def site_mismatch_count(evidence: list[EvidenceObject], expected_commune: str, source_registry: SourceRegistry) -> int:
    count = 0
    for item in evidence:
        if not item.source_id:
            continue
        source = source_registry.get_by_id(item.source_id)
        if source is None or source.commune is None:
            continue
        if source.commune.lower() != expected_commune.lower():
            count += 1
    return count


def require_grounding(metric: str, value: object, failures: list[EvaluationFailure]) -> None:
    if value != 1.0:
        failures.append(failure(metric, 1.0, value, f"{metric} is below 1.0."))


def failure(metric: str, expected: object | None, actual: object | None, message: str) -> EvaluationFailure:
    return EvaluationFailure(metric=metric, expected=expected, actual=actual, message=message)
