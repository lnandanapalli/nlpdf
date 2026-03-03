# NLPDF

AI-powered PDF processing using natural language.

Upload PDFs and describe what you want in plain English. The system uses Llama 3.1 to parse your instructions and executes the operations.

**Examples:**
- "compress this and split into 3 parts"
- "extract pages 5-10 and rotate page 7 by 90 degrees"
- "merge these files and compress the result"
- "convert this markdown to PDF on letter paper"

## Features

- **Natural Language Parsing** — Llama 3.1 via HuggingFace Inference API
- **PDF Operations** — Compress, split, merge, rotate, markdown-to-PDF (chainable)
- **Auth** — httpOnly cookie JWTs, refresh token rotation, email OTP, CSRF protection
- **Security** — File validation, CAPTCHA, rate limiting, Argon2id hashing

## Tech Stack

| Layer    | Technology                                          |
| -------- | --------------------------------------------------- |
| Frontend | React 19, TypeScript, Material UI, Vite             |
| Backend  | Python 3.13, FastAPI, SQLAlchemy, Alembic           |
| Database | SQL Server (aioodbc)                                |
| PDF      | pypdf, pikepdf, Pillow, xhtml2pdf                   |
| LLM      | HuggingFace Inference API                           |

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

| Method | Path               | Auth   | Purpose                             |
| ------ | ------------------ | ------ | ----------------------------------- |
| POST   | `/auth/signup`     | -      | Register, send OTP                  |
| POST   | `/auth/verify_otp` | -      | Verify OTP, set auth cookies        |
| POST   | `/auth/resend_otp` | -      | Resend OTP                          |
| POST   | `/auth/login`      | -      | Authenticate, set auth cookies      |
| POST   | `/auth/refresh`    | Cookie | Rotate token pair                   |
| POST   | `/auth/logout`     | Cookie | Revoke refresh token, clear cookies |
| GET    | `/auth/me`         | Cookie | Current user info                   |
| POST   | `/pdf/process`     | Cookie | Process PDFs with natural language  |
| GET    | `/health`          | -      | Health check                        |

## Docker

```bash
docker build -t nlpdf .
docker run -p 8000:8000 --env-file .env nlpdf
```

Packages the backend only. Frontend is deployed separately as static files.

## Testing

```bash
poetry run pytest tests/ -v
```

## Code Quality

Pre-commit hooks run `ruff`, `black`, `ty`, and `bandit` on every commit.

```bash
poetry run pre-commit install
```

## Environment Variables

See [`.env.example`](.env.example) (backend) and [`frontend/.env.example`](frontend/.env.example) (frontend).
