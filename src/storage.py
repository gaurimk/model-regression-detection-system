"""
Lightweight persistence: each EvalRun is stored as its own JSON file
under runs/<prompt_version>/<run_id>.json. This is the "SQLite + JSON
files" storage layer from the tech stack -- here implemented purely
with JSON for zero-dependency portability; swap in SQLite if the
dataset/run history grows large enough to need querying.
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import EvalRun


def save_run(run: EvalRun, runs_dir: str | Path) -> Path:
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    out_path = runs_dir / f"{run.run_id}.json"
    out_path.write_text(run.model_dump_json(indent=2))

    # Maintain a flat "history.jsonl" index for fast chronological loads.
    index_path = runs_dir / "history.jsonl"
    with open(index_path, "a") as f:
        f.write(json.dumps({"run_id": run.run_id, "timestamp": run.timestamp}) + "\n")

    return out_path


def load_run_history(runs_dir: str | Path) -> list[EvalRun]:
    """Returns all stored runs, ordered oldest -> newest."""
    runs_dir = Path(runs_dir)
    index_path = runs_dir / "history.jsonl"
    if not index_path.exists():
        return []

    run_ids = []
    with open(index_path) as f:
        for line in f:
            line = line.strip()
            if line:
                run_ids.append(json.loads(line)["run_id"])

    runs = []
    for run_id in run_ids:
        run_path = runs_dir / f"{run_id}.json"
        if run_path.exists():
            runs.append(EvalRun.model_validate_json(run_path.read_text()))
    return runs


def load_latest_run(runs_dir: str | Path) -> EvalRun | None:
    history = load_run_history(runs_dir)
    return history[-1] if history else None
