"""
Phase 4 (part 2): Slack alerting.

Sends a structured message to a Slack Incoming Webhook with pass/warn/fail
status, headline numbers, and a link to the full HTML diff report.
If SLACK_WEBHOOK_URL is not configured, this silently no-ops so the
pipeline still works for local development.
"""
from __future__ import annotations

import os

import requests

from .comparison import ComparisonResult, Severity
from .drift import DriftResult
from .models import EvalRun

SEVERITY_EMOJI = {
    Severity.OK: "✅",
    Severity.WARNING: "⚠️",
    Severity.CRITICAL: "🚨",
}


def build_slack_payload(
    run: EvalRun,
    comparison: ComparisonResult,
    drift: DriftResult,
    report_url: str | None = None,
) -> dict:
    emoji = SEVERITY_EMOJI[comparison.severity]
    headline = (
        f"{emoji} *{comparison.severity.value.upper()}* — prompt `{run.prompt_version}` — "
        f"{len(comparison.regressions)} regression(s) detected, "
        f"pass rate {run.pass_rate:.1%} "
        f"({comparison.pass_rate_delta:+.1f} pp vs. baseline)"
    )

    lines = [headline]
    if comparison.regressions:
        sample = ", ".join(f.case_id for f in comparison.regressions[:5])
        more = f" (+{len(comparison.regressions) - 5} more)" if len(comparison.regressions) > 5 else ""
        lines.append(f"Regressed cases: {sample}{more}")
    if drift.drift_detected:
        lines.append(
            f"🐌 Slow drift: {drift.window_size}-run rolling pass rate is "
            f"{drift.rolling_pass_rate:.1%}, below the {drift.min_rolling_pass_rate:.1%} floor."
        )
    if report_url:
        lines.append(f"Full report: {report_url}")

    return {"text": "\n".join(lines)}


def send_slack_alert(
    run: EvalRun,
    comparison: ComparisonResult,
    drift: DriftResult,
    report_url: str | None = None,
    webhook_url: str | None = None,
) -> bool:
    """Returns True if an alert was sent, False if skipped (no webhook configured)."""
    webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return False

    payload = build_slack_payload(run, comparison, drift, report_url)
    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()
    return True
