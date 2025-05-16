# run.py test
import uvicorn
# No es estrictamente necesario importar 'os' si obtenemos todo de 'settings'

# Intentar importar la aplicación y la configuración.
try:
    from app import app 
    from app.core.config import get_settings # Importar get_settings

    current_settings = get_settings() # Obtener la instancia de settings
    CONFIG_LOADED_SUCCESSFULLY = True
    print(f"run.py: Configuración cargada. Log level desde settings: {current_settings.log_level}")
    print(f"run.py DEBUG: WHATSAPP_ACCESS_TOKEN visto por run.py (desde settings): {current_settings.whatsapp_access_token[:10] if current_settings.whatsapp_access_token else 'NO TOKEN'}...")

except ImportError as e_imp:
    print(f"Error CRÍTICO importando 'app' o 'settings' en run.py: {e_imp}")
    CONFIG_LOADED_SUCCESSFULLY = False
except Exception as e_cfg:
    print(f"Error CRÍTICO durante la carga inicial de settings en run.py: {e_cfg}")
    CONFIG_LOADED_SUCCESSFULLY = False

if __name__ == "__main__":
    if CONFIG_LOADED_SUCCESSFULLY:
        # --- ¡CORRECCIÓN AQUÍ! ---
        # Obtener host, port y log_level de la instancia 'current_settings'
        server_host = current_settings.server_host
        server_port = current_settings.server_port
        log_level_uvicorn = current_settings.log_level.lower()
        # --- FIN DE LA CORRECCIÓN ---
        
        print(f"Iniciando servidor Uvicorn en http://{server_host}:{server_port} con log level: {log_level_uvicorn}...")
        
        uvicorn.run(
            "app:app",  # Asumiendo que tu app = FastAPI() está en app/__init__.py
            host=server_host,
            port=server_port,
            reload=True, 
            log_level=log_level_uvicorn
        )
    else: 
        print("No se puede iniciar el servidor Uvicorn debido a errores previos en la carga de configuración o importación de la aplicación.")
        print("Revisa los mensajes de error anteriores para más detalles.")