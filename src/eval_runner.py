"""
Phase 3 (part 1): the test runner.

Loads a PromptConfig and the golden dataset, runs every test case through
the LLM feature, and produces a scored EvalRun.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import yaml

from .llm_feature import LLMClient, classify_email, get_client
from .models import CaseScore, EvalRun, PromptConfig, TestCase


def load_prompt(path: str | Path) -> PromptConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return PromptConfig(**raw)


def load_dataset(path: str | Path) -> list[TestCase]:
    with open(path) as f:
        raw = json.load(f)
    return [TestCase(**case) for case in raw["cases"]]


def score_case(
    case: TestCase, prompt: PromptConfig, client: LLMClient, judge_passing_score: int = 3
) -> CaseScore:
    try:
        output, latency_ms, in_tok, out_tok = classify_email(
            case.input_email, prompt, client=client
        )
        category_match = output.category == case.expected_category
        relevance_score = client.judge_relevance(case.expected_summary, output.summary)
        passed = category_match and relevance_score >= judge_passing_score
        return CaseScore(
            case_id=case.id,
            category_match=category_match,
            relevance_score=relevance_score,
            passed=passed,
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            raw_output=output,
            expected=case,
        )
    except Exception as exc:  # noqa: BLE001 -- we want to record ANY failure as a failing case
        from .models import FeatureOutput

        return CaseScore(
            case_id=case.id,
            category_match=False,
            relevance_score=0,
            passed=False,
            latency_ms=0.0,
            input_tokens=0,
            output_tokens=0,
            raw_output=FeatureOutput(category="general", summary=""),
            expected=case,
            error=str(exc),
        )


def run_evaluation(
    prompt_path: str | Path,
    dataset_path: str | Path,
    judge_passing_score: int = 3,
    client: LLMClient | None = None,
) -> EvalRun:
    """
    Runs every test case in the golden dataset through the LLM feature
    configured by `prompt_path`, and returns a fully scored EvalRun.

    Async batching is intentionally omitted here to keep the reference
    implementation simple and dependency-light; swap `client.classify`
    calls for `asyncio.gather` batches if your dataset grows large enough
    that latency becomes a problem.
    """
    prompt = load_prompt(prompt_path)
    dataset = load_dataset(dataset_path)
    client = client or get_client()

    scores = [score_case(case, prompt, client, judge_passing_score) for case in dataset]

    return EvalRun(
        run_id=str(uuid.uuid4())[:8],
        prompt_version=prompt.version,
        model=prompt.model,
        scores=scores,
    )
