"""Modal deployment wrapper for VoiceNote FastAPI backend.

Deploy:
  modal deploy backend/modal_app.py

Serve locally (hot reload):
  modal serve backend/modal_app.py

The FastAPI app is imported from backend.main and served via Modal's ASGI adapter.
Env secrets are injected via Modal Secrets (see README.md for setup).
"""
from __future__ import annotations

import modal

# ---------------------------------------------------------------------------
# Modal app definition
# ---------------------------------------------------------------------------

app = modal.App("voicenote-backend")

# Python dependencies installed in the container image
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.115",
        "uvicorn[standard]>=0.29",
        "anthropic>=0.25",
        "openai>=1.25",
        "python-multipart>=0.0.9",  # required for FastAPI file uploads
        "supabase>=2.3",            # optional; gracefully absent if env not set
    )
    .add_local_dir("backend", remote_path="/app/backend")
)

# Modal secret group — set these in https://modal.com/secrets
# Required: ANTHROPIC_API_KEY, OPENAI_API_KEY
# Optional: SUPABASE_URL, SUPABASE_ANON_KEY, VOICENOTE_ALLOWED_ORIGINS
secrets = [
    modal.Secret.from_name("voicenote-secrets", required=False),
]


@app.function(
    image=image,
    secrets=secrets,
    # Keep 1 container warm to avoid cold starts on demo
    min_concurrency=0,
    max_concurrency=10,
    # 5-min timeout: enough for Whisper (30s) + Claude (20s) on long recordings
    timeout=300,
    # Generous memory for audio buffering
    memory=1024,
)
@modal.asgi_app()
def fastapi_app():
    """Return the FastAPI ASGI application."""
    import sys
    sys.path.insert(0, "/app")
    from backend.main import app as _app
    return _app


# ---------------------------------------------------------------------------
# One-off test function (modal run backend/modal_app.py::smoke_test)
# ---------------------------------------------------------------------------


@app.function(image=image, secrets=secrets)
def smoke_test():
    """Verify the app imports and /healthz is reachable."""
    import sys

    sys.path.insert(0, "/app")
    from fastapi.testclient import TestClient

    from backend.main import app as fastapi
    client = TestClient(fastapi)
    response = client.get("/healthz")
    assert response.status_code == 200, f"healthz failed: {response.text}"
    print("smoke test PASSED:", response.json())
