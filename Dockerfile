FROM python:3.12-slim-bookworm AS build
ENV UV_LINK_MODE=copy UV_NO_CACHE=1
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.24
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa poppler-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 nexo \
    && mkdir var && chown nexo:nexo var
COPY --from=build /app/.venv /app/.venv
USER nexo
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=20s --start-period=30s --retries=3 \
    CMD ["/app/.venv/bin/python", "-m", "nexolicitcr.healthcheck"]
CMD ["/app/.venv/bin/nexolicit", "api", "--host", "0.0.0.0", "--no-worker"]
