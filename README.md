# NLPDF

AI-powered PDF processing using natural language.

## Idea

Upload a PDF and describe what you want to do with it in plain English. The system processes your request and returns the modified PDF.

Example: "compress this and split into 3 parts"

## Features

- **Natural Language Parsing**: Uses Llama 3.1 via HuggingFace Inference API to parse natural language instructions into structured operations.
- **PDF Manipulation**: Merging, splitting, rotating, and compressing PDFs (using `pypdf`, `pikepdf`, and `Pillow`).
- **User Authentication**: Secure JWT-based signup and login flow using `bcrypt`.
- **Relational Database**: Dockerized PostgreSQL with robust async SQLAlchemy sessions and Alembic migrations.
- **Comprehensive Testing**: Over 130 tests covering unit functionality, integration, and security edge cases.
- **Security & Rate Limiting**: File validation (magic bytes, size limits), temporary file cleanup, and IP-based rate limiting via `slowapi`.

## Structure

```
nlpdf/
├── backend/
│   ├── auth/         # JWT and password hashing
│   ├── crud/         # Database operations
│   ├── models/       # SQLAlchemy models
│   ├── routers/      # FastAPI endpoint definitions
│   ├── schemas/      # Pydantic validation models
│   ├── services/     # Core logic (LLM, PDF ops)
│   └── validators/   # Reusable validation logic
├── migrations/       # Alembic version control
├── tests/            # Comprehensive pytest suite
└── docker-compose.yml
```

## Getting Started

### Prerequisites

- Python 3.13
- Poetry
- Docker Desktop (for PostgreSQL)
- A HuggingFace API Token (for the LLM)

### Setup

1. **Clone the repository and install dependencies:**

   ```bash
   poetry install
   ```

2. **Start the Database:**

   ```bash
   docker compose up -d
   ```

3. **Configure the Environment:**
   Copy `.env.example` to `.env` and fill in your secrets.

   ```bash
   cp .env.example .env
   ```

   _Note: Ensure `HUGGINGFACE_API_TOKEN` and `JWT_SECRET_KEY` are set._

4. **Run Database Migrations:**

   ```bash
   poetry run alembic upgrade head
   ```

5. **Start the API Server:**

   ```bash
   poetry run uvicorn backend.main:app --reload
   ```

6. **API Documentation:**
   Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser to interact with the API endpoints.

## Testing

Run the full test suite (requires dependencies including `aiosqlite` for the in-memory test database):

```bash
poetry run pytest tests/ -v
```

Code quality and formatting are enforced with `ruff`, `black`, and `ty` type checking.
