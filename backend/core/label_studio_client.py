"""
Label Studio client helper.

Reads LABEL_STUDIO_URL and LABEL_STUDIO_API_KEY from the .env file
at the project root.

Usage:
    from core.label_studio_client import get_client
    ls = get_client()
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from label_studio_sdk import LabelStudio

# Load .env from project root  (backend/../.env)
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH)

LABEL_STUDIO_URL = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
LABEL_STUDIO_API_KEY = os.getenv("LABEL_STUDIO_API_KEY", "")


def get_client(
    url: str | None = None,
    api_key: str | None = None,
) -> LabelStudio:
    """Return a connected LabelStudio client."""
    return LabelStudio(
        base_url=url or LABEL_STUDIO_URL,
        api_key=api_key or LABEL_STUDIO_API_KEY,
    )
