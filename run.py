# run.py
import os
import uvicorn
from app.core.config import settings, get_settings  # Importar settings y get_settings

# Importa la instancia 'app' DIRECTAMENTE desde app/__init__.py
try:
    from app import app  # app es la instancia FastAPI de app/__init__.py
    APP_LOADED_OK = True
except ImportError as e_app_import:
    print(f"ERROR CRÍTICO en run.py: No se pudo importar 'app' desde el paquete 'app'. Error: {e_app_import}", file=os.sys.stderr)
    APP_LOADED_OK = False
    app = None  # Para evitar NameError más adelante
except Exception as e_generic_app_import:
    print(f"ERROR CRÍTICO GENÉRICO en run.py al importar 'app': {e_generic_app_import}", file=os.sys.stderr)
    APP_LOADED_OK = False
    app = None

# La lógica de Socket.IO, si es necesaria, debería integrarse en app/__init__.py
# o montarse en la instancia 'app' importada.
# Si se mantiene aquí, asegúrate de que 'sio' y 'socket_app' se monten
# en la instancia 'app' correcta (la importada de app/__init__.py).

# Ejemplo si necesitas Socket.IO y lo configuras aquí (no ideal si app está en __init__):
# if APP_LOADED_OK and app:
#     from socketio import AsyncServer, ASGIApp
#     sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*')
#     socket_app_run = ASGIApp(sio, socketio_path="/ws/socket.io") # Path completo
#     app.mount("/ws", socket_app_run) # Ojo, esto montaría en app la instancia de __init__
#
#     @sio.event
#     async def connect(sid, environ):
#         print(f"RUN.PY Socket.IO: Cliente conectado: {sid}")
#     # ... otros eventos de socket.io ...
# else:
#     print("RUN.PY: No se pudo cargar 'app', Socket.IO no se montará desde run.py")


if __name__ == "__main__":
    if APP_LOADED_OK and app:
        # Obtener configuración de settings
        uvicorn_host = getattr(settings, "SERVER_HOST", "0.0.0.0")
        uvicorn_port = int(getattr(settings, "SERVER_PORT", 8000))
        
        # Obtener log_level de settings
        log_level_run = getattr(settings, "LOG_LEVEL", "info").lower()
        
        print(f"Iniciando Uvicorn desde run.py apuntando a 'app' en {uvicorn_host}:{uvicorn_port}")
        print(f"  Nivel de log para Uvicorn: {log_level_run}")
        print(f"  Para control total y reloads, usa: uvicorn app:app --reload --log-level debug")
        
        uvicorn.run(
            app,  # Usa la 'app' importada de app/__init__.py
            host=uvicorn_host,
            port=uvicorn_port,
            reload=False,  # El reload es mejor manejarlo con el comando uvicorn directo
            log_level=log_level_run
        )
    else:
        print("No se pudo iniciar la aplicación debido a errores de importación.", file=os.sys.stderr)
        os.sys.exit(1)