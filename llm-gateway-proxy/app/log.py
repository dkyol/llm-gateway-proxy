import os
import atexit
from typing import Optional
from fastapi import FastAPI

# We'll use the modern client pattern – works on every PostHog version
client = None
_posthog_enabled = False

def setup_logging(app: Optional[FastAPI] = None):
    global client, _posthog_enabled

    posthog_project_api_key = os.getenv("POSTHOG_PROJECT_API_KEY")
    if posthog_project_api_key:
        try:
            # This import works in all versions
            from posthog import Posthog

            host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
            client = Posthog(project_api_key=posthog_project_api_key, host=host)

            if os.getenv("DEBUG", "").lower() == "true":
                client.debug = True

            _posthog_enabled = True

            # Flush on exit (works perfectly with uvicorn/gunicorn)
            atexit.register(lambda: client.flush() if client else None)

        except Exception as e:
            print(f"PostHog failed to initialize (will be disabled): {e}")
            _posthog_enabled = False

def log_to_posthog(distinct_id: str, event: str, properties: Optional[dict] = None):
    if not _posthog_enabled or not client:
        return

    if properties is None:
        properties = {}

    properties.setdefault("$process", "llm-gateway-proxy")
    properties.setdefault("$lib", "python-posthog")

    # We don't let PostHog crash the request even if it fails
    try:
        client.capture(distinct_id=distinct_id, event=event, properties=properties)
    except Exception as e:
        print(f"PostHog capture failed: {e}")