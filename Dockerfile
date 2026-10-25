# Two stages: dependencies are compiled in "builder", and only the resulting
# virtualenv is copied into the final image, so compilers and -dev headers
# never ship. Both stages must use the same base image: the virtualenv points
# at that image's Python.
ARG PYTHON_IMAGE=python:3.13-slim-bookworm

# ---- Build stage ------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder

# pycairo (pulled in by xhtml2pdf) has no Linux wheels and compiles here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc pkg-config libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Pinned so a new Poetry release can't change what an unchanged lock file
# installs; keep in step with the version used locally and in CI.
ARG POETRY_VERSION=2.5.1
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# Poetry installs into the activated virtualenv instead of creating its own.
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1
RUN python -m venv /opt/venv

WORKDIR /build
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-ansi

# ---- Runtime stage ----------------------------------------------------------
FROM ${PYTHON_IMAGE}

# Runtime libraries only: the Microsoft ODBC driver for SQL Server and cairo.
# libgssapi-krb5-2 is loaded by the ODBC driver but not declared by its
# package; without it here, purging curl removes it and every DB connection
# fails with "Can't open lib ... file not found".
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg2 \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
    > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 libgssapi-krb5-2 libcairo2 \
    && apt-get purge -y --auto-remove curl gnupg2 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/opt/venv/bin:$PATH \
    # Logs go to stdout, which App Service collects; don't hold them in a buffer.
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
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
