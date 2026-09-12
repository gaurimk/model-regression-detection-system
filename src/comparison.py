"""
Phase 3 (part 2): the comparison engine.

The core value of this system is diffing: given a new run and the most
recent previous run, what changed? This module computes deltas, flags
regressions/improvements at the individual test-case level, and applies
configurable significance thresholds so a 2-out-of-80 flip doesn't
trigger the same alarm as a 20-out-of-80 flip.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from .models import EvalRun


class Severity(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


class CaseFlip(BaseModel):
    case_id: str
    kind: str  # "regression" or "improvement"
    previous_passed: bool
    current_passed: bool
    previous_output: str
    current_output: str


class ComparisonResult(BaseModel):
    current_run_id: str
    baseline_run_id: str | None
    pass_rate_delta: float
    category_accuracy_delta: float
    avg_relevance_delta: float
    avg_latency_delta_ms: float
    regressions: list[CaseFlip]
    improvements: list[CaseFlip]
    severity: Severity

    @property
    def has_regressions(self) -> bool:
        return len(self.regressions) > 0


def compare_runs(
    current: EvalRun,
    baseline: EvalRun | None,
    warning_delta_percent: float = 3.0,
    critical_delta_percent: float = 8.0,
) -> ComparisonResult:
    if baseline is None:
        # First run ever -- nothing to diff against.
        return ComparisonResult(
            current_run_id=current.run_id,
            baseline_run_id=None,
            pass_rate_delta=0.0,
            category_accuracy_delta=0.0,
            avg_relevance_delta=0.0,
            avg_latency_delta_ms=0.0,
            regressions=[],
            improvements=[],
            severity=Severity.OK,
        )

    baseline_by_id = {s.case_id: s for s in baseline.scores}
    regressions: list[CaseFlip] = []
    improvements: list[CaseFlip] = []

    for score in current.scores:
        prev = baseline_by_id.get(score.case_id)
        if prev is None:
            continue  # new test case with no prior baseline to compare against
        if prev.passed and not score.passed:
            regressions.append(
                CaseFlip(
                    case_id=score.case_id,
                    kind="regression",
                    previous_passed=True,
                    current_passed=False,
                    previous_output=prev.raw_output.summary,
                    current_output=score.raw_output.summary,
                )
            )
        elif not prev.passed and score.passed:
            improvements.append(
                CaseFlip(
                    case_id=score.case_id,
                    kind="improvement",
                    previous_passed=False,
                    current_passed=True,
                    previous_output=prev.raw_output.summary,
                    current_output=score.raw_output.summary,
                )
            )

    pass_rate_delta = (current.pass_rate - baseline.pass_rate) * 100
    category_accuracy_delta = (current.category_accuracy - baseline.category_accuracy) * 100
    avg_relevance_delta = current.avg_relevance - baseline.avg_relevance
    avg_latency_delta_ms = current.avg_latency_ms - baseline.avg_latency_ms

    # A drop is a negative delta; severity is based on magnitude of decline only.
    decline = -pass_rate_delta
    if decline >= critical_delta_percent:
        severity = Severity.CRITICAL
    elif decline >= warning_delta_percent:
        severity = Severity.WARNING
    else:
        severity = Severity.OK

    return ComparisonResult(
        current_run_id=current.run_id,
        baseline_run_id=baseline.run_id,
        pass_rate_delta=pass_rate_delta,
        category_accuracy_delta=category_accuracy_delta,
        avg_relevance_delta=avg_relevance_delta,
        avg_latency_delta_ms=avg_latency_delta_ms,
        regressions=regressions,
        improvements=improvements,
        severity=severity,
    )
