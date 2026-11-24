# LLM Chatbot with Key Failover and Response Caching

A chatbot (React + FastAPI) that calls Gemini through **LiteLLM**, automatically **fails over between API keys**, uses **LiteLLM's built-in response cache**, and stores conversations in **SQLite**.

**Architecture**

```
React (Vite, Tailwind)  --POST /chat-->  FastAPI
                                          |- loads history from SQLite
                                          |- builds [system + history + new message]
                                          |- tries key_1, then key_2, ... via litellm.completion
                                          |    (LiteLLM cache answers repeated conversations)
                                          '- saves user + assistant rows (only on success)
```

```
backend/app/    main.py config.py database.py models.py schemas.py
                routes/chat.py            (the 3 endpoints)
                services/llm_service.py       (litellm.completion call)
                services/failover_service.py  (key order, X-Simulate-Failure)
                services/cache_service.py     (litellm.Cache + cache-hit detection)
backend/tests/  pytest suite (34 tests)
frontend/src/   App.jsx, components/, services/api.js
docker-compose.yml  Makefile  .env.example
```

---

## 1. Live URLs

- Frontend: **Not deployed yet.**
- Backend: **Not deployed yet.**

(Fill these in after you deploy using the Render steps below.)

---

## 2. Run locally: with Docker and without

### Prerequisites: get two Gemini keys
Create two API keys at <https://aistudio.google.com/apikey> (ideally in two different Google projects so they have separate quotas).

```bash
cp .env.example .env      # Windows PowerShell: copy .env.example .env
```
Edit `.env` and set `LLM_API_KEYS=yourFirstKey,yourSecondKey`. `.env` is git-ignored, never commit it.

> **Model note:** `LLM_MODEL=gemini/gemini-2.0-flash` is only the default. Google retires models over time. If chat returns `502 provider rejected the request (check LLM_MODEL)`, set `LLM_MODEL` to a model your account can use (for example `gemini/gemini-2.5-flash`) and restart.

### With Docker
Install Docker Desktop, then:
```bash
make up        # or: docker compose up --build -d
make down      # stop (SQLite data is kept in the named volume)
make logs
```
- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000/health>

SQLite lives at `/data/app.db` in the `app_data` Docker volume, so history survives `make down` / `make up`.
(`make` is not installed on Windows by default; just run the `docker compose` commands shown.)

### Without Docker
Backend (Python 3.12+):
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
# DATABASE_URL in .env should be sqlite:///./app.db for local runs
uvicorn app.main:app --port 8000
```
Frontend (Node 20+), in a second terminal:
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000, uses VITE_API_BASE_URL or http://localhost:8000
```
Tests: `cd backend && python -m pytest -q` (no real keys needed). Frontend build check: `cd frontend && npm run build`.

### Environment variables
| Variable | Meaning |
|---|---|
| `LLM_API_KEYS` | Comma-separated keys. First = `key_1`, second = `key_2`, ... |
| `LLM_MODEL` | LiteLLM model name |
| `DATABASE_URL` | `sqlite:////data/app.db` (Docker/Render) or `sqlite:///./app.db` (local) |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins (no wildcard) |
| `ENABLE_FAILURE_SIMULATION` | `true` enables the `X-Simulate-Failure` header |
| `VITE_API_BASE_URL` | Frontend only, embedded at build time |

### API
```bash
curl localhost:8000/health
# {"status":"ok","keys_configured":2,"cache_enabled":true}

curl -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"s-1","message":"What is the capital of France?"}'

curl localhost:8000/sessions/s-1/messages
```
Errors are always JSON `{"detail": ...}`: 422 invalid input, 404 unknown session, 503 `all providers unavailable`, 502 provider rejected the request itself (e.g. wrong model name).

---

## 3. Design decisions: key fallback, caching, SQLite session storage

**Key fallback** (`failover_service.py`). Keys are tried in a fixed order (`key_1`, `key_2`, ...). A key is skipped and the next one tried on 429/quota/rate limit, any 5xx, timeouts/connection errors, and 401/403 (that key is bad). `fallback_attempts` = number of keys that failed before success. If all fail → HTTP 503 `{"detail":"all providers unavailable"}` and nothing is saved. Each attempt is a real `litellm.completion(api_key=...)` call with `num_retries=0`, so LiteLLM doesn't keep retrying an exhausted key. No key is ever disabled permanently. Errors that no other key can fix (e.g. unknown model, HTTP 400/404) return 502 instead of burning every key. Key values are never logged or returned; only `key_N` ids are.

