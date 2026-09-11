"""Environment-driven configuration for the payee-disambiguation demo.

Two rules govern this module:

1. Importing it must never raise. Every setting has a usable default, so a
   missing environment variable degrades behaviour rather than breaking start-up
   (the container deploy relies on this).
2. ``get_llm()`` re-reads the environment on every call rather than closing over
   the constants below. The Streamlit sidebar flips feature flags between runs
   in the same process, so anything that can change at runtime must be read at
   call time. Later modules follow the same convention.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root regardless of the current working directory.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- Paths -------------------------------------------------------------
# Resolved from __file__ so tools, RAG and the UI can read data/ whether they
# were started from the project root, from ui/, or from inside the container.
DATA_DIR = BASE_DIR / "data"
PAYEES_PATH = DATA_DIR / "payees.json"
TRANSFER_HISTORY_PATH = DATA_DIR / "transfer_history.json"
CUSTOMER_MASTER_DIR = DATA_DIR / "customer_master"
CHROMA_PATH = BASE_DIR / "chroma_store"

# --- Model backend -----------------------------------------------------
SUPPORTED_PROVIDERS = ("openai_compatible", "anthropic")

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai_compatible")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "")

# --- Telemetry ---------------------------------------------------------
TELEMETRY_BACKEND = os.getenv("TELEMETRY_BACKEND", "phoenix")
PHOENIX_ENDPOINT = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006/v1/traces")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# Deterministic by default: the demo compares runs side by side, so sampling
# noise would be indistinguishable from genuine model disagreement.
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0"))


def get_llm(**overrides):
    """Return a LangChain chat model built from the environment.

    The provider is selected by MODEL_PROVIDER alone, so swapping backends is a
    config change and not a code change. Any keyword argument overrides the
    corresponding setting, which the verifier agent uses to run at a different
    temperature from the primary agent.

    Raises:
        ValueError: if MODEL_PROVIDER is not one of SUPPORTED_PROVIDERS.
        ImportError: with an actionable message if the provider's package is
            not installed.
    """
    provider = overrides.pop("provider", os.getenv("MODEL_PROVIDER", MODEL_PROVIDER))
    model = overrides.pop("model", os.getenv("MODEL_NAME", MODEL_NAME))
    api_key = overrides.pop("api_key", os.getenv("MODEL_API_KEY", MODEL_API_KEY))
    base_url = overrides.pop("base_url", os.getenv("MODEL_BASE_URL", MODEL_BASE_URL))
    temperature = overrides.pop(
        "temperature", float(os.getenv("MODEL_TEMPERATURE", MODEL_TEMPERATURE))
    )

    provider = (provider or "").strip().lower()

    if provider == "openai_compatible":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - install-time guidance
            raise ImportError(
                "MODEL_PROVIDER=openai_compatible requires langchain-openai. "
                "Install it with: pip install langchain-openai"
            ) from exc
        kwargs = {"model": model, "api_key": api_key, "temperature": temperature}
        # Only pass base_url when set; an empty string would override the
        # provider's own default endpoint with an invalid one.
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs, **overrides)

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:  # pragma: no cover - install-time guidance
            raise ImportError(
                "MODEL_PROVIDER=anthropic requires langchain-anthropic. "
                "Install it with: pip install langchain-anthropic"
            ) from exc
        # MODEL_BASE_URL is deliberately ignored here: the Anthropic client
        # takes a different URL shape and the demo never needs to override it.
        return ChatAnthropic(
            model=model, api_key=api_key, temperature=temperature, **overrides
        )

    raise ValueError(
        f"Unsupported MODEL_PROVIDER {provider!r}. "
        f"Expected one of: {', '.join(SUPPORTED_PROVIDERS)}."
    )
