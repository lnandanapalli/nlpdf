FROM python:3.14-slim-bookworm

# Install ODBC Driver 18 for Azure SQL
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    curl gnupg2 apt-transport-https unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
    > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y --auto-remove curl gnupg2 apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

WORKDIR /app

# Install Python dependencies (layer cached until lock file changes)
COPY pyproject.toml poetry.lock ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libcairo2-dev \
    && poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi \
    && pip cache purge \
    && apt-get purge -y --auto-remove gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY backend/ ./backend/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Non-root user
RUN useradd -r -s /usr/sbin/nologin appuser \
    && mkdir -p /tmp/nlpdf_uploads \
    && chown appuser:appuser /tmp/nlpdf_uploads
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
