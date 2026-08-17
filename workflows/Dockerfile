FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema se necessário
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala os requisitos do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código fonte para dentro do container
COPY . .

EXPOSE 5000

# Comando para iniciar a aplicação com Gunicorn (porta 5000)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
