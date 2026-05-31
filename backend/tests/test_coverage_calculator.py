from app.models.schemas import ReadinessMatrixItem
from app.services.coverage_calculator import calculate_coverage


def item(category_id: str, status: str) -> ReadinessMatrixItem:
    return ReadinessMatrixItem(
        category_id=category_id,
        label=category_id,
        status=status,
        summary="summary",
        evidence_refs=[],
        recommended_next_action="review",
    )


def test_coverage_score_is_rule_based():
    coverage = calculate_coverage(
        [
            item("a", "available"),
            item("b", "partial"),
            item("c", "missing"),
            item("d", "unknown"),
            item("e", "not_applicable"),
        ]
    )

    assert coverage.coverage_score == 38
    assert coverage.available == 1
    assert coverage.not_applicable == 1

