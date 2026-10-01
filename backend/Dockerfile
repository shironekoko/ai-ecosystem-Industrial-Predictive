# ── FastAPI Backend ──
# Build:  docker compose build backend
# Run:    docker compose up backend

FROM python:3.12-slim

# ── System deps ──
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl libpq-dev libgl1 libglib2.0-0 libgomp1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# ── Install uv ──
RUN pip install --no-cache-dir --timeout=120 uv

WORKDIR /app

# ── Install Python deps (cache layer) ──
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev

# ── Copy source ──
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
