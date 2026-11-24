# Build context is the REPOSITORY ROOT (so Render and docker-compose both work):
#   docker build -f backend/Dockerfile .

# ---- Stage 1: install dependencies into a virtualenv ----
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# ---- Stage 2: small runtime image ----
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATABASE_URL=sqlite:////data/app.db
# libsndfile is needed by the 'soundfile' module that litellm imports.
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY backend/app ./app
# /data holds SQLite. Mount a volume (compose) or Render Persistent Disk here.
RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000
# Render injects $PORT; default 8000 for local use.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
