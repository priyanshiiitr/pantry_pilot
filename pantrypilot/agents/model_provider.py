"""Builds the AI model object the agents run on, based on `.env`.

This is the ONE place that knows about API keys and provider-specific setup, so
switching providers (e.g. moving off the Groq free tier to Bedrock for the AWS
judges) never means touching the agents themselves.

Why Groq needs no new library: Groq's API copies OpenAI's request/response shape
exactly ("OpenAI-compatible"), so we reuse Strands' own OpenAIModel and just point
it at Groq's URL instead of OpenAI's. Nothing extra to install.
"""

from strands.models import Model

from pantrypilot.agents.rotating_keys import build_rotating_http_client
from pantrypilot.config import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def build_model(model_id: str | None = None) -> Model:
    """Build a Strands model object for whichever provider is configured in `.env`.

    Args:
        model_id: override the model id from `.env` (used for the Coordinator's
            optionally-stronger model in later steps). Defaults to settings.model_id.
    """
    provider = settings.model_provider.lower()
    resolved_model_id = model_id or settings.model_id

    if provider == "groq":
        return _build_groq_model(resolved_model_id)
    if provider == "openai":
        return _build_openai_compatible_model(
            api_key=settings.openai_api_key, base_url=None, model_id=resolved_model_id, provider_name="OpenAI"
        )
    if provider == "anthropic":
        return _build_anthropic_model(resolved_model_id)
    if provider == "bedrock":
        return _build_bedrock_model(resolved_model_id)

    raise ValueError(
        f"Unknown MODEL_PROVIDER='{settings.model_provider}' in .env. "
        "Use one of: groq, anthropic, bedrock, openai."
    )


def _build_groq_model(model_id: str) -> Model:
    """Build the Groq model, with automatic failover across every configured key.

    Groq's free tier limits tokens per minute per key, and a multi-agent run
    exhausts one key's minute quickly. When more than one key is configured the
    HTTP layer moves to the next one on a 429 instead of waiting (see
    agents/rotating_keys.py); with a single key the behaviour is unchanged.
    """
    api_keys = settings.groq_api_keys
    if not api_keys:
        raise ValueError("GROQ_API_KEY is not set. Add it to your .env file (MODEL_PROVIDER=groq).")

    from strands.models.openai import OpenAIModel

    client_args: dict[str, object] = {"api_key": api_keys[0], "base_url": GROQ_BASE_URL}
    if len(api_keys) > 1:
        client_args["http_client"] = build_rotating_http_client(api_keys)

    return OpenAIModel(client_args=client_args, model_id=model_id, params={"temperature": 0.2})


def _build_openai_compatible_model(*, api_key: str, base_url: str | None, model_id: str, provider_name: str) -> Model:
    """Build a model for any provider that speaks the OpenAI API shape (OpenAI itself, or Groq)."""
    if not api_key:
        env_var = "GROQ_API_KEY" if provider_name == "Groq" else "OPENAI_API_KEY"
        raise ValueError(f"{env_var} is not set. Add it to your .env file (MODEL_PROVIDER={provider_name.lower()}).")

    from strands.models.openai import OpenAIModel

    client_args = {"api_key": api_key}
    if base_url:
        client_args["base_url"] = base_url

    return OpenAIModel(client_args=client_args, model_id=model_id, params={"temperature": 0.2})


def _build_anthropic_model(model_id: str) -> Model:
    """Build a direct Anthropic API model."""
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set. Add it to your .env file (MODEL_PROVIDER=anthropic).")

    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args={"api_key": settings.anthropic_api_key},
        model_id=model_id,
        max_tokens=2048,
        params={"temperature": 0.2},
    )


def _build_bedrock_model(model_id: str) -> Model:
    """Build an Amazon Bedrock model. Credentials come from boto3 (aws configure, env vars, etc.)."""
    from strands.models import BedrockModel

    return BedrockModel(model_id=model_id, region_name=settings.aws_region, temperature=0.2)
