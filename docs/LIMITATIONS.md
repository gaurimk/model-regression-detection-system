# Known Limitations

An honest account of where this project is a solid v1, and where it would
need more work before being trusted as a production safety net.

## Dataset size and coverage

41 hand-written test cases is a reasonable seed for demonstrating the system,
not a mature evaluation suite. Real production usage should grow this to
several hundred cases over time, primarily by adding real failure cases from
production traffic (anonymized) as they're discovered — the dataset should
get *harder to fool* with every incident, not stay static.

## The LLM-as-judge is itself imperfect

Summary relevance is scored by asking a model to rate how well one summary
matches another on a 1–5 scale. This is a reasonable proxy, but it inherits
all the usual issues with LLM-as-judge scoring: it can be inconsistent
run-to-run at temperature > 0, it can be fooled by superficially plausible
but substantively wrong summaries, and it doesn't explain *why* it gave a
particular score beyond the number itself. Treat relevance scores as a
useful signal, not ground truth.

## No statistical confidence intervals

The current significance handling is a simple fixed-percentage threshold
("flag as warning if pass rate drops more than 3 percentage points"). With a
41-case dataset, a 3-percentage-point swing is roughly one or two flipped
cases — which is closer to noise than signal at this sample size. A more
rigorous version would compute a confidence interval on the pass-rate delta
(e.g., a binomial proportion test) and only alert when the drop is
statistically significant given the sample size, not just numerically above
a fixed cutoff.

## Latency and cost figures are indicative, not authoritative

`avg_latency_ms` measures wall-clock time for a single sequential run of the
test suite, not concurrent/production load. Async batching is explicitly
called out as a future improvement in the code comments (`eval_runner.py`)
and hasn't been implemented — for a large dataset this would matter a lot for
both CI runtime and getting a realistic latency figure.

## No automatic dataset versioning/diffing

Golden dataset changes (adding/removing/editing test cases) aren't
separately tracked from prompt changes. If you both change the dataset and
change the prompt in the same run, the diff can't cleanly attribute a
regression to one or the other. Git history on `data/golden_dataset.json`
partially covers this, but a purpose-built dataset version field (already
present as `dataset_version` in the JSON) isn't yet checked or surfaced in
the report.

## Single-environment assumption

The GitHub Actions workflow and Docker setup assume a single deployment
target. Multi-environment promotion (dev → staging → prod prompt rollout,
with different thresholds per environment) isn't modeled.