**Caching** (`cache_service.py`). `litellm.cache = Cache(type="local")` (in-memory, built into LiteLLM). LiteLLM's cache key is built from the model and the *full* message list (system prompt + history + new message). The session id and API key are not part of it, so the same first question in two sessions is a cache hit, while the same question after a different history is not. Hits are detected from LiteLLM's own `_hidden_params["cache_hit"]` flag (not by timing or text comparison). On a hit: `resolution_source=LLM_CACHE`, `key_id=null`, `fallback_attempts=0`, and the original cached reply and token usage. Limitations: the cache is in-memory, so it resets on restart; and a cached answer is returned even if a real key is currently exhausted (that's the point of a cache). With `X-Simulate-Failure` all-keys-fail, the simulated failure wins, so use a *new* message for the 503 demo.

**SQLite** (`database.py`). Table `messages(id, session_id, role, content, metadata, created_at)` exactly as specified, created at startup. The client sends only the new message; the backend loads that session's history. User + assistant rows are written in one transaction, only after a successful reply, so failed (422/503) requests leave no trace. A session's system prompt (optional `system_prompt` field) is stored as a `system` row, reused for later turns, and hidden from the history endpoint. `GET /sessions/{id}/messages` never creates a session; unknown → 404.

**Docs routes are disabled** (`/docs`, `/openapi.json`) so the app exposes only the 3 contract endpoints.

---

## 4. Verification: how to see failover, cache hits and per-message token usage

Needs `ENABLE_FAILURE_SIMULATION=true` and two keys. In the UI, expand **Options** to type the failure header; or use curl:

```bash
# Normal call: key_1, fallback_attempts 0, LIVE_INFERENCE
curl -s -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"Name three rivers in Europe"}'

# Cache hit: same message, NEW session -> LLM_CACHE, key_id null, same tokens, lower latency
curl -s -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo2","message":"Name three rivers in Europe"}'

# Failover: key_1 "fails", key_2 makes a real call -> key_id key_2, fallback_attempts 1
curl -s -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id":"demo3","message":"Tell me a fun fact about owls"}'

# All fail -> 503 {"detail":"all providers unavailable"}, nothing stored
curl -i -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429,key_2=500" \
  -d '{"session_id":"demo4","message":"Tell me a fun fact about cats"}'
curl -i localhost:8000/sessions/demo4/messages     # 404 session not found
```
(On Windows PowerShell use `curl.exe` and put the JSON in single quotes with `\"` escapes, or use the UI / browser DevTools.)
Per-message token usage: every assistant reply shows `in tokens` / `out tokens` for *that reply only*; `GET /sessions/demo/messages` returns them under each assistant message's `metadata`.

### Automated tests
`cd backend && python -m pytest -q` runs 34 tests covering validation, history, separate sessions, failover (429/500/502/503), simulation on/off, 503 not stored, cache hit semantics, and full-history cache keys. Provider failures are faked at the lowest level, but the fake still calls the real `litellm.completion` (with `mock_response`), so LiteLLM's real cache is exercised.

### Demo video script (2–3 min)
1. Open the deployed frontend; say what it is. (20s)
2. Send "What is the capital of France?"; point at the metadata: source, model, latency, tokens. (20s)
3. Send "And what is its population?" to show multi-turn context. (15s)
4. Reload the page (new session), send the first question again: show `LLM_CACHE`, lower latency, same tokens. (20s)
5. Options → X-Simulate-Failure `key_1=429`, send a *new* question: show `key_2` and `fallbacks: 1`. (25s)
6. Set `key_1=429,key_2=500`, send a new question: show the red 503 message. (20s)
7. In a browser tab open `<backend>/health`, then `<backend>/sessions/<id>/messages` (session id is under the title). (25s)

---

## 5. Setup Used: your editor and AI tools

- Editor: Visual Studio Code
- AI assistant: Claude Code (Claude Sonnet) in VS Code, used to scaffold and test the code
- Libraries: FastAPI, LiteLLM, SQLAlchemy, pytest, React, Vite, Tailwind CSS v4
- Docker / Render for packaging and hosting

---

## 6. Bonus features (if any): what you added beyond the requirements and why

- Failure-header and system-prompt inputs in the UI, so failover can be demoed without curl.
- Per-session system prompt that is persisted and reused, and hidden from the history API.
- `/health` returns 503 if the DB, key pool or cache isn't ready (useful for Render health checks).
- Generic error handlers so no stack trace, HTML page or key ever reaches a client.

---

## Deploying on Render (manual, I have not deployed anything)

Render **persistent disks are a paid feature**. On a free web service the filesystem is ephemeral, so SQLite history is lost on restart/redeploy. Use a paid instance + disk if history must survive.

**A. Put the code on GitHub yourself**
1. Create an empty repo on github.com (don't add a README).
2. In the project folder:
```bash
git remote add origin https://github.com/YOUR-USER/YOUR-REPO.git
git push -u origin main
```
Check first that `git status` shows no `.env` file being added.

**B. Backend (Render Web Service)**
1. Render dashboard → **New → Web Service** → connect your repo.
2. Language/Runtime: **Docker**. Root Directory: leave empty (repo root). **Dockerfile Path:** `backend/Dockerfile`. (Build context = repo root.)
3. Health Check Path: `/health`.
4. Environment variables: `LLM_API_KEYS` (your real keys, comma-separated), `LLM_MODEL`, `DATABASE_URL=sqlite:////data/app.db`, `ENABLE_FAILURE_SIMULATION=true`, `ALLOWED_ORIGINS=http://localhost:3000` (temporary).
5. Instance type: a paid one → **Disks → Add Disk**, mount path `/data`.
6. Create/Deploy. Note the URL, e.g. `https://lyftr-ai-backend.onrender.com`. Open `/health`.

**C. Frontend (Render Static Site)**
1. **New → Static Site** → same repo. Name `lyftr-ai-frontend`.
2. Root Directory `frontend`; Build Command `npm install && npm run build`; Publish Directory `dist`.
3. Environment variable `VITE_API_BASE_URL=https://YOUR-BACKEND-NAME.onrender.com` (no trailing slash). It is embedded at build time, so **redeploy the frontend if you change it**.
4. Deploy; note the URL.

**D. Connect them**: edit the backend's `ALLOWED_ORIGINS` to your frontend URL (e.g. `https://lyftr-ai-frontend.onrender.com`, no trailing slash), save (it redeploys), then open the frontend and send a message. If the browser shows "Cannot reach the backend", it's a wrong `VITE_API_BASE_URL` or `ALLOWED_ORIGINS`.

Consider setting `ENABLE_FAILURE_SIMULATION=false` after your demo, since anyone could use the header.

## Security notes
- Keys only come from environment variables; `.env` is git-ignored; `.env.example` has placeholders.
- Keys never appear in responses, logs or the frontend bundle; only `key_1`, `key_2`... are exposed.
- CORS allows only the origins in `ALLOWED_ORIGINS`.
- Unhandled errors return `{"detail":"internal server error"}` with no trace.
