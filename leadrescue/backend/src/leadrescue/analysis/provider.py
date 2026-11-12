"""Provider interface and the shared analyze pipeline.

Every provider returns a ProviderResult whose `raw` dict must match
MODEL_OUTPUT_SCHEMA. `run_analysis` validates it and applies guardrails, so the
demo analyzer and Bedrock produce exactly the same stored contract.
There is no fallback between providers: a failed live call is a failure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from ..errors import AnalysisError
from ..schema_validator import validate
from .contract import MODEL_OUTPUT_SCHEMA, PROMPT_VERSION
from .guardrails import apply_guardrails


@dataclass
class ProviderResult:
    raw: dict
    model_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class AnalysisProvider(Protocol):
    name: str

    def analyze(self, message: str, channel: str, customer: dict) -> ProviderResult: ...


def run_analysis(provider: AnalysisProvider, message: str, channel: str, customer: dict) -> dict:
    started = time.perf_counter()
    result = provider.analyze(message, channel, customer)
    latency_ms = int((time.perf_counter() - started) * 1000)
    errors = validate(result.raw, MODEL_OUTPUT_SCHEMA)
    if errors:
        raise AnalysisError(
            "invalid_model_output",
            "The AI response did not match the required format, so it was discarded. Retry or handle manually.",
            retryable=True,
        )
    analysis = apply_guardrails(result.raw, message, customer)
    analysis["meta"] = {
        "provider": provider.name,
        "modelId": result.model_id,
        "promptVersion": PROMPT_VERSION,
        "latencyMs": latency_ms,
        "inputTokens": result.input_tokens,
        "outputTokens": result.output_tokens,
        "analyzedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "confidenceCalibrated": False,
    }
    analysis["rawExtracted"] = result.raw["extracted"]
    return analysis


def get_provider(config) -> AnalysisProvider:
    if config.ai_provider == "bedrock":
        from .bedrock_provider import BedrockProvider

        return BedrockProvider(config)
    from .demo_provider import DemoProvider

    return DemoProvider()
