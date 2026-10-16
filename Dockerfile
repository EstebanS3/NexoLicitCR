FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa poppler-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.12.24 \
    && useradd --create-home --uid 10001 nexo
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev && mkdir var && chown nexo:nexo var
USER nexo
EXPOSE 8000
CMD ["/app/.venv/bin/nexolicit", "api"]
