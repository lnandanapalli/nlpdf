# NLPDF

AI-powered PDF processing using natural language.

## Idea

Upload a PDF and describe what you want to do with it in plain English. The system processes your request and returns the modified PDF.

Example: "compress this and split into 3 parts"

## Features

- **Natural Language Parsing**: Uses Llama 3.1 via HuggingFace Inference API to parse instructions into structured operations.
- **PDF Manipulation**: Merging, splitting, rotating, and compressing PDFs.
- **User Authentication**: JWT-based auth with email OTP verification on signup to prevent spam.
- **Relational Database**: Async SQLAlchemy with Alembic migrations.
- **Comprehensive Testing**: Over 130 tests covering unit functionality, integration, and security edge cases.
- **Security & Rate Limiting**: File validation, temporary file cleanup, and IP-based rate limiting.

## Structure

```
nlpdf/
├── backend/
│   ├── auth/         # JWT and password hashing
│   ├── crud/         # Database operations
│   ├── models/       # SQLAlchemy models
│   ├── routers/      # FastAPI endpoint definitions
│   ├── schemas/      # Pydantic validation models
│   ├── services/     # Core logic (LLM, PDF ops, email)
│   └── validators/   # Reusable validation logic
├── migrations/       # Alembic version control
├── tests/            # Comprehensive pytest suite
└── docker-compose.yml
```

## Getting Started

### Prerequisites

- Python 3.13
- Poetry
- Docker Desktop
- A HuggingFace API Token
- A [Resend](https://resend.com) API key (for OTP emails)

### Setup

1. **Install dependencies:**

   ```bash
   poetry install
   ```

2. **Configure the environment:**

   ```bash
   cp .env.example .env
   ```

   Fill in your secrets in `.env`.

3. **Start the database and run migrations:**

   ```bash
   docker compose up -d
   poetry run alembic upgrade head
   ```

4. **Start the API server:**

   ```bash
   poetry run uvicorn backend.main:app --reload
   ```

5. **API docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

## Code Quality

Pre-commit hooks run automatically on every `git commit`:

| Hook     | Purpose                         |
| -------- | ------------------------------- |
| `ruff`   | Linting and import sorting      |
| `black`  | Code formatting                 |
| `ty`     | Static type checking            |
| `bandit` | Security vulnerability scanning |

Install the hooks after cloning:

```bash
poetry run pre-commit install
```

To run them manually against all files:

```bash
poetry run pre-commit run --all-files
```

## Testing

```bash
poetry run pytest tests/ -v
```
