# VoiceNote

**Talk for 5 minutes. Get a polished, publish-ready article.**

Founders, creators, and podcasters have ideas in their heads but find writing slow. VoiceNote removes the blank page: speak your thoughts, get a structured article ready to publish.

---

## Live URLs

> Update after deploy

- **Frontend**: `https://voicenote.vercel.app` (pending Vercel deploy)
- **Backend**: `https://jj--voicenote-backend-fastapi-app.modal.run` (pending Modal deploy)
- **Health check**: `GET /healthz` → `{"status":"ok","version":"0.1.0"}`

---

## Demo Path

1. Open the web URL
2. Click the red microphone button (browser requests mic permission)
3. Talk for 2-5 minutes about any topic
4. Click "Stop & Generate Article" (enabled after 10 seconds)
5. See rendered article with title + full body
6. Click "Copy Markdown", "Download .md", or "Publish to Substack"

---

## How It Compares

| Feature | Otter/Whisper | Riverside/Descript | VoiceNote |
|---|---|---|---|
| Live transcript | Yes | Yes | No (batch) |
| Structured article | No | No | Yes |
| 1-click publish | No | No | Yes (Substack) |
| Price | $17/mo | $24/mo | ~$0.04/article |

---

## Quickstart (Local Dev)

### Backend

```bash
cd voicenote/

# Install Python deps
pip install -e .

# Copy and fill env vars
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY + OPENAI_API_KEY

# Run locally
uvicorn backend.main:app --reload --port 8000

# Health check
curl http://localhost:8000/healthz
# {"status":"ok","version":"0.1.0"}

# Test with fixture audio
curl -X POST http://localhost:8000/articles/generate \
  -F "audio=@tests/fixtures/sample.wav"
```

### Frontend

```bash
cd web/
npm install

# Create env
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local

npm run dev
# Open http://localhost:3000
```

### Tests

```bash
# Unit + live Claude tests (requires ANTHROPIC_API_KEY)
pytest tests/ -v

# Lint
ruff check backend/

# Frontend type check + build
cd web && npm run build
```

---

## Deploy

### Backend (Modal)

```bash
pip install modal
modal token new  # first-time auth

# Create secret group in https://modal.com/secrets named "voicenote-secrets"
# Add: ANTHROPIC_API_KEY, OPENAI_API_KEY
# Optional: SUPABASE_URL, SUPABASE_ANON_KEY, VOICENOTE_ALLOWED_ORIGINS

modal deploy backend/modal_app.py
# Prints URL like: https://jj--voicenote-backend-fastapi-app.modal.run
```

### Frontend (Vercel)

```bash
cd web/
npx vercel --prod
# Set env var NEXT_PUBLIC_BACKEND_URL to the Modal URL above
```

---

## Architecture

```
Browser                      Modal (FastAPI)              APIs
  |                               |                         |
  |-- MediaRecorder (.webm) ----> |                         |
  |                               |-- audio bytes --------> Whisper
  |                               |<-- transcript ----------|
  |                               |-- transcript ---------> Claude claude-sonnet-4-6
  |                               |<-- {title,body_md} -----|
  |                               |-- save to SQLite/Supabase
  |<-- {id,title,body_md,cost} ---|
  |                               |
  |-- Markdown preview            |
  |-- Copy/Download/.md           |
  |-- Publish to Substack         |
```

### Key files

```
backend/
  main.py           FastAPI app: /healthz, POST /articles/generate, GET /articles/{id}
  transcribe.py     Whisper API wrapper + CJK language heuristic
  article_writer.py Claude prompt + JSON parser + cost calculator
  storage.py        Supabase upsert with SQLite fallback
  modal_app.py      Modal ASGI wrapper + smoke test function

web/
  app/page.tsx              Landing page + recorder UI (single page)
  components/Recorder.tsx   MediaRecorder state machine + waveform UI
  components/ArticlePreview.tsx  Rendered markdown + Copy/Download/Substack
  lib/api.ts                Fetch wrapper pointing at backend URL

tests/
  test_article_writer.py    Live Claude test + unit tests
  fixtures/sample.wav       5s sine-wave WAV for curl testing
```

---

## Cost Per Article

| Step | Model | Est. cost |
|---|---|---|
| Whisper transcription | whisper-1 | $0.006/min x 3min = $0.018 |
| Claude article writer | claude-sonnet-4-6 | ~$0.018 (1K in + 1K out tokens) |
| Total | | ~$0.036/article |

---

## Known Issues / Not Done

1. **No user auth**: `user_id` is not required. All articles stored as "anonymous". Add Clerk or Supabase Auth for multi-user.
2. **Supabase integration untested**: SUPABASE_URL/ANON_KEY not in shell env during build. SQLite fallback is active. Supabase path is written and should work with env vars set.
3. **No real-time waveform**: Waveform bars are simulated from AudioContext analyser. A true spectrogram requires Web Audio API canvas rendering (nice-to-have).
4. **Substack publish**: URL-stuffing only (Substack has no public write API). Opens compose page with title pre-filled. User pastes body manually.
5. **Modal cold start**: First request after inactivity may take 5-10s. Set `min_concurrency=1` in modal_app.py to keep warm (increases cost).
6. **5-min hard cap**: Auto-stops recording at 300s. Whisper's 25MB file limit is the practical ceiling (~4 hours at webm quality).
7. **LiveKit not used**: MediaRecorder fallback shipped as primary (see HOW-DECISION.md §1).

---

## Comparison with Existing Solutions Researched

- **Otter.ai / Whisper**: transcription only, no article structure, no 1-click publish
- **Riverside.fm / Descript**: podcast-focused, video editing, no article generation from voice
- **Podium**: AI podcast show notes, closest competitor, subscription-based
- **VoiceNote angle**: structured long-form article (600-1200 words), per-use cost model, open infra
