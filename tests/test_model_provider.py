"""Tests for pantrypilot/agents/model_provider.py (Step 6).

These tests never call a real AI API — they only check that the right model
object gets constructed (or the right error raised) for each provider setting.
"""

import pytest

from pantrypilot.agents.model_provider import build_model
from pantrypilot.config import settings


def test_groq_without_any_api_key_raises_a_helpful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Groq key at all should fail loudly and clearly, not with a confusing network error.

    Both the primary and the fallbacks have to be cleared: the check is "is there
    any usable key", so a fallback alone is enough to proceed.
    """
    monkeypatch.setattr(settings, "model_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "groq_fallback_api_keys", "")

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        build_model()


def test_groq_can_run_on_a_fallback_key_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key is a key — an unset primary with fallbacks configured still works."""
    monkeypatch.setattr(settings, "model_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "groq_fallback_api_keys", "fallback-key")

    assert build_model() is not None


def test_groq_with_api_key_builds_an_openai_compatible_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a key set, building the model succeeds (this never makes a network call)."""
    monkeypatch.setattr(settings, "model_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "fake-key-for-testing")
    monkeypatch.setattr(settings, "model_id", "openai/gpt-oss-120b")

    from strands.models.openai import OpenAIModel

    model = build_model()

    assert isinstance(model, OpenAIModel)


def test_openai_without_api_key_raises_a_helpful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same check for plain OpenAI."""
    monkeypatch.setattr(settings, "model_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_model()


def test_anthropic_without_api_key_raises_a_helpful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same check for Anthropic."""
    monkeypatch.setattr(settings, "model_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_model()


def test_unknown_provider_raises_a_helpful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo in MODEL_PROVIDER should say so clearly instead of failing deep inside Strands."""
    monkeypatch.setattr(settings, "model_provider", "not-a-real-provider")

    with pytest.raises(ValueError, match="Unknown MODEL_PROVIDER"):
        build_model()
