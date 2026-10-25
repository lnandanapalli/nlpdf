# NLPDF

AI-powered PDF processing using natural language.

![Demo](demo/demo.gif)

Upload PDFs and describe what you want in plain English. The system uses Llama 3.1 (via HuggingFace) to parse your instructions and executes the operations. If HuggingFace is unavailable, requests automatically fall back to OpenAI gpt-4o-mini.

**Examples:**

- "compress this and split into 3 parts"
- "extract pages 5-10 and rotate page 7 by 90 degrees"
- "merge these files and compress the result"
- "convert this markdown to PDF on letter paper"

## Features

- **Natural Language Parsing** -Llama 3.1 via HuggingFace Inference API, with automatic OpenAI fallback on failure
- **PDF Operations** -Compress, split, merge, rotate, markdown-to-PDF (chainable and deterministic)
- **Auth** -httpOnly cookie JWTs, refresh token rotation, email OTP, CSRF protection
- **Security & Robustness** -File validation, CAPTCHA, rate limiting, Argon2id hashing, OOM protection for massive images, and safe Unicode chunked decoding for large files
- **Persistent Logging** - Daily-rotated file logging with a hardcoded 30-day retention window. Uses persistent `/home/nlpdf_logs` in production and `./logs` in development, with startup and hourly cleanups to prune old logs.

## Tech Stack

| Layer    | Technology                                                         |
| -------- | ------------------------------------------------------------------ |
| Frontend | React 19, TypeScript, Material UI, Vite                            |
| Backend  | Python 3.13, FastAPI, SQLAlchemy, Alembic                          |
| Database | SQL Server (aioodbc)                                               |
| PDF      | pypdf, pikepdf, Pillow, xhtml2pdf                                  |
| LLM      | HuggingFace Inference API (primary), OpenAI gpt-4o-mini (fallback) |

## Project Structure

```
nlpdf/
├── backend/
│   ├── auth/         # JWT, cookies, CSRF, password hashing
│   ├── crud/         # Database operations
│   ├── models/       # SQLAlchemy models
│   ├── routers/      # API endpoint definitions
│   ├── schemas/      # Pydantic request/response models
│   ├── services/     # Core logic (LLM, PDF ops, email, CAPTCHA)
│   └── validators/   # Input validation
├── frontend/src/
│   ├── components/   # React components
│   └── services/     # API client
├── migrations/       # Alembic migrations
├── tests/            # pytest suite
└── Dockerfile
```

## Getting Started

