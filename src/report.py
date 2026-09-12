"""
Phase 4 (part 1): the HTML diff report.

Generates a single self-contained HTML file: run metadata, a summary
scorecard vs. baseline, a table of every regressed case (old vs. new
output side by side), and a trend chart across recent runs. No JS
framework or build step -- a small inline <script> renders the trend
chart so the report stays a single portable file.
"""
from __future__ import annotations

import json
from pathlib import Path

from .comparison import ComparisonResult, Severity
from .drift import DriftResult
from .models import EvalRun

SEVERITY_COLORS = {
    Severity.OK: "#16a34a",
    Severity.WARNING: "#d97706",
    Severity.CRITICAL: "#dc2626",
}

SEVERITY_LABELS = {
    Severity.OK: "PASS",
    Severity.WARNING: "WARNING",
    Severity.CRITICAL: "CRITICAL",
}


def _case_row(flip, kind_label: str, color: str) -> str:
    return f"""
    <tr>
      <td><code>{flip.case_id}</code></td>
      <td style="color:{color}; font-weight:600;">{kind_label}</td>
      <td>{flip.previous_output or '<em>(empty)</em>'}</td>
      <td>{flip.current_output or '<em>(empty)</em>'}</td>
    </tr>"""


def render_html_report(
    run: EvalRun,
    comparison: ComparisonResult,
    drift: DriftResult,
    run_history: list[EvalRun],
    out_path: str | Path,
) -> Path:
    severity_color = SEVERITY_COLORS[comparison.severity]
    severity_label = SEVERITY_LABELS[comparison.severity]

    regression_rows = "".join(
        _case_row(f, "REGRESSION", "#dc2626") for f in comparison.regressions
    )
    improvement_rows = "".join(
        _case_row(f, "IMPROVEMENT", "#16a34a") for f in comparison.improvements
    )

    trend_labels = json.dumps([r.run_id for r in run_history])
    trend_values = json.dumps([round(r.pass_rate * 100, 1) for r in run_history])

    drift_banner = ""
    if drift.drift_detected:
        drift_banner = f"""
        <div style="background:#fef3c7;border:1px solid #d97706;padding:12px 16px;border-radius:8px;margin-bottom:20px;">
          <strong>Slow drift warning:</strong> the {drift.window_size}-run rolling average pass rate
          is {drift.rolling_pass_rate:.1%}, below the configured floor of {drift.min_rolling_pass_rate:.1%}.
          No single run crossed a hard threshold, but quality is trending down over time.
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Eval Report — {run.prompt_version} — {run.run_id}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 32px; background: #f8fafc; color: #0f172a; }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .meta {{ color: #64748b; font-size: 14px; margin-bottom: 24px; }}
  .badge {{ display:inline-block; padding: 4px 12px; border-radius: 999px; color: white; font-weight: 700; font-size: 13px; background:{severity_color}; }}
  .cards {{ display:flex; gap:16px; flex-wrap:wrap; margin: 24px 0; }}
  .card {{ background:white; border:1px solid #e2e8f0; border-radius:10px; padding:16px 20px; flex:1; min-width:160px; }}
  .card .label {{ font-size:12px; color:#64748b; text-transform:uppercase; letter-spacing:0.04em; }}
  .card .value {{ font-size:24px; font-weight:700; margin-top:4px; }}
  table {{ width:100%; border-collapse: collapse; background:white; border-radius:10px; overflow:hidden; margin-bottom:32px; }}
  th, td {{ text-align:left; padding:10px 14px; border-bottom:1px solid #e2e8f0; font-size:13px; vertical-align:top; }}
  th {{ background:#f1f5f9; font-size:12px; text-transform:uppercase; color:#475569; }}
  section h2 {{ font-size:16px; margin-top:32px; }}
  canvas {{ background:white; border:1px solid #e2e8f0; border-radius:10px; padding:12px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Model Regression Report</h1>
  <div class="meta">
    Prompt version <strong>{run.prompt_version}</strong> · Model <strong>{run.model}</strong> ·
    Run <code>{run.run_id}</code> · {run.timestamp}
  </div>

  <span class="badge">{severity_label}</span>

  {drift_banner}

  <div class="cards">
    <div class="card"><div class="label">Pass Rate</div><div class="value">{run.pass_rate:.1%}</div></div>
    <div class="card"><div class="label">Pass Rate Δ</div><div class="value">{comparison.pass_rate_delta:+.1f} pp</div></div>
    <div class="card"><div class="label">Category Accuracy</div><div class="value">{run.category_accuracy:.1%}</div></div>
    <div class="card"><div class="label">Avg Relevance</div><div class="value">{run.avg_relevance:.2f}/5</div></div>
    <div class="card"><div class="label">Avg Latency</div><div class="value">{run.avg_latency_ms:.0f} ms</div></div>
    <div class="card"><div class="label">Total Tokens</div><div class="value">{run.total_tokens}</div></div>
  </div>

  <section>
    <h2>Regressed Cases ({len(comparison.regressions)})</h2>
    <table>
      <tr><th>Case ID</th><th>Type</th><th>Previous Output</th><th>Current Output</th></tr>
      {regression_rows or '<tr><td colspan="4"><em>No regressions detected.</em></td></tr>'}
    </table>
  </section>

  <section>
    <h2>Improved Cases ({len(comparison.improvements)})</h2>
    <table>
      <tr><th>Case ID</th><th>Type</th><th>Previous Output</th><th>Current Output</th></tr>
      {improvement_rows or '<tr><td colspan="4"><em>No improvements detected.</em></td></tr>'}
    </table>
  </section>

  <section>
    <h2>Pass Rate Trend (last {len(run_history)} runs)</h2>
    <canvas id="trend" width="900" height="220"></canvas>
  </section>
</div>

<script>
  const labels = {trend_labels};
  const values = {trend_values};
  const canvas = document.getElementById('trend');
  const ctx = canvas.getContext('2d');
  const pad = 40, w = canvas.width - pad * 2, h = canvas.height - pad * 2;
  ctx.strokeStyle = '#cbd5e1';
  ctx.beginPath(); ctx.moveTo(pad, pad); ctx.lineTo(pad, pad + h); ctx.lineTo(pad + w, pad + h); ctx.stroke();
  ctx.fillStyle = '#64748b'; ctx.font = '11px sans-serif';
  ctx.fillText('100%', 4, pad + 4); ctx.fillText('0%', 8, pad + h + 4);
  if (values.length > 1) {{
    ctx.strokeStyle = '#4f46e5'; ctx.lineWidth = 2; ctx.beginPath();
    values.forEach((v, i) => {{
      const x = pad + (i / (values.length - 1)) * w;
      const y = pad + h - (v / 100) * h;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }});
    ctx.stroke();
    values.forEach((v, i) => {{
      const x = pad + (i / (values.length - 1)) * w;
      const y = pad + h - (v / 100) * h;
      ctx.fillStyle = '#4f46e5';
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
    }});
  }}
</script>
</body>
</html>"""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path
