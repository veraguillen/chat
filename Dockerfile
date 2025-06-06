# Etapa de compilación para instalar dependencias
FROM python:3.11-slim AS builder

WORKDIR /app

# Instalación de dependencias mínimas del sistema para compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar y actualizar pip
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel 

# Crear ambiente virtual e instalar dependencias
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Etapa final para la imagen de producción
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias mínimas del sistema para ejecución
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar el entorno virtual desde la etapa de compilación
COPY --from=builder /opt/venv /opt/venv

# Configurar PATH para usar el entorno virtual
ENV PATH="/opt/venv/bin:$PATH"

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Copiar solamente los archivos necesarios para la aplicación
# Primero los archivos de configuración y código
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY main.py ./
COPY debug_startup.py ./
COPY gunicorn.conf.py ./

# Exponer el puerto
EXPOSE 8000

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

# Verificar que el script existe y tiene permisos de ejecución
RUN ls -la /app/start.sh && test -x /app/start.sh

# Comando para ejecutar la aplicación con diagnóstico previo
CMD ["/app/start.sh"]
