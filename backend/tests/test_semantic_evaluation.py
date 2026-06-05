from app.evaluation.runner import load_semantic_cases, run_semantic_case


def test_semantic_missing_structural_docs_case_passes_in_mock_mode():
    cases = load_semantic_cases()

    assert [case.case_id for case in cases] == ["semantic_missing_structural_docs"]
    result = run_semantic_case(cases[0], mode="mock")

    assert result.passed, result.failures
    assert result.metrics["absence_to_risk_violation_count"] == 0
    assert result.metrics["required_limitations_present"] is True
    assert result.metrics["generation_mode"] == "mock"
    assert result.metrics["external_llm_called"] is False
