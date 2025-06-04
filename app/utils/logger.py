# app/utils/logger.py
import logging
import sys
from logging.handlers import RotatingFileHandler
# NO importar 'settings' aquí a nivel de módulo
from pathlib import Path
# Crear el logger base. Su configuración final se hará en setup_logging.
logger = logging.getLogger("ChatbotMultimarcaBeta") # O un nombre más genérico si PROJECT_NAME no está disponible aquí
logger.setLevel(logging.DEBUG) # Nivel base muy permisivo, se ajustará.

_is_logger_configured = False # Flag para evitar reconfiguración múltiple

def setup_logging(app_settings): # Recibe la instancia de settings ya inicializada
    global _is_logger_configured
    
    # Usar un print aquí es más seguro si el logger aún no está configurado para la consola
    print(f"DEBUG PRINT [logger.py - setup_logging]: Iniciando configuración del logger. ¿Ya configurado?: {_is_logger_configured}")

    if _is_logger_configured and not getattr(app_settings, 'FORCE_LOGGER_RECONFIGURATION', False):
        # Si ya está configurado y no se fuerza reconfiguración, no hacer nada.
        # Esto puede ser útil con Uvicorn reload para no duplicar handlers.
        print(f"DEBUG PRINT [logger.py - setup_logging]: Logger ya configurado y no se fuerza reconfiguración. Saltando.")
        return

    if not app_settings:
        print("ERROR CRÍTICO [logger.py - setup_logging]: app_settings no fue provisto. Usando config de emergencia para logger.", file=sys.stderr)
        # Configurar un handler de emergencia si settings no está
        emergency_handler = logging.StreamHandler(sys.stderr)
        emergency_formatter = logging.Formatter('%(asctime)s - %(name)s - EMERGENCY - %(levelname)s - %(message)s')
        emergency_handler.setFormatter(emergency_formatter)
        if not logger.handlers: logger.addHandler(emergency_handler) # Añadir solo si no hay ninguno
        logger.setLevel(logging.ERROR)
        _is_logger_configured = True # Marcar como configurado (de emergencia)
        return

    # Limpiar handlers existentes para evitar duplicación, especialmente con Uvicorn reload
    if logger.handlers:
        print(f"DEBUG PRINT [logger.py - setup_logging]: Limpiando {len(logger.handlers)} handlers existentes del logger '{logger.name}'.")
        for handler in logger.handlers[:]:
            try:
                handler.close() # Cerrar el handler, especialmente importante para FileHandlers
            except Exception as e_close:
                print(f"DEBUG PRINT [logger.py - setup_logging]: Excepción al cerrar handler {handler}: {e_close}", file=sys.stderr)
            logger.removeHandler(handler)
    
    # Obtener el nivel de log del objeto settings (ya debería estar normalizado)
    log_level_str = app_settings.LOG_LEVEL 
    numeric_level = getattr(logging, log_level_str, logging.INFO) # Fallback a INFO
    logger.setLevel(numeric_level)
    print(f"DEBUG PRINT [logger.py - setup_logging]: Nivel del logger '{logger.name}' establecido a {log_level_str} ({numeric_level}).")

    # Handler para la consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(app_settings.LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    # El handler de consola puede tener un nivel diferente si se desea, ej. siempre INFO
    # console_handler.setLevel(logging.INFO) 
    logger.addHandler(console_handler)
    print(f"DEBUG PRINT [logger.py - setup_logging]: Console handler añadido al logger '{logger.name}'.")

    # Handler para el archivo (si LOG_FILE y LOG_DIR están definidos y son válidos)
    if app_settings.LOG_FILE and isinstance(app_settings.LOG_FILE, Path) and \
       app_settings.LOG_DIR and isinstance(app_settings.LOG_DIR, Path):
        try:
            app_settings.LOG_DIR.mkdir(parents=True, exist_ok=True) # Asegurar que el directorio exista
            
            file_handler = RotatingFileHandler(
                filename=app_settings.LOG_FILE, 
                maxBytes=app_settings.LOG_MAX_SIZE_BYTES, 
                backupCount=app_settings.LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_formatter = logging.Formatter(app_settings.LOG_FORMAT)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            # Loguear usando el logger recién configurado
            logger.info(f"Logging a archivo también configurado: {app_settings.LOG_FILE} (Nivel: {log_level_str})")
            print(f"DEBUG PRINT [logger.py - setup_logging]: File handler añadido para {app_settings.LOG_FILE}.")
        except Exception as e_fh:
            # Si falla el file handler, al menos el console handler debería funcionar
            logger.error(f"No se pudo configurar el logging a archivo {app_settings.LOG_FILE}: {e_fh}", exc_info=True)
            print(f"ERROR PRINT [logger.py - setup_logging]: Error configurando file handler: {e_fh}", file=sys.stderr)
    else:
        logger.warning("LOG_FILE o LOG_DIR no definidos correctamente en settings. Logging a archivo deshabilitado.")
        print(f"DEBUG PRINT [logger.py - setup_logging]: Logging a archivo deshabilitado (LOG_FILE/LOG_DIR no OK).")
    
    logger.info(f"Logger principal '{logger.name}' completamente configurado por setup_logging.")
    print(f"DEBUG PRINT [logger.py - setup_logging]: Configuración del logger finalizada.")
    _is_logger_configured = True

# El logger se importa así: from app.utils.logger import logger, setup_logging
# Y setup_logging(settings) se llama desde app/__init__.py