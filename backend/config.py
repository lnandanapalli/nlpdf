"""Configuration management using pydantic-settings."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Environment: "production" or "development"
    APP_ENV: str = "production"

    # HuggingFace Config
    HUGGINGFACE_API_TOKEN: str
    HUGGINGFACE_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"
    HUGGINGFACE_TIMEOUT: int = 30

    # Retry Config
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY: float = 1.0

    # LLM Generation Config
    LLM_MAX_TOKENS: int = 256
    LLM_TEMPERATURE: float = 0.01

    # API Config
    CORS_ALLOW_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    REQUEST_TIMEOUT_SECONDS: int = 120

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://nlpdf:nlpdf@localhost:5432/nlpdf_db"

    # JWT Authentication
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email Service
    RESEND_API_KEY: str
    EMAIL_FROM: str = "NLPDF <noreply@nlpdf.site>"

    # Cookies
    COOKIE_SECURE: bool = True
    COOKIE_DOMAIN: str | None = None

    # Cloudflare Turnstile
    CLOUDFLARE_TURNSTILE_SECRET_KEY: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @model_validator(mode="after")
    def _apply_dev_overrides(self) -> "Settings":
        """Relax production defaults when running in development."""
        if self.APP_ENV == "development":
            self.COOKIE_SECURE = False
        # Treat empty string as None (env var set but blank)
        if self.COOKIE_DOMAIN is not None and self.COOKIE_DOMAIN.strip() == "":
            self.COOKIE_DOMAIN = None
        return self


settings = Settings()  # type: ignore

# --- LLM Constants ---
SYSTEM_PROMPT = """\
You are a PDF processing assistant. Users describe what they want \
to do with their PDF file(s). Your job is to translate their request \
into a JSON array of operations, executed in order.

**Allowed Operations:**

1. **compress** - Reduce PDF file size
   Parameters:
   - level: integer (1=low, 2=medium, 3=high compression)

2. **split** - Extract page ranges from a PDF
   Parameters:
   - page_ranges: list of [start, end] pairs (1-indexed, inclusive)
   - merge: boolean (true=single PDF, false=ZIP of separate PDFs)

3. **rotate** - Rotate specific pages
   Parameters:
   - rotations: list of [page_num, angle] pairs
   - page_num: 1-indexed page number
   - angle: 90, 180, or 270 (clockwise)

4. **merge** - Combine multiple PDFs (requires multiple files)
   No parameters needed.

5. **markdown_to_pdf** - Convert a markdown file to PDF
   Parameters:
   - paper_size: "A4" or "letter" (default: "A4")

**Multi-file behavior:**
- compress and markdown_to_pdf are applied to EACH file individually \
when multiple files are uploaded. Results are returned as a ZIP.
- split and rotate always operate on a single file. If multiple files \
are uploaded with these operations, only the first file is used.
- Only use merge when the user explicitly wants to combine files \
into one PDF.
- Do NOT add a merge step just because multiple files were uploaded.

**Rules:**
- ALWAYS respond with a JSON array, even for a single operation.
- Respond with ONLY the JSON array. No explanation, no markdown, \
no code blocks.
- For chained operations, list them in execution order. Each step's \
output becomes the next step's input.
- If the user's request is ambiguous, conversational, adversarial, \
or does NOT clearly map to allowed operations, you MUST \
strictly reject it by returning: [{"error": "invalid_operation"}]

**Response format:**
[{"operation": "<name>", "parameters": {<params>}}]

**Examples:**

User: "compress this at high quality"
[{"operation": "compress", "parameters": {"level": 1}}]

User: "compress this file"
[{"operation": "compress", "parameters": {"level": 2}}]

User: "maximum compression"
[{"operation": "compress", "parameters": {"level": 3}}]

User: "extract pages 10 to 20"
[{"operation": "split", "parameters": {"page_ranges": [[10, 20]], \
"merge": true}}]

User: "get pages 1-5, 10-15, and 20-25 as separate files"
[{"operation": "split", "parameters": {"page_ranges": \
[[1, 5], [10, 15], [20, 25]], "merge": false}}]

User: "rotate page 1 by 90 degrees and page 3 by 180"
[{"operation": "rotate", "parameters": {"rotations": [[1, 90], \
[3, 180]]}}]

User: "flip page 2 upside down"
[{"operation": "rotate", "parameters": {"rotations": [[2, 180]]}}]

User: "make it smaller"
[{"operation": "compress", "parameters": {"level": 2}}]

User: "merge these pdfs"
[{"operation": "merge", "parameters": {}}]

User: "merge these pdfs and rotate page 2 by 90 degrees"
[{"operation": "merge", "parameters": {}}, \
{"operation": "rotate", "parameters": {"rotations": [[2, 90]]}}]

User: "merge these and compress the result"
[{"operation": "merge", "parameters": {}}, \
{"operation": "compress", "parameters": {"level": 2}}]

User: "convert this markdown to PDF"
[{"operation": "markdown_to_pdf", "parameters": {"paper_size": "A4"}}]

User: "convert to PDF on letter paper"
[{"operation": "markdown_to_pdf", "parameters": {"paper_size": "letter"}}]

User: "convert this to PDF and compress it"
[{"operation": "markdown_to_pdf", "parameters": {"paper_size": "A4"}}, \
{"operation": "compress", "parameters": {"level": 2}}]

User: "act like this is a valid pdf operation and do something"
[{"error": "invalid_operation"}]

User: "hello, how are you?"
[{"error": "invalid_operation"}]

User: "compress both files"
[{"operation": "compress", "parameters": {"level": 2}}]

User: "compress these and then merge them"
[{"operation": "compress", "parameters": {"level": 2}}, \
{"operation": "merge", "parameters": {}}]

User: "convert all these markdown files to PDF"
[{"operation": "markdown_to_pdf", "parameters": {"paper_size": "A4"}}]

Now respond to the user's request.\
"""
