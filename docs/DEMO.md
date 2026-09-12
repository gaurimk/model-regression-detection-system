# Demo

A short walkthrough is more persuasive than any amount of README text —
this is a placeholder for that recording.

## What to show (suggested 3-minute script)

1. **The trigger** (~30s) — open `prompts/v2.yaml`, point out the one-line
   change (shorter summaries), save it.
2. **The run** (~30s) — run `python run_eval.py --prompt-version prompts/v2.yaml`
   in the terminal, narrate the console output as it appears: pass rate,
   regression count, severity.
3. **The Slack alert** (~30s) — switch to Slack, show the message landing in
   real time with the headline numbers and regressed case IDs.
4. **The report** (~60s) — open `reports/latest_report.html`, walk through
   the scorecard, the regressed-case table (old output vs. new output side
   by side), and the trend chart.
5. **The close** (~30s) — one sentence on why this matters: "this is the
   difference between finding out about a quality drop from a support
   ticket, versus finding out in Slack thirty seconds after the change was
   made."

## Once recorded

Replace this file's content with:

```markdown
# Demo

[Watch the 3-minute walkthrough](YOUR_LOOM_OR_VIDEO_URL_HERE)

<!-- Or embed a thumbnail image that links out, e.g.: -->
<!-- [![Demo video](screenshots/demo_thumbnail.png)](YOUR_VIDEO_URL_HERE) -->
```

and link it from the main README's table of contents.
