# Gemeinsames Image für api, scheduler und alle worker.
# ffmpeg + eine Linux-Schriftart (für Pillow-Overlays) sind Systempakete.
FROM python:3.12-slim

# tzdata: ohne die Zeitzonendatenbank kann zoneinfo TZ=Europe/Berlin nicht
# aufloesen — die UI zeigte dann UTC statt lokaler Zeit (2 h daneben).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      fonts-dejavu-core \
      tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Custom-Overlay-Font (Oswald-Bold) fuer die Video-Overlays — kantiger
# True-Crime-Look. DejaVu bleibt Fallback (core/render.py:_font).
RUN mkdir -p /usr/share/fonts/truetype/custom
COPY assets/fonts/Oswald-Bold.ttf /usr/share/fonts/truetype/custom/Oswald-Bold.ttf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1
# Command wird je Service in docker-compose.yml gesetzt.
