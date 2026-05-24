# HOW-DECISION.md, VoiceNote MVP

Engineering decisions made during the build. Format per JJ's CLAUDE.md §3.1.

---

## Decision 1: STT Path, LiveKit vs MediaRecorder + Whisper

**HOW decision**: speech-to-text pipeline for MVP

**Options:**
- A) LiveKit real-time STT: pro: low latency streaming, user sees transcript live. con: requires LiveKit server ($), complex agent worker infrastructure (200+ lines of Muse code), multiple env vars to configure, fragile for one-night MVP.
- B) MediaRecorder → upload .webm → Whisper API: pro: browser-native, zero infra beyond backend endpoint, 1 API call, ~$0.006/min. con: no real-time feedback (user waits after Stop), file size limit (~25MB = ~4hr at .webm quality, well above 5min cap).
- C) OpenAI Realtime API streaming: pro: no upload step, streaming text. con: new API surface, more complex state machine, higher cost, same infra complexity as LiveKit.

**Preference: B**, MediaRecorder + Whisper API. Fits the MVP demo path exactly, matches JJ's serverless-first rule (no LiveKit server), and Muse Agents' LiveKit pattern is specialized for music intake (12 tools, complex state). Whisper accuracy at 5min monologue is excellent.

**Researched via**: Muse Agents source (server.py, worker.py read), Whisper API docs, OpenAI Realtime API pricing.

---

## Decision 2: Storage, Supabase vs SQLite

**HOW decision**: article draft persistence

**Options:**
- A) Supabase Pro: pro: JJ already runs it (Muse Agents), proper UUID + timestamps, queryable. con: SUPABASE_URL + SUPABASE_ANON_KEY not present in shell env; would require .env config.
- B) SQLite local file: pro: zero deps, instant, works in Modal via `/tmp`. con: ephemeral in serverless (articles lost between cold starts), not queryable across requests.
- C) Supabase with SQLite fallback: pro: best of both worlds, graceful degradation. con: slightly more code.

**Preference: C**, try Supabase, fall back to SQLite. `storage.py` detects `SUPABASE_URL` at import; if absent, writes to `/tmp/voicenote.db`. For Modal, SQLite in `/tmp` is per-invocation; for persistent storage users set Supabase env vars.

**Researched via**: Muse Agents Supabase patterns, Modal ephemeral filesystem docs.

---

## Decision 3: LLM Model for Article Generation

**HOW decision**: Claude model selection

**Options:**
- A) claude-opus-4-5: highest quality. con: ~5x cost vs Sonnet.
- B) claude-sonnet-4-6: solid quality, fast. cost: ~$3/MTok input, ~$15/MTok output. At 1K input + 1K output tokens per article ≈ $0.018/article.
- C) claude-haiku-3-5: cheapest. con: article quality noticeably lower for long-form structured output.

**Preference: B**, `claude-sonnet-4-6` as specified in the brief. Good quality/cost balance for MVP.

**Cost estimate per article**:
- Whisper: $0.006/min × 3min = ~$0.018
- Claude sonnet: ~$0.018 (1K+1K tokens)
- Total: ~$0.036/article (~3.6 cents)

---

## Decision 4: Frontend Framework

**No choice needed**: Next.js 14 App Router + Tailwind specified in brief. Using `react-markdown` for markdown rendering (lighter than `marked`, better React integration, has TypeScript types).

---

## Decision 5: Modal Deployment Strategy

**HOW decision**: Modal app structure

**Options:**
- A) Single `@app.function()` wrapping FastAPI via ASGI: simplest, one deploy.
- B) Separate functions per endpoint: more granular scaling. con: overkill for MVP.

**Preference: A**, `modal serve` + `modal deploy` wrapping FastAPI app via `asgi_app()`. Standard Modal pattern. CORS headers added for Vercel domain.
