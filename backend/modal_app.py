"""Modal deployment wrapper for VoiceNote FastAPI backend.

Deploy:  modal deploy backend/modal_app.py

Prereqs (one-time):
  modal secret create voicenote-secrets \\
      OPENAI_API_KEY=$OPENAI_API_KEY \\
      ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \\
      VOICENOTE_API_KEY=<random secret> \\
      VOICENOTE_ALLOWED_ORIGINS=https://<your-frontend>.vercel.app

For Supabase storage add SUPABASE_URL + SUPABASE_ANON_KEY to the same secret;
otherwise the SQLite fallback at /data/voicenote.db (on the voicenote-data
Volume) is used so articles survive scale-to-zero.
"""
from __future__ import annotations

import modal

app = modal.App("voicenote-backend")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.115",
        "uvicorn[standard]>=0.29",
        "anthropic>=0.40",
        "openai>=1.25",
        "python-multipart>=0.0.9",
        "supabase>=2.3",
    )
    .add_local_dir("backend", remote_path="/app/backend")
)

secrets = [modal.Secret.from_name("voicenote-secrets")]

volume = modal.Volume.from_name("voicenote-data", create_if_missing=True)


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/data": volume},
    min_containers=0,
    max_containers=10,
    timeout=300,
    memory=1024,
)
@modal.concurrent(max_inputs=5)
@modal.asgi_app()
def fastapi_app():
    import os
    import sys

    sys.path.insert(0, "/app")
    os.environ.setdefault("VOICENOTE_DB_PATH", "/data/voicenote.db")
    from backend.main import app as _app

    return _app


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
