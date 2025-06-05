FROM python:3.11-slim

WORKDIR /app

# Instalación de dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
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

# Comando para ejecutar la aplicación con la ruta correcta a la instancia app
# La instancia 'app' está en app/__init__.py, NO en app/main.py
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --timeout 600 -k uvicorn.workers.UvicornWorker app:app"]
