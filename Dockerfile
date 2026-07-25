# Gemeinsames Image für api, scheduler und alle worker.
# ffmpeg + eine Linux-Schriftart (für Pillow-Overlays) sind Systempakete.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1
# Command wird je Service in docker-compose.yml gesetzt.
