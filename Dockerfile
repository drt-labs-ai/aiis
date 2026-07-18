FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
COPY README.md* ./

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Pre-download sentence-transformers model (cache in image)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# Copy application code
COPY src/ ./src/
COPY knowledge-base/ ./knowledge-base/
COPY scripts/ ./scripts/

# Create data directory
RUN mkdir -p /app/data/chroma

EXPOSE 8000

CMD ["uvicorn", "src.api.webhook:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