**Prerequisites:** Python 3.13, [Poetry](https://python-poetry.org/), Node.js 20+, Docker

```bash
# Backend
poetry install
cp .env.example .env        # fill in your secrets

# Frontend
cd frontend && npm install
cp .env.example .env        # fill in your secrets
cd ..

# Database
docker compose up -d
poetry run alembic upgrade head

# Run
poetry run uvicorn backend.main:app --reload   # backend at :8000
cd frontend && npm run dev                      # frontend at :5173
```

API docs available at [localhost:8000/docs](http://localhost:8000/docs) when running.

## API Endpoints

| Method | Path                           | Auth   | Purpose                                                  |
| ------ | ------------------------------ | ------ | -------------------------------------------------------- |
| POST   | `/auth/signup`                 | -      | Register, send OTP                                       |
| POST   | `/auth/verify_otp`             | -      | Verify OTP and set the password, set auth cookies        |
| POST   | `/auth/resend_otp`             | -      | Resend OTP to an unverified email                        |
| POST   | `/auth/login`                  | -      | Authenticate, set auth cookies                           |
| POST   | `/auth/refresh`                | Cookie | Rotate token pair                                        |
| POST   | `/auth/logout`                 | Cookie | End this device's session, clear cookies                 |
| GET    | `/auth/me`                     | Cookie | Current user info                                        |
| PUT    | `/auth/profile`                | Cookie | Update first/last name                                   |
| POST   | `/auth/change-password`        | Cookie | Change password, revoke all other sessions               |
| GET    | `/auth/sessions`               | Cookie | List active sessions (devices)                           |
| DELETE | `/auth/sessions/{session_id}`  | Cookie | Sign out one device                                      |
| POST   | `/auth/sessions/logout-all`    | Cookie | Sign out every other device immediately                  |
| POST   | `/auth/delete-account/request` | Cookie | Check password, email a deletion code                    |
| POST   | `/auth/delete-account/confirm` | Cookie | Delete the account with the emailed code                 |
| POST   | `/auth/forgot-password`        | -      | Email a password reset code                              |
| POST   | `/auth/reset-password`         | -      | Reset password with the code, revoke all sessions        |
| POST   | `/pdf/process`                 | Cookie | Process PDFs/Markdown with natural language              |
| GET    | `/documents`                   | Cookie | Paginated processing history                             |
| DELETE | `/documents/{document_id}`     | Cookie | Delete one history entry                                 |
| DELETE | `/documents`                   | Cookie | Clear all history                                        |
| GET    | `/health`                      | -      | Health check (includes a database query)                 |

## Docker

```bash
docker build -t nlpdf .
docker run -p 8000:8000 --env-file .env nlpdf
```

The image is a two-stage build: dependencies (including pycairo, which has no
Linux wheels) compile in a builder stage, and the final image holds only the
virtualenv, the app and runtime libraries (ODBC Driver 18, cairo). It runs as
a non-root user and logs to stdout. On Azure App Service that output is in
Log stream, App Service logs and (via diagnostic settings) Log Analytics; set
`LOG_DIR` only if you also want rotated log files, and point it somewhere
persistent and writable (on App Service, under `/home` with
`WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`).

Packages the backend only. Frontend is deployed separately as static files.

## Testing

| Suite | Where | What it covers |
| ----- | ----- | -------------- |
| Backend unit | `tests/` | Services, validators, schemas, auth helpers, logging, startup cleanup |
| Backend integration | `tests/integration/` | The full app (all middleware and routers) on SQLite: PDF pipeline, CSRF/CORS, auth security properties |
| Property-based | `tests/test_properties.py` | Fuzzes LLM replies, page ranges and forwarded IPs with Hypothesis |
| Migrations | `tests/test_migrations.py` | Upgrade, downgrade and model/migration drift on a scratch SQL Server database (skipped if none is reachable) |
| Frontend unit | `frontend/src/**/*.test.ts(x)` | API client (token refresh, CSRF, error messages) and key screens, with Vitest |
| End-to-end | `frontend/e2e/` | Real browser against the real backend and database; only the LLM, email and Turnstile are faked |

```bash
# Backend (unit + integration + property + migrations)
poetry run pytest

# Frontend unit tests
cd frontend && npm test

# End-to-end (needs SQL Server up and migrated; starts its own servers on ports 8001/5174)
docker compose up -d sqlserver && poetry run alembic upgrade head
cd frontend && npx playwright install chromium && npm run test:e2e
```

The e2e backend is `tests/e2e_support/app.py`: the real application with a
scripted LLM, an in-memory email outbox and the server-side CAPTCHA check
stubbed. It refuses to start with `APP_ENV=production`, sends no real email,
and only creates (and cleans up) `e2e-*@example.com` accounts.

## Code Quality

Pre-commit hooks run `ruff`, `black`, `ty`, `bandit`, `pip-audit`, and `detect-secrets` on every commit.

```bash
poetry run pre-commit install
```
 
Secrets are managed via `.secrets.baseline`. If a commit is blocked by `detect-secrets`:
1.  Verify the "secret" is safe (e.g. a mock string or migration ID).
2.  Update the baseline: `poetry run detect-secrets scan > .secrets.baseline`.
3.  Stage the updated `.secrets.baseline` and try again.

## Environment Variables

See [`.env.example`](.env.example) (backend) and [`frontend/.env.example`](frontend/.env.example) (frontend).

### LLM Configuration

The backend uses HuggingFace as the primary LLM provider. If HuggingFace fails for any reason, it automatically falls back to OpenAI for that request.

| Variable                | Required | Description                                                                            |
| ----------------------- | -------- | -------------------------------------------------------------------------------------- |
| `HUGGINGFACE_API_TOKEN` | Yes      | HuggingFace token from [hf.co/settings/tokens](https://huggingface.co/settings/tokens) |
| `OPENAI_API_KEY`        | No       | OpenAI key used as fallback. Leave blank to disable.                                   |
| `OPENAI_MODEL`          | No       | Defaults to `gpt-4o-mini`                                                              |
