"""
Unit tests covering the core logic: the mock classifier, the eval
runner, the comparison/diff engine, and drift detection. These run
fully offline (no API key required) via MockClient.
"""
from src.comparison import Severity, compare_runs
from src.drift import detect_drift
from src.eval_runner import load_dataset, load_prompt, run_evaluation
from src.llm_feature import MockClient
from src.models import CaseScore, EvalRun, FeatureOutput, TestCase


def make_test_case(**overrides) -> TestCase:
    defaults = dict(
        id="t1",
        input_email="I was charged twice for my subscription this month.",
        expected_category="billing",
        expected_summary="Customer was double-charged for their subscription.",
        difficulty="easy",
    )
    defaults.update(overrides)
    return TestCase(**defaults)


def make_score(case_id: str, passed: bool, summary: str = "output") -> CaseScore:
    case = make_test_case(id=case_id)
    return CaseScore(
        case_id=case_id,
        category_match=passed,
        relevance_score=5 if passed else 1,
        passed=passed,
        latency_ms=10.0,
        input_tokens=5,
        output_tokens=5,
        raw_output=FeatureOutput(category="billing", summary=summary),
        expected=case,
    )


def test_dataset_loads_and_is_nonempty():
    dataset = load_dataset("data/golden_dataset.json")
    assert len(dataset) >= 30
    ids = [c.id for c in dataset]
    assert len(ids) == len(set(ids)), "test case IDs must be unique"


def test_prompt_loads():
    prompt = load_prompt("prompts/v1.yaml")
    assert prompt.version == "v1"
    assert "customer support" in prompt.system_prompt.lower()


def test_mock_classifier_classifies_billing_email():
    client = MockClient()
    from src.models import PromptConfig

    prompt = PromptConfig(
        version="test", timestamp="now", system_prompt="be accurate", model="mock"
    )
    output, in_tok, out_tok = client.classify(
        "I was charged twice for my subscription, please refund me.", prompt
    )
    assert output.category == "billing"
    assert in_tok > 0


def test_full_evaluation_run_with_mock_client_produces_scores():
    run = run_evaluation(
        prompt_path="prompts/v1.yaml",
        dataset_path="data/golden_dataset.json",
        client=MockClient(),
    )
    assert isinstance(run, EvalRun)
    assert len(run.scores) >= 30
    assert 0.0 <= run.pass_rate <= 1.0


def test_comparison_flags_regression():
    baseline = EvalRun(
        run_id="base",
        prompt_version="v1",
        model="mock",
        scores=[make_score("a", True), make_score("b", True)],
    )
    current = EvalRun(
        run_id="curr",
        prompt_version="v2",
        model="mock",
        scores=[make_score("a", True), make_score("b", False)],
    )
    result = compare_runs(current, baseline, warning_delta_percent=3, critical_delta_percent=8)
    assert result.has_regressions
    assert result.regressions[0].case_id == "b"
    assert result.severity in (Severity.WARNING, Severity.CRITICAL)


def test_comparison_with_no_baseline_is_ok():
    current = EvalRun(run_id="curr", prompt_version="v1", model="mock", scores=[make_score("a", True)])
    result = compare_runs(current, None)
    assert result.severity == Severity.OK
    assert result.baseline_run_id is None


def test_drift_detects_slow_decline():
    history = [
        EvalRun(run_id=f"r{i}", prompt_version="v1", model="mock", scores=[make_score("a", i < 4)])
        for i in range(7)
    ]
    drift = detect_drift(history, window_size=7, min_rolling_pass_rate=0.90)
    assert drift.drift_detected is True


def test_drift_ok_when_all_passing():
    history = [
        EvalRun(run_id=f"r{i}", prompt_version="v1", model="mock", scores=[make_score("a", True)])
        for i in range(7)
    ]
    drift = detect_drift(history, window_size=7, min_rolling_pass_rate=0.90)
    assert drift.drift_detected is False
