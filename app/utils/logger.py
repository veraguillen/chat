# app/utils/logger.py
import logging
import sys
import os
from logging.handlers import RotatingFileHandler

# --- Usar un nombre fijo para el logger ---
# Esto evita problemas si este archivo se importa antes de que 'settings' esté listo
# o si hay errores al cargar la configuración.
APP_LOGGER_NAME = "chatbot_multimarca_app"
# -----------------------------------------

# --- Configuración de Formato y Nivel ---
# Puedes cambiar log_level a logging.INFO para producción cuando ya no necesites debug
log_level = logging.DEBUG
log_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S" # Formato de fecha opcional
)
# -----------------------------------------

# --- Obtener y Configurar el Logger Principal de la App ---
logger = logging.getLogger(APP_LOGGER_NAME)
logger.setLevel(log_level)
# Evitar que los logs se propaguen al logger raíz (evita duplicados si raíz tiene handlers)
logger.propagate = False
# -----------------------------------------

# --- Configurar Handler para la Consola (StreamHandler) ---
# Asegurarse de que siempre haya salida a consola
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(log_level) # Mostrar DEBUG en consola también
    logger.addHandler(console_handler)
    print(f"Logger '{APP_LOGGER_NAME}': Handler de consola configurado con nivel {logging.getLevelName(log_level)}.") # Mensaje de confirmación
# -----------------------------------------

# --- Configurar Handler para el Archivo (RotatingFileHandler) ---
log_file_path = "chatbot.log" # En el directorio desde donde se ejecuta run.py
try:
    # Intentar crear el handler rotatorio
    # maxBytes: 1MB, backupCount: 3 archivos de respaldo
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=1000000, # 1 MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(log_level) # Guardar DEBUG en archivo también

    # Añadir handler de archivo al logger
    logger.addHandler(file_handler)
    logger.info(f"Logging a archivo configurado: {os.path.abspath(log_file_path)}")

except PermissionError:
    logger.warning(f"Error de permisos: No se puede escribir en '{log_file_path}'. Logging a archivo deshabilitado.")
except Exception as e:
    logger.error(f"Error al configurar el file handler para logging: {e}", exc_info=True)
    logger.warning("Logging a archivo deshabilitado debido a un error.")
# -----------------------------------------

# Log inicial para confirmar que el logger está listo
logger.debug(f"Logger '{APP_LOGGER_NAME}' inicializado y configurado.")

# --- Cómo usar en otros módulos ---
# Simplemente importa el logger:
# from app.utils.logger import logger
#
# logger.info("Este es un mensaje informativo.")
# logger.debug("Este es un mensaje de depuración.")
# logger.warning("Esta es una advertencia.")
# logger.error("Este es un error.")