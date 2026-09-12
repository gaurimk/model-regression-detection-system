# Architecture

This document goes one level deeper than the README's overview — it's aimed
at someone about to modify the code, not someone deciding whether to use the
project.

## Module map

```
src/
├── models.py        # Typed data contracts (PromptConfig, TestCase, EvalRun, etc.)
├── llm_feature.py    # The feature under test + LLMClient interface (OpenAI / Mock)
├── eval_runner.py     # Loads prompt + dataset, runs every case, scores it
├── comparison.py      # Diffs current run vs. previous baseline
├── drift.py           # Rolling-average drift detection across run history
├── storage.py         # JSON-based persistence for run history
├── report.py          # Self-contained HTML report generator
└── slack_alert.py     # Slack webhook integration

run_eval.py            # CLI entry point wiring all of the above together
```

Data flows in one direction: `eval_runner` produces an `EvalRun` →
`comparison` and `drift` each independently analyze it against history →
`report` and `slack_alert` each independently render the results. No module
downstream of `eval_runner` mutates the run itself; they only read it. This
makes it straightforward to add a new output (say, a Microsoft Teams
integration) without touching scoring or comparison logic at all.

## Why a shared run history, not one per prompt version

Early in development, run history was stored per prompt-version folder
(`runs/v1/`, `runs/v2/`). This was a bug: the entire point of the comparison
engine is to answer "did the *last* thing we tried work better or worse than
this new thing?" — and "the last thing we tried" is very often a *different*
prompt version. Splitting storage by version meant every new version's first
run had no baseline to compare against, silently defeating the diff engine.

The fix: `runs/` is a single flat history, ordered by timestamp, regardless
of which prompt produced each run. `run_eval.py`'s baseline lookup is just
"the most recent run, whatever version it was."

## Why regressions and drift are separate code paths

See [`docs/blog.md`](blog.md) for the full reasoning — in short, sudden
per-run regressions and slow multi-run decline require different math
(a single delta vs. a rolling average) and different thresholds. Keeping
`comparison.py` and `drift.py` as independent modules that both consume an
`EvalRun`/history means each can be tuned or replaced without touching the
other.

## Why a MockClient exists alongside the real OpenAI client

`LLMClient` is an abstract interface with two implementations. `MockClient`
is not a testing stub that gets deleted before "real" use — it's a
permanent, deterministic, offline stand-in that makes the entire pipeline
(dataset, scoring, diffing, reporting, alerting, CI) runnable and
demonstrable with zero API cost and zero network dependency. This matters
for:

- Local development without burning API credits on every test run
- CI dry-runs on forks/PRs where secrets aren't available
- Onboarding a new contributor who wants to see the system work before
  configuring any credentials

Swapping to the real model is a one-line environment variable
(`OPENAI_API_KEY`) — no code changes, because both clients satisfy the same
interface.

## Extension points

- **New LLM provider**: implement `LLMClient` (see `llm_feature.py`) and
  update `get_client()`'s factory logic.
- **New notification channel** (e.g. Microsoft Teams, email): add a sibling
  module to `slack_alert.py` with the same `send_*_alert(run, comparison,
  drift, report_url)` signature, and call it from `run_eval.py`.
- **New scoring dimension**: extend `CaseScore` in `models.py`, populate it
  in `eval_runner.score_case`, and surface it in `report.py`'s scorecard.
- **Swap JSON storage for SQLite**: `storage.py` is the only module that
  touches the filesystem for run history — replacing its two functions
  (`save_run`, `load_run_history`) with SQL-backed equivalents requires no
  changes anywhere else.
