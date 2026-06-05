from app.models.evaluation import EvaluationFailure, SemanticEvaluationCase
from app.models.schemas import Dossier


def compute_semantic_metrics(case: SemanticEvaluationCase, dossier: Dossier) -> tuple[dict[str, object], list[EvaluationFailure]]:
    failures: list[EvaluationFailure] = []
    expectation = case.semantic_expectations.absence_to_risk
    text = dossier_text(dossier)
    matrix_by_category = {item.category_id: item for item in dossier.readiness_matrix}
    matrix_item = matrix_by_category.get(expectation.category_id)

    absence_to_risk_violation_count = phrase_count(text, expectation.forbidden_meanings)
    forbidden_semantic_claims = absence_to_risk_violation_count
    allowed_meaning_coverage = 1.0 if any_phrase(text, expectation.allowed_meanings_any) else 0.0
    required_limitations_present = all(any(phrase.lower() in limitation.lower() for limitation in dossier.limitations) for phrase in case.semantic_expectations.required_limitations)

    metrics: dict[str, object] = {
        "absence_to_risk_violation_count": absence_to_risk_violation_count,
        "forbidden_semantic_claims": forbidden_semantic_claims,
        "allowed_meaning_coverage": allowed_meaning_coverage,
        "required_limitations_present": required_limitations_present,
        "generation_mode": dossier.usage.generation_mode if dossier.usage else None,
        "external_llm_called": dossier.usage.external_llm_called if dossier.usage else None,
        "total_tokens_estimated": dossier.usage.total_tokens_estimated if dossier.usage else None,
        "total_tokens_reported": dossier.usage.total_tokens_reported if dossier.usage else None,
        "usage_source": dossier.usage.usage_source if dossier.usage else None,
    }

    if expectation.missing_status_required:
        actual_status = matrix_item.status if matrix_item else None
        if actual_status != "missing":
            failures.append(
                EvaluationFailure(
                    metric="semantic_missing_status_required",
                    expected="missing",
                    actual=actual_status,
                    message=f"{expectation.category_id} must be missing for this semantic case.",
                )
            )
    if absence_to_risk_violation_count:
        failures.append(
            EvaluationFailure(
                metric="absence_to_risk_violation_count",
                expected=0,
                actual=absence_to_risk_violation_count,
                message="Missing evidence was converted into a forbidden risk or approval meaning.",
            )
        )
    if forbidden_semantic_claims:
        failures.append(
            EvaluationFailure(
                metric="forbidden_semantic_claims",
                expected=0,
                actual=forbidden_semantic_claims,
                message="Forbidden semantic claim detected.",
            )
        )
    if not required_limitations_present:
        failures.append(
            EvaluationFailure(
                metric="required_limitations_present",
                expected=True,
                actual=False,
                message="Required limitation wording is missing.",
            )
        )
    return metrics, failures


def dossier_text(dossier: Dossier) -> str:
    return " ".join(
        [
            dossier.building_summary,
            dossier.public_context,
            " ".join(dossier.limitations),
            " ".join(item.summary for item in dossier.readiness_matrix),
            " ".join(item.recommended_next_action for item in dossier.readiness_matrix),
            " ".join(item.description for item in dossier.technical_risk_signals),
            " ".join(item.task for item in dossier.inspection_checklist),
            " ".join(item.reason for item in dossier.inspection_checklist),
            " ".join(item.description for item in dossier.missing_information_checklist),
            " ".join(item.recommended_next_action for item in dossier.missing_information_checklist),
        ]
    ).lower()


def any_phrase(text: str, phrases: list[str]) -> bool:
    return any(phrase.lower() in text for phrase in phrases)


def phrase_count(text: str, phrases: list[str]) -> int:
    return sum(1 for phrase in phrases if phrase.lower() in text)
