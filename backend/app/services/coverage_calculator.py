from app.models.schemas import CoverageScore, ReadinessMatrixItem


def calculate_coverage(matrix: list[ReadinessMatrixItem]) -> CoverageScore:
    counts = {
        "available": 0,
        "partial": 0,
        "missing": 0,
        "unknown": 0,
        "not_applicable": 0,
    }
    for item in matrix:
        counts[item.status] += 1
    denominator = counts["available"] + counts["partial"] + counts["missing"] + counts["unknown"]
    if denominator == 0:
        score = 0
    else:
        score = round(((counts["available"] + 0.5 * counts["partial"]) / denominator) * 100)
    return CoverageScore(
        coverage_score=score,
        available=counts["available"],
        partial=counts["partial"],
        missing=counts["missing"],
        unknown=counts["unknown"],
        not_applicable=counts["not_applicable"],
    )

