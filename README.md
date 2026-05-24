# VoiceNote

**Talk for 5 minutes. Get a polished, publish-ready article.**

Founders, creators, and podcasters have ideas in their heads but find writing slow. VoiceNote removes the blank page: speak your thoughts, get a structured article ready to publish.

> **Status**: V0.1 ships record-and-generate via Whisper + Claude Sonnet 4.6. The Substack "publish" button is a compose-page URL prefill, not a real API write.

---

## Quickstart (local)

1. Backend:
   ```bash
   cd voicenote
   pip install -e .
   export ANTHROPIC_API_KEY="sk-ant-..."
   export OPENAI_API_KEY="sk-..."
   export VOICENOTE_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
   echo "VOICENOTE_API_KEY=$VOICENOTE_API_KEY"
   uvicorn backend.main:app --reload --port 8000
   ```

2. Frontend:
   ```bash
   cd web
   echo "VOICENOTE_BACKEND_URL=http://localhost:8000" > .env.local
   echo "VOICENOTE_API_KEY=$VOICENOTE_API_KEY" >> .env.local
   npm install && npm run dev
   ```
   Both env vars are **server-only** (no `NEXT_PUBLIC_` prefix). The browser uploads audio to Next.js at `/api/articles/generate`; the route holds the key and proxies to the backend. Nothing secret ships in the JS bundle.

3. Open `http://localhost:3000`. Click record, talk, click stop.

---

## Tests

```bash
pip install -e .[dev]
pytest tests/ -v                              # offline tests run without keys
ANTHROPIC_API_KEY=sk-ant-... pytest tests/    # plus the 2 live-Claude tests
```

10 offline tests cover article-writer schema, prompt-injection escape, length cap, /articles/generate auth + size cap, and parser hardening. 2 live_api tests require ANTHROPIC_API_KEY.

---

## Deploy

### Backend (Modal)

```bash
modal token new   # one-time auth

# One-time: create the secret bundle Modal reads at runtime
modal secret create voicenote-secrets \
    OPENAI_API_KEY=$OPENAI_API_KEY \
    ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    VOICENOTE_API_KEY=$VOICENOTE_API_KEY \
    VOICENOTE_ALLOWED_ORIGINS=https://<your-frontend>.vercel.app

# Optional Supabase persistence (else SQLite on /data Volume):
#     SUPABASE_URL=...
#     SUPABASE_ANON_KEY=...

modal deploy backend/modal_app.py
```

The `voicenote-data` Modal Volume keeps the SQLite fallback durable across container scale-to-zero.

### Frontend (Vercel)

```bash
cd web
vercel env add VOICENOTE_BACKEND_URL production   # e.g. https://<...>.modal.run
vercel env add VOICENOTE_API_KEY production       # same value as backend's VOICENOTE_API_KEY
vercel --prod
```

Both env vars are server-only. The Next.js route at `web/app/api/articles/generate/route.ts` is the only thing that talks to the backend.

---

## Security posture (V0.1)

- All `POST /articles/generate` and `GET /articles/:id` calls require an `X-API-Key` header. Missing config = 503; bad key = 401.
- Per-IP rate limit (default 5/hour on backend, 5/hour on Next.js proxy too), LRU-capped at 5000 buckets to prevent memory DoS.
- `X-Forwarded-For` is ignored unless source IP is in `TRUSTED_PROXIES`; the Next.js proxy reads only platform-trusted `x-vercel-forwarded-for` / `x-real-ip`.
- Audio capped at 25 MB on the backend (Whisper API limit); the Next.js proxy caps tighter at 4 MB to fit Vercel Hobby's serverless body limit. Longer recordings need Vercel Pro or direct backend access with API key.
- CORS locked to `VOICENOTE_ALLOWED_ORIGINS` (default `http://localhost:3000`).
- Transcript wrapped in `<transcript>` XML tags with case- and whitespace-insensitive close-tag escape and anti-injection guardrail in the system prompt. Truncated at 60k chars before being sent to Claude.
- Anthropic + OpenAI clients are module-level lazy singletons.

---

## How it compares

| Feature              | Otter/Whisper | Riverside/Descript | VoiceNote        |
|----------------------|---------------|--------------------|------------------|
| Live transcript      | Yes           | Yes                | No (batch)       |
| Structured article   | No            | No                 | Yes              |
| 1-click publish      | No            | No                 | Yes (Substack)   |
| Price                | $17/mo        | $24/mo             | ~$0.04/article   |

---

## Architecture

```
Browser                 Next.js /api/articles/generate   Modal (FastAPI)     APIs
  |                                |                            |              |
  |-- MediaRecorder (.webm) -----> | server route adds X-API-Key|              |
  |                                |---- upload ---------------->              |
  |                                |                            |-- bytes -----> Whisper
  |                                |                            |<-- transcript -|
  |                                |                            |-- prompt ------> Claude Sonnet 4.6
  |                                |                            |<-- {title,body_md}|
  |                                |                            |-- save -> SQLite or Supabase
  |                                |<--- {id,title,body_md} ----|
  |<-- {id,title,body_md} ---------|
```

### Files

```
backend/
  main.py            FastAPI app: auth + rate limit + size cap, /healthz, /articles/generate, /articles/:id
  transcribe.py      Whisper API wrapper, lazy client, CJK language heuristic
  article_writer.py  Claude prompt (XML-wrapped transcript + anti-injection), schema validation
  storage.py         Supabase upsert with SQLite fallback
  modal_app.py       Modal ASGI wrapper, /data Volume for SQLite persistence, @modal.concurrent
web/
  app/
    page.tsx                          Landing + recorder UI
    api/articles/generate/route.ts    Server-side proxy holding API key
  components/
    Recorder.tsx                       MediaRecorder state machine
    ArticlePreview.tsx                 Rendered markdown
  lib/api.ts                           Same-origin fetch wrapper
tests/
  test_article_writer.py               Offline + live_api tests
```

---

## Cost per article

| Step                  | Model              | Cost                       |
|-----------------------|--------------------|----------------------------|
| Whisper transcription | whisper-1          | $0.006/min x 3min = $0.018 |
| Claude article writer | claude-sonnet-4-6  | ~$0.018 (1K in + 1K out)   |
| **Total**             |                    | **~$0.036/article**        |

---

## Known limitations (V0.1)

- No user auth model. `user_id` is an optional query param; all storage rows are effectively single-tenant under the backend API key.
- Substack publish is a compose-page URL prefill (no public write API exists).
- Modal cold start adds 5-10s to the first request after inactivity. Set `min_containers=1` to keep one warm (raises cost).
- Audio cap is 25 MB on the backend (Whisper limit); Next.js proxy is tighter at 4 MB for Vercel Hobby.
- Rate limit is per-container in-memory. Multi-container scale needs Redis or Cloudflare.

See `HOW-DECISION.md` for implementation decisions.
