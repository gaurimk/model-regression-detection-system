"""
Phase 1: the LLM feature under test.

A single, self-contained function that classifies a customer support
email into a category and produces a one-sentence summary. The prompt
is a configurable parameter (PromptConfig) so the eval pipeline can run
the exact same feature code against many prompt versions.

Two backends are supported:
  - OpenAIClient: calls the real OpenAI API (used when OPENAI_API_KEY is set)
  - MockClient:   a deterministic, offline stand-in used for local development,
                  CI dry-runs, and demoing the pipeline without API cost

This mirrors how real teams work: the eval pipeline itself should never
care which backend is behind the interface.
"""
from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod

from .models import FeatureOutput, PromptConfig

CATEGORY_KEYWORDS = {
    "billing": [
        "invoice", "charge", "charged", "refund", "payment", "subscription", "billed",
        "price", "pricing", "discount", "currency", "receipt", "fee", "prorated",
        "annual plan", "monthly plan", "card on file", "declining", "trial",
    ],
    "technical": [
        "error", "bug", "crash", "crashes", "not working", "broken", "login", "log in",
        "password", "fails", "stuck", "processing", "502", "export", "upload",
        "notification", "session expired", "blank page", "se cierra", "funciona",
    ],
    "account": [
        "account", "profile", "email address", "username", "delete my", "close my",
        "merge two accounts", "team member", "workspace", "logged into my account",
        "suspended", "acces", "acount",
    ],
}
GENERAL_KEYWORDS = [
    "great", "nice work", "office in", "policy", "hiring", "webinar", "feedback", "hey",
]


class LLMClient(ABC):
    @abstractmethod
    def classify(self, email_text: str, prompt: PromptConfig) -> tuple[FeatureOutput, int, int]:
        """Returns (structured_output, input_tokens, output_tokens)."""
        raise NotImplementedError

    @abstractmethod
    def judge_relevance(self, expected_summary: str, actual_summary: str) -> int:
        """Returns an integer 1-5 rating of how well actual matches expected."""
        raise NotImplementedError


class OpenAIClient(LLMClient):
    """Real backend. Requires OPENAI_API_KEY to be set."""

    def __init__(self, model: str | None = None):
        from openai import OpenAI

        self._client = OpenAI()
        self._model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def classify(self, email_text: str, prompt: PromptConfig) -> tuple[FeatureOutput, int, int]:
        messages = [{"role": "system", "content": prompt.system_prompt}]
        for ex in prompt.few_shot_examples:
            messages.append({"role": "user", "content": ex["input"]})
            messages.append({"role": "assistant", "content": json.dumps(ex["output"])})
        messages.append({"role": "user", "content": email_text})

        response = self._client.chat.completions.create(
            model=prompt.model or self._model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        output = FeatureOutput(category=data["category"], summary=data["summary"])
        usage = response.usage
        return output, usage.prompt_tokens, usage.completion_tokens

    def judge_relevance(self, expected_summary: str, actual_summary: str) -> int:
        judge_prompt = (
            "Rate how well the ACTUAL summary captures the same meaning as the "
            "EXPECTED summary, on a scale of 1 (unrelated) to 5 (equivalent meaning). "
            "Respond with only the integer.\n\n"
            f"EXPECTED: {expected_summary}\nACTUAL: {actual_summary}"
        )
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0,
        )
        text = response.choices[0].message.content.strip()
        match = re.search(r"[1-5]", text)
        return int(match.group()) if match else 3


class MockClient(LLMClient):
    """
    Deterministic offline stand-in.

    Uses simple keyword matching instead of a real model call. This lets
    the entire pipeline (dataset, scoring, diffing, reporting, alerting,
    CI) run and be demonstrated with zero API cost and zero network
    dependency -- exactly what you want for local dev and CI dry-runs.
    """

    def classify(self, email_text: str, prompt: PromptConfig) -> tuple[FeatureOutput, int, int]:
        text = email_text.lower()
        category = "general"
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                category = cat
                break

        # Simulate the small amount of prompt-driven variance real
        # prompt changes cause, so the "diff" behavior has something
        # to actually detect across prompt versions.
        strict_mode = "concise" in prompt.system_prompt.lower()
        first_sentence = re.split(r"(?<=[.!?])\s+", email_text.strip())[0]
        summary = first_sentence[:80] if strict_mode else first_sentence[:140]

        output = FeatureOutput(category=category, summary=summary)
        input_tokens = len(email_text.split())
        output_tokens = len(summary.split()) + 2
        return output, input_tokens, output_tokens

    def judge_relevance(self, expected_summary: str, actual_summary: str) -> int:
        expected_words = set(expected_summary.lower().split())
        actual_words = set(actual_summary.lower().split())
        if not expected_words:
            return 3
        overlap = len(expected_words & actual_words) / len(expected_words)
        if overlap >= 0.6:
            return 5
        if overlap >= 0.4:
            return 4
        if overlap >= 0.2:
            return 3
        if overlap > 0:
            return 2
        return 1


def get_client() -> LLMClient:
    """Factory: real client if a key is configured, mock client otherwise."""
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIClient()
    return MockClient()


def classify_email(
    email_text: str, prompt: PromptConfig, client: LLMClient | None = None
) -> tuple[FeatureOutput, float, int, int]:
    """
    The feature under test.

    Returns (output, latency_ms, input_tokens, output_tokens).
    """
    client = client or get_client()
    start = time.perf_counter()
    output, in_tok, out_tok = client.classify(email_text, prompt)
    latency_ms = (time.perf_counter() - start) * 1000
    return output, latency_ms, in_tok, out_tok
