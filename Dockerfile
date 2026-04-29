FROM python:3.11-slim

# ── System deps (lxml, etc. need libxml2) ────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# ── App directory structure ───────────────────────────────────────
# /app/
#   backend/   ← Python source + requirements.txt
#   frontend/  ← Static HTML/CSS/JS (served by FastAPI)
WORKDIR /app

# Copy backend source
COPY backend/ ./backend/

# Copy frontend static files
COPY frontend/ ./frontend/

# ── Install Python dependencies ───────────────────────────────────
RUN pip install --upgrade pip && \
    pip install --prefer-binary -r ./backend/requirements.txt

# ── Tell main.py where the frontend lives ────────────────────────
ENV FRONTEND_DIR=/app/frontend

# ── Run from the backend directory so imports resolve ─────────────
WORKDIR /app/backend

EXPOSE 10000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]