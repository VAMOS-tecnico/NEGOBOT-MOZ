FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements-workers.txt ./
RUN pip install --no-cache-dir -r requirements-workers.txt

COPY services ./services
COPY config.py ./config.py
COPY ai_worker.py image_worker.py audio_worker.py social_poster_worker.py mailer_worker.py ./

CMD ["python", "ai_worker.py"]
