FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /api

# Dependencias para OpenCV y utilidades de red
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /api/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /api

RUN chmod +x /api/entrypoint.sh /api/iniciar.sh 2>/dev/null || true

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "/api/entrypoint.sh"]
