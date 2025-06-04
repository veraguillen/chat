@echo off
setlocal

:: Configuración inicial
set PYTHONPATH=%PYTHONPATH%;%CD%

:: Crear directorio de logs si no existe
if not exist "logs" mkdir logs

:: Variables de entorno
set ENVIRONMENT=production
set LOG_LEVEL=INFO

:: Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt

:: Ejecutar migraciones de base de datos
echo Ejecutando migraciones...
alembic upgrade head

:: Iniciar la aplicación
echo Iniciando la aplicación...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

endlocal