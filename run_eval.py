#!/usr/bin/env python
"""
CLI entry point for the Model Regression Detection System.

Usage:
    python run_eval.py --prompt-version prompts/v1.yaml
    python run_eval.py --prompt-version prompts/v2.yaml --dataset data/golden_dataset.json

Wires together every phase of the pipeline:
    1. Load prompt + golden dataset
    2. Run the evaluation
    3. Compare against the last stored run (baseline)
    4. Check for slow drift across run history
    5. Render the HTML diff report
    6. Send a Slack alert (if configured)
    7. Save the run to history
    8. Exit non-zero if a critical regression was found (for CI gating)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.comparison import Severity, compare_runs
from src.drift import detect_drift
from src.eval_runner import run_evaluation
from src.report import render_html_report
from src.slack_alert import send_slack_alert
from src.storage import load_run_history, save_run

load_dotenv()


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LLM regression evaluation pipeline.")
    parser.add_argument(
        "--prompt-version",
        default="prompts/v1.yaml",
        help="Path to the prompt YAML file to evaluate.",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Path to the golden dataset JSON file. Defaults to config.yaml's dataset_path.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the pipeline config file.",
    )
    parser.add_argument(
        "--no-slack",
        action="store_true",
        help="Skip sending a Slack alert even if SLACK_WEBHOOK_URL is set.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    dataset_path = args.dataset or config["dataset_path"]
    # NOTE: runs are stored in a single shared history (not split per prompt
    # version) because the entire point of this pipeline is to diff a new
    # prompt/model against whatever the last run was -- including runs from
    # a different prompt version. Splitting by version would make the
    # comparison engine always see an empty baseline.
    runs_dir = Path(config["runs_dir"])
    reports_dir = Path(config["reports_dir"])
    thresholds = config["thresholds"]
    drift_cfg = config["drift"]
    judge_cfg = config["judge"]

    print(f"→ Running evaluation for prompt '{args.prompt_version}' against '{dataset_path}'...")
    run = run_evaluation(
        prompt_path=args.prompt_version,
        dataset_path=dataset_path,
        judge_passing_score=judge_cfg["passing_score"],
    )
    print(f"  Run ID: {run.run_id} | Pass rate: {run.pass_rate:.1%} ({len(run.scores)} cases)")

    history = load_run_history(runs_dir)
    baseline = history[-1] if history else None

    comparison = compare_runs(
        current=run,
        baseline=baseline,
        warning_delta_percent=thresholds["warning_delta_percent"],
        critical_delta_percent=thresholds["critical_delta_percent"],
    )

    full_history = history + [run]
    drift = detect_drift(
        full_history,
        window_size=drift_cfg["window_size"],
        min_rolling_pass_rate=drift_cfg["min_rolling_pass_rate"],
    )

    report_path = reports_dir / f"{run.prompt_version}_{run.run_id}.html"
    render_html_report(run, comparison, drift, full_history, report_path)
    latest_path = reports_dir / "latest_report.html"
    render_html_report(run, comparison, drift, full_history, latest_path)
    print(f"  Report written to {report_path}")

    if not args.no_slack:
        sent = send_slack_alert(run, comparison, drift, report_url=str(report_path.resolve()))
        print(f"  Slack alert {'sent' if sent else 'skipped (no webhook configured)'}")

    save_run(run, runs_dir)

    print(f"\n  Regressions: {len(comparison.regressions)} | Improvements: {len(comparison.improvements)}")
    print(f"  Severity: {comparison.severity.value.upper()}")
    if drift.drift_detected:
        print(f"  ⚠️  Slow drift detected: rolling pass rate {drift.rolling_pass_rate:.1%}")

    if comparison.severity == Severity.CRITICAL:
        print("\n✗ CRITICAL regression detected. Blocking merge.")
        return 1

    print("\n✓ Evaluation passed thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
