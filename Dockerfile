# SROT Backend Production Container
# Targets Render Docker Web Service with Persistent Disk mounted at /var/data

FROM python:3.11-slim-bookworm

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    SROT_DATA=/var/data \
    PORT=8077

WORKDIR /app

# 1. Install required system dependencies:
#    - ffmpeg + ffprobe: Frame sampling & stress testing
#    - tesseract-ocr + eng, hin, pan: Multilingual OCR
#    - fonts-dejavu-core + fontconfig: Report rendering and demo video text
#    - libpango, libcairo, libgdk-pixbuf: WeasyPrint PDF compilation
#    - curl: Container health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-pan \
    fonts-dejavu-core \
    fontconfig \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Install PyTorch CPU wheels and Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# 3. Pre-bake exact pinned neural model revision into container image:
#    umm-maybe/AI-image-detector @ c7e223baf11bc40528af364ba7bdea030ef42f9e
#    This guarantees offline operation on Render without downloading during startup.
RUN python -c 'from transformers import pipeline; pipeline("image-classification", model="umm-maybe/AI-image-detector", revision="c7e223baf11bc40528af364ba7bdea030ef42f9e")'

# 4. Enforce offline mode for runtime
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# 5. Create persistent data mount point
RUN mkdir -p /var/data

# 6. Copy backend application code
COPY backend /app/backend

# Render dynamically sets $PORT at runtime
EXPOSE 8077

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8077} --app-dir backend"]
