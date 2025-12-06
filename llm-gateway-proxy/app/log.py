import os
import atexit
import posthog
from typing import Optional
from fastapi import FastAPI


# Global flag so we only flush if PostHog is actually enabled
_posthog_enabled = False

def setup_logging(app: Optional[FastAPI] = None):

    # === PostHog analytics ===
    posthog_project_api_key = os.getenv("POSTHOG_PROJECT_API_KEY")
    if posthog_project_api_key:
        global _posthog_enabled
        _posthog_enabled = True

        posthog.project_api_key = posthog_project_api_key
        posthog.host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")  # change to https://eu.i.posthog.com if you use EU instance

        if os.getenv("DEBUG", "").lower() == "true":
            posthog.debug = True

        # Ensure events are flushed when the process shuts down (important for uvicorn/gunicorn)
        atexit.register(posthog.flush)

def log_to_posthog(distinct_id: str, event: str, properties: Optional[dict] = None):
    """
    Safe wrapper – does nothing if PostHog is not configured.
    Use this everywhere you want to track analytics (successes, errors, fallbacks, comparisons, etc.).
    """
    if not _posthog_enabled:
        return

    if properties is None:
        properties = {}

    # Always add some useful defaults
    properties.setdefault("$process", "llm-gateway-proxy")
    properties.setdefault("$lib", "python-posthog")

    posthog.capture(distinct_id=distinct_id, event=event, properties=properties)