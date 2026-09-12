"""
Phase 4 (part 3): drift detection.

Per-run diffing catches sudden regressions, but misses slow, gradual
decline where each individual run only drops a fraction of a percent.
This module tracks a rolling average of pass rate across the last N
runs and fires a separate "slow drift" warning when that average falls
below a floor, even if no single run tripped a hard threshold.
"""
from __future__ import annotations

from pydantic import BaseModel

from .models import EvalRun


class DriftResult(BaseModel):
    window_size: int
    runs_considered: int
    rolling_pass_rate: float
    min_rolling_pass_rate: float
    drift_detected: bool


def detect_drift(
    run_history: list[EvalRun], window_size: int = 7, min_rolling_pass_rate: float = 0.90
) -> DriftResult:
    """
    `run_history` should be ordered oldest -> newest and include the
    current run as the last element.
    """
    window = run_history[-window_size:]
    if not window:
        return DriftResult(
            window_size=window_size,
            runs_considered=0,
            rolling_pass_rate=1.0,
            min_rolling_pass_rate=min_rolling_pass_rate,
            drift_detected=False,
        )

    rolling_pass_rate = sum(r.pass_rate for r in window) / len(window)
    drift_detected = rolling_pass_rate < min_rolling_pass_rate

    return DriftResult(
        window_size=window_size,
        runs_considered=len(window),
        rolling_pass_rate=rolling_pass_rate,
        min_rolling_pass_rate=min_rolling_pass_rate,
        drift_detected=drift_detected,
    )
