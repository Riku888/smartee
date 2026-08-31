"""Tests for the LLM client wrapper. No real API calls — `anthropic.Anthropic`
is replaced with a fake."""

from types import SimpleNamespace

import anthropic
import pytest

from smartee.llm import DEFAULT_MODEL, LlmConfig, LlmUnavailable, generate


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


class _FakeMessages:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.last_kwargs: dict = {}

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self._error is not None:
            raise self._error
        return self._response


class _FakeClient:
    def __init__(self, messages: _FakeMessages):
        self.messages = messages


def _install(monkeypatch, *, response=None, error=None) -> _FakeMessages:
    messages = _FakeMessages(response=response, error=error)
    monkeypatch.setattr(anthropic, "Anthropic", lambda: _FakeClient(messages))
    return messages


# --- config ----------------------------------------------------------


def test_model_defaults_then_env_then_explicit(monkeypatch):
    monkeypatch.delenv("SMARTEE_TEACHER_MODEL", raising=False)
    assert LlmConfig().resolved_model() == DEFAULT_MODEL
    monkeypatch.setenv("SMARTEE_TEACHER_MODEL", "claude-sonnet-5")
    assert LlmConfig().resolved_model() == "claude-sonnet-5"
    assert LlmConfig(model="claude-haiku-4-5").resolved_model() == "claude-haiku-4-5"


# --- generate --------------------------------------------------------


def test_generate_returns_joined_text_and_sends_expected_request(monkeypatch):
    monkeypatch.delenv("SMARTEE_TEACHER_MODEL", raising=False)
    messages = _install(
        monkeypatch,
        response=SimpleNamespace(
            stop_reason="end_turn",
            content=[
                _text_block("Hello "),
                _text_block("world"),
                SimpleNamespace(type="thinking"),
            ],
        ),
    )
    out = generate(
        "SYS", "PROMPT", config=LlmConfig(model="claude-opus-5", max_tokens=100)
    )
    assert out == "Hello world"
    assert messages.last_kwargs["model"] == "claude-opus-5"
    assert messages.last_kwargs["max_tokens"] == 100
    assert messages.last_kwargs["system"] == "SYS"
    assert messages.last_kwargs["messages"] == [{"role": "user", "content": "PROMPT"}]
    assert messages.last_kwargs["thinking"] == {"type": "adaptive"}


def test_generate_wraps_anthropic_errors(monkeypatch):
    _install(monkeypatch, error=anthropic.AnthropicError("no credentials"))
    with pytest.raises(LlmUnavailable, match="no credentials"):
        generate("s", "p")


def test_generate_raises_on_refusal(monkeypatch):
    _install(
        monkeypatch,
        response=SimpleNamespace(stop_reason="refusal", content=[]),
    )
    with pytest.raises(LlmUnavailable, match="declined"):
        generate("s", "p")


def test_generate_raises_when_sdk_missing(monkeypatch):
    # A None entry in sys.modules makes `import anthropic` raise ImportError.
    import sys

    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(LlmUnavailable):
        generate("s", "p")
