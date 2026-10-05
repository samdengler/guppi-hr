# Probe image for the Runtime V2 cold start study (docs/runtime-v2-experiments.md).
# Build arguments: PAD_MB (random bytes never read, for the image size experiment) and
# NOPYC (1 ships no bytecode and forbids writing it; the default compiles it in).
FROM --platform=linux/arm64 python:3.12-slim
ARG PAD_MB=0
ARG NOPYC=
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt \
    && if [ -z "$NOPYC" ]; then python -m compileall -q /usr/local/lib/python3.12 || true; \
       else find /usr/local/lib/python3.12 -name '__pycache__' -type d -prune -exec rm -rf {} +; fi
RUN if [ "$PAD_MB" -gt 0 ]; then head -c ${PAD_MB}M /dev/urandom > /app/pad.bin; fi
COPY server.py .
RUN if [ -z "$NOPYC" ]; then python -m compileall -q /app; fi
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=${NOPYC}
EXPOSE 8080 8000 9000
CMD ["python", "server.py"]
