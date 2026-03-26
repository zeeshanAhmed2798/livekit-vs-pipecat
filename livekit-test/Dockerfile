FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config \
    ffmpeg libportaudio2 portaudio19-dev libasound2 \
    libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswresample-dev libswscale-dev \
    libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY agent.py .
CMD ["python", "agent.py", "start"]
