FROM python:3.11-slim

WORKDIR /app

# Instalación de dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . .

# Exponer el puerto
EXPOSE 8000

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Definir puerto con valor por defecto para desarrollo local
ENV PORT=8000

# Script de diagnóstico y arranque
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'echo "==== INICIANDO DIAGNÓSTICO DE ENTORNO ====" ' >> /app/start.sh && \
    echo 'echo "Variables de entorno:"' >> /app/start.sh && \
    echo 'echo "PORT=$PORT"' >> /app/start.sh && \
    echo 'echo "WEBSITES_PORT=$WEBSITES_PORT"' >> /app/start.sh && \
    echo 'echo "PGHOST: [presente=$PGHOST]"' >> /app/start.sh && \
    echo 'echo "DATABASE_URL: [presente=$DATABASE_URL]"' >> /app/start.sh && \
    echo 'python /app/debug_startup.py' >> /app/start.sh && \
    echo 'echo "==== INICIANDO APLICACIÓN ====" ' >> /app/start.sh && \
    echo 'exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 600 --log-level debug --capture-output main:app' >> /app/start.sh && \
    chmod +x /app/start.sh

# Comando para ejecutar la aplicación con diagnóstico previo
CMD ["/app/start.sh"]
