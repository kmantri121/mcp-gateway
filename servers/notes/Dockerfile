# syntax=docker/dockerfile:1
# Build from the repo root so the shared pyproject.toml and uv.lock are in the context:
#   docker build -f servers/notes/Dockerfile .

# Stage 1: install the locked dependencies into /app/.venv.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv
# Compile .pyc at build time for faster startup; copy files out of the cache mount
# instead of hard-linking; use the image's Python rather than downloading one.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
# --locked fails the build if uv.lock is out of date with pyproject.toml.
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

# Stage 2: runtime image with only the venv and the server code, no uv.
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY servers/notes/server.py ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 HOST=0.0.0.0
USER app
EXPOSE 8000
# The slim image has no curl, so probe /health with Python's standard library.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["python", "server.py"]
