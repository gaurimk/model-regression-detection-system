# Teams Ship Prompt Changes Blind. Here's a CI Pipeline That Fixes That.

## The problem

If you've shipped an LLM-powered feature, you've probably lived this: someone
tweaks a system prompt to fix one annoying edge case, the fix works — and three
other cases silently break. Nobody notices for days, sometimes weeks, until a
support ticket lands or a teammate says "hey, is it just me or did the bot get
worse?"

Traditional software has a whole discipline built around this exact failure
mode: continuous integration. You don't ship code without running the test
suite. But most teams building AI features have no equivalent for *model
behavior*. Prompts get edited like copy in a Google Doc — no versioning, no
regression tests, no alerting. The AI equivalent of "push straight to
production with no CI" is somehow the default, not the exception.

## The approach

This project treats a prompt (or a model swap) the same way a real CI
pipeline treats a code change: as something that must pass a test suite
before anyone trusts it.

Concretely:

1. **A golden dataset** — a hand-verified set of realistic inputs with known
   correct outputs, including deliberately nasty edge cases: typos, sarcasm,
   two emails that could plausibly belong to either of two categories,
   emails in another language, single-word messages with no real content.
2. **A test runner** that sends every case through the actual feature code —
   not a simulation of it — so what you're testing is exactly what runs in
   production.
3. **Multi-dimensional scoring** — category correctness, an LLM-as-judge
   score for summary relevance, latency, and token cost, because "did it
   look right" is not a rigorous bar.
4. **A diff engine** that compares the new run to the last one and reports,
   case by case, what flipped from passing to failing (a regression) or
   failing to passing (an improvement).
5. **Alerting that meets the team where they already are** — Slack, with the
   headline numbers and a link to a full report, not a dashboard nobody
   remembers to check.

## The design decision I'm proudest of: separating regressions from drift

Per-run diffing catches the dramatic failures — the prompt edit that tanks
accuracy from 94% to 60% in one shot. But it's blind to a subtler, more
common failure: **slow drift**, where each individual run only degrades by a
fraction of a percent. No single run trips a threshold. Three months later,
the feature is noticeably worse than it used to be, and there's no single
commit to point to as the cause.

So this system tracks two signals independently:

- **Per-run regression detection**, with configurable warning/critical
  thresholds, for sudden breaks.
- **A rolling average across the last N runs**, with its own floor, for slow
  decline that never crosses a hard line on any single day.

The two live in separate code paths (`comparison.py` and `drift.py`) on
purpose. Conflating them would mean picking one threshold that's either too
noisy for day-to-day changes or too insensitive to catch gradual rot. Keeping
them separate means each can be tuned for what it's actually good at
catching.

## What I'd do differently at scale

Forty-one test cases is a reasonable seed, not a mature eval suite. The real
value of a system like this compounds over time: every production failure
that slips through becomes a new golden-dataset entry, so the test suite gets
harder to fool with every incident. That discipline — treating eval data as
a living artifact, not a one-time deliverable — is the part most teams skip,
and it's the part that actually matters.
