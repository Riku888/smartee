"""Thin, provider-configurable wrapper for one-shot LLM generation.

Smartee's deterministic layers never call this — structured fields (dates,
scores, URLs, ids) are always extracted deterministically (Hard Rule 3).
This exists only for the enrichment layers (the Teacher), which reconstruct
course material into a learning experience.

Model is configurable per D-022 (`SMARTEE_TEACHER_MODEL`, default
`claude-opus-5`). Credentials resolve the normal Anthropic way
(`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or an `ant auth login`
profile); nothing is read from or written to the repo. When the SDK or
credentials are missing, `generate` raises `LlmUnavailable` rather than
failing deep in a call stack.
"""

import os
from dataclasses import dataclass

DEFAULT_MODEL = "claude-opus-5"
_MODEL_ENV = "SMARTEE_TEACHER_MODEL"


class LlmUnavailable(RuntimeError):
    """The LLM could not be reached: SDK not installed, no credentials, or a
    transport/auth error from the API."""


@dataclass(frozen=True)
class LlmConfig:
    """One generation's model settings. `model` defaults to the
    `SMARTEE_TEACHER_MODEL` env var, then `DEFAULT_MODEL`."""

    model: str = ""
    max_tokens: int = 16000

    def resolved_model(self) -> str:
        return self.model or os.environ.get(_MODEL_ENV, "") or DEFAULT_MODEL


def generate(system: str, prompt: str, *, config: LlmConfig | None = None) -> str:
    """One request, one response. `system` carries the policy (including the
    treat-course-text-as-data rule); `prompt` carries the task plus the
    untrusted course content. Returns the concatenated text blocks.

    Raises `LlmUnavailable` for any missing-dependency, missing-credential,
    or API transport/status failure — callers decide whether to skip the
    enrichment or surface the error.
    """
    settings = config or LlmConfig()
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise LlmUnavailable("the 'anthropic' SDK is not installed") from exc

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=settings.resolved_model(),
            max_tokens=settings.max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AnthropicError as exc:
        raise LlmUnavailable(str(exc)) from exc

    if response.stop_reason == "refusal":
        raise LlmUnavailable("the model declined to answer this request")

    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
