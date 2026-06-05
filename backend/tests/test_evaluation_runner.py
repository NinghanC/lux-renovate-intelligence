from app.evaluation.runner import load_cases, run_deterministic_case, run_evaluation


def test_deterministic_evaluation_cases_pass_in_mock_mode():
    cases = load_cases()

    assert {case.case_id for case in cases} == {
        "demo_lux_laangfur_basic",
        "demo_lux_custom_query",
    }
    for case in cases:
        result = run_deterministic_case(case, mode="mock")
        assert result.passed, result.failures


def test_evaluation_report_aggregates_cases_without_writing():
    report = run_evaluation(mode="mock", write_output=False)

    assert report.passed, report.cases
    assert report.summary["cases_total"] == 3
    assert report.summary["cases_failed"] == 0
