# LLM Chatbot with Key Failover and Response Caching

React + FastAPI chatbot that calls Gemini through LiteLLM, fails over between API keys, uses LiteLLM's built-in response cache, and stores conversations in SQLite.

## 1. Live URLs

- Frontend: Not deployed yet.
- Backend: Not deployed yet.

## 2. Run locally: with Docker and without

Copy `.env.example` to `.env` and set `LLM_API_KEYS=key1,key2` (`.env` is git-ignored).

**Without Docker** (this is what was run and tested)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000      # set DATABASE_URL=sqlite:///./app.db for local runs
```
```bash
cd frontend
npm install
npm run dev                            # http://localhost:3000
```
Backend tests: `cd backend && python -m pytest -q` (34 pass). Frontend build: `cd frontend && npm run build` (succeeds).

**With Docker**: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` and a Makefile (`make up`, `make down`) are written, but they have **not been built or run** yet because Docker is not installed on the development machine.

Endpoints: `GET /health`, `POST /chat`, `GET /sessions/{session_id}/messages`.

## 3. Design decisions: key fallback, caching, SQLite session storage

- **Key fallback:** keys are tried in order (`key_1`, `key_2`, ...) with real `litellm.completion` calls. Failover happens on 429, 5xx, timeouts, connection errors and 401/403. If all fail the API returns 503 `{"detail":"all providers unavailable"}` and nothing is saved. `X-Simulate-Failure` (e.g. `key_1=429`, `*=429`) simulates failures for one request when `ENABLE_FAILURE_SIMULATION=true`.
- **Caching:** `litellm.Cache(type="local")` (in-memory). The key is built from the model and the full message list, not the session id or API key. Cache hits are detected with LiteLLM's `cache_hit` flag and return `LLM_CACHE`, `key_id: null`, `fallback_attempts: 0` and the original token counts. The cache resets when the backend restarts.
- **SQLite:** table `messages(id, session_id, role, content, metadata, created_at)`. The client sends only the new message; the backend loads history. User and assistant rows are saved together only after a successful reply.

## 4. Verification: how to see failover, cache hits and per-message token usage

Verified by the automated tests (provider calls faked, real LiteLLM cache used) and a live run with fake keys (real Gemini returned 401, failover reached 503). Not yet verified with real Gemini keys.

```bash
# same message in two sessions -> second is LLM_CACHE
curl -X POST localhost:8000/chat -H "Content-Type: application/json" -d '{"session_id":"a","message":"Name three rivers"}'
curl -X POST localhost:8000/chat -H "Content-Type: application/json" -d '{"session_id":"b","message":"Name three rivers"}'

# failover: key_2 answers, fallback_attempts 1
curl -X POST localhost:8000/chat -H "Content-Type: application/json" -H "X-Simulate-Failure: key_1=429" -d '{"session_id":"c","message":"A new question"}'

# all keys fail -> 503
curl -i -X POST localhost:8000/chat -H "Content-Type: application/json" -H "X-Simulate-Failure: *=429" -d '{"session_id":"d","message":"Another new question"}'

# per-message token usage
curl localhost:8000/sessions/a/messages
```

## 5. Setup Used: your editor and AI tools

- Editor: Visual Studio Code
- AI tool: Claude Code
- Stack: FastAPI, LiteLLM, SQLAlchemy, pytest, React, Vite, Tailwind CSS

## 6. Bonus features (if any): what you added beyond the requirements and why

- Optional system prompt and failure-header inputs in the UI, so failover can be shown without curl.
