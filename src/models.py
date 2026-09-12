"""
Typed data contracts used across the pipeline.

Keeping these in one place means every stage (eval runner, scorer,
comparison engine, reporter) agrees on exactly what a "test case" or
"result" looks like. This is the "interface contract" referenced in
Phase 1 of the build guide.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["billing", "technical", "account", "general"]
Difficulty = Literal["easy", "medium", "hard", "edge_case"]


class PromptConfig(BaseModel):
    """A single versioned prompt definition loaded from /prompts/*.yaml."""

    version: str
    timestamp: str
    system_prompt: str
    few_shot_examples: list[dict] = Field(default_factory=list)
    model: str = "gpt-4o-mini"


class TestCase(BaseModel):
    """One entry in the golden dataset."""

    id: str
    input_email: str
    expected_category: Category
    expected_summary: str
    difficulty: Difficulty = "easy"
    notes: str = ""


class FeatureOutput(BaseModel):
    """Structured output returned by the LLM feature under test."""

    category: Category
    summary: str


class CaseScore(BaseModel):
    """Multi-dimensional score for a single test case on a single run."""

    case_id: str
    category_match: bool
    relevance_score: int  # 1-5, from LLM-as-judge (or heuristic fallback)
    passed: bool  # overall pass/fail for this case
    latency_ms: float
    input_tokens: int
    output_tokens: int
    raw_output: FeatureOutput
    expected: TestCase
    error: Optional[str] = None


class EvalRun(BaseModel):
    """The full result of one evaluation run, ready to persist to disk."""

    run_id: str
    prompt_version: str
    model: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    scores: list[CaseScore]

    @property
    def pass_rate(self) -> float:
        if not self.scores:
            return 0.0
        return sum(1 for s in self.scores if s.passed) / len(self.scores)

    @property
    def category_accuracy(self) -> float:
        if not self.scores:
            return 0.0
        return sum(1 for s in self.scores if s.category_match) / len(self.scores)

    @property
    def avg_relevance(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.relevance_score for s in self.scores) / len(self.scores)

    @property
    def avg_latency_ms(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.latency_ms for s in self.scores) / len(self.scores)

    @property
    def total_tokens(self) -> int:
        return sum(s.input_tokens + s.output_tokens for s in self.scores)
