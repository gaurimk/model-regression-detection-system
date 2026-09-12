# Changelog

All notable changes to this project, in reverse chronological order.

## [Unreleased]

### Added
- `docs/ARCHITECTURE.md` — module map and design-decision writeup for contributors.
- `docs/LIMITATIONS.md` — honest accounting of current gaps (dataset size, judge reliability, no confidence intervals, etc.).
- `docs/blog.md` — public-facing writeup of the problem, approach, and a key design decision.
- `docs/screenshots/` — real output screenshots (baseline report, regression report, Slack alerts) referenced from the main README.

### Fixed
- **Run history was being stored per prompt-version folder** (`runs/v1/`, `runs/v2/`), which meant switching prompt versions always compared against an empty baseline instead of the actual last run. Run history is now a single shared, timestamp-ordered store so cross-version diffing works as intended.

## [0.1.0] — Initial release

### Added
- Core evaluation pipeline: `PromptConfig`/`TestCase`/`EvalRun` data models, test runner, multi-dimensional scoring (category match, LLM-judged relevance, latency, tokens).
- `MockClient` offline classifier alongside a real `OpenAIClient`, selected automatically based on whether `OPENAI_API_KEY` is set.
- Comparison engine with configurable warning/critical pass-rate-delta thresholds.
- Drift detection via rolling N-run average pass rate.
- Self-contained HTML report generator with scorecard, regression/improvement tables, and a trend chart.
- Slack incoming-webhook alerting.
- GitHub Actions workflow that runs the eval on prompt-file PRs and can block merges.
- Dockerfile for containerized runs.
- Seed golden dataset (41 hand-written test cases across billing/technical/account/general categories, including deliberate edge cases).
- Unit test suite (`pytest`) covering scoring, comparison, and drift logic, runnable fully offline via `MockClient`.
