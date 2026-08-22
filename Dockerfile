FROM python:3.11-slim

WORKDIR /app

# Dependências mínimas do sistema: compilação Python e validação/conversão de áudio.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc ffmpeg tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
