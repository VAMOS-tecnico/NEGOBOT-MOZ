FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir Flask gunicorn

COPY index.html platform.html assistant.html site_server.py ./
COPY platform-react/dist ./platform-react/dist

RUN python -m py_compile site_server.py

EXPOSE 3000
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "2", "--timeout", "60", "site_server:app"]
