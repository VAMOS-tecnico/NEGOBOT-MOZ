FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak-ng fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-video.txt ./requirements-video.txt
RUN pip install --no-cache-dir -r requirements-video.txt

COPY video_service.py video_pipeline.py video_worker.py ./
COPY services ./services

RUN mkdir -p /var/lib/negobot/videos
EXPOSE 8080

CMD ["uvicorn", "video_service:app", "--host", "0.0.0.0", "--port", "8080"]
