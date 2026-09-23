"""Application settings, read from the `.env` file.

Why this file exists: every setting (database location, AI provider, secret keys)
is read in ONE place. The rest of the code does `from pantrypilot.config import settings`
instead of reading environment variables itself, so nothing secret is hard-coded.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The top folder of the project (the one containing README.md).
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Default database file: <project>/data/pantrypilot.db
DEFAULT_DATABASE_URL: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'pantrypilot.db').as_posix()}"


class Settings(BaseSettings):
    """All configurable values for PantryPilot.

    Each field has a safe default. A matching line in `.env` overrides it,
    e.g. `MODEL_PROVIDER=bedrock` sets `model_provider`. Names are not case-sensitive.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore .env lines we don't know about instead of crashing
    )

    # --- Web app ---
    app_name: str = "PantryPilot"
    session_secret: str = "dev-only-secret-change-me"
    database_url: str = DEFAULT_DATABASE_URL

    # Where the frontend is served from, when it isn't the same origin as the API.
    # Locally the Vite dev server proxies /api, so they look like one site and
    # this stays empty. Deployed (frontend on Vercel, API on Render) they are two
    # origins, and the browser needs both CORS permission and a cookie allowed to
    # travel cross-site. Comma-separated; no wildcard, because credentialed
    # requests require an exact origin.
    frontend_origins: str = ""

    # Set true wherever the site is served over HTTPS. It switches the login
    # cookie to SameSite=None; Secure, without which a cross-origin deployment
    # silently drops it and every request looks logged out.
    secure_cookies: bool = False

    # Shared secret for POST /api/tick (web/routes/tick.py), which lets an
    # external scheduler drive the agents where a long-running worker can't run.
    # Empty disables the endpoint entirely.
    tick_secret: str = ""

    @property
    def allowed_origins(self) -> list[str]:
        """frontend_origins split into a list, blanks removed."""
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    # --- Demo city ---
    # Pantry opening hours and driver availability are written in this city's local time.
    city_name: str = "Seattle, WA"
    city_timezone: str = "America/Los_Angeles"

    # --- AI model (used from Step 6) ---
    # model_provider is one of: "anthropic" | "bedrock" | "openai" | "groq".
    # Groq isn't a separate Strands feature — it speaks the same API shape as OpenAI,
    # so we reuse Strands' OpenAIModel and just point it at Groq's URL. See
    # pantrypilot/agents/model_provider.py.
    model_provider: str = "groq"
    model_id: str = "openai/gpt-oss-120b"
    coordinator_model_id: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    # Optional extra Groq keys, comma-separated, used only as failover when the
    # primary key is rate-limited. Groq's free tier caps tokens per *minute* per
    # key, which a multi-agent run hits easily; see agents/model_provider.py.
    groq_fallback_api_keys: str = ""
    aws_region: str = "us-east-1"

    @property
    def groq_api_keys(self) -> list[str]:
        """Every Groq key to try, primary first, with duplicates and blanks removed.

        Duplicates are dropped deliberately: the same key listed twice shares one
        rate-limit budget, so retrying it would just burn a retry for nothing.
        """
        candidates = [self.groq_api_key, *self.groq_fallback_api_keys.split(",")]
        unique: list[str] = []
        for candidate in candidates:
            key = candidate.strip()
            if key and key not in unique:
                unique.append(key)
        return unique

    # --- Tracing (used from Step 13) ---
    otel_console: bool = False


# One shared settings object, created when this module is first imported.
settings: Settings = Settings()
