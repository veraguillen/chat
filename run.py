# run.py test
import uvicorn
import os # Importar os para acceder a variables de entorno si es necesario en config

# Intentar importar la aplicación y la configuración.
try:
    from app import app  # Asumiendo que 'app' es tu instancia de FastAPI/Starlette
    from app.core.config import get_settings # Importar la función para obtener la configuración

    current_settings = get_settings() # Obtener la instancia de settings
    CONFIG_LOADED_SUCCESSFULLY = True
    print(f"run.py: Configuración cargada exitosamente desde app.core.config.")
    print(f"run.py: Log level configurado: {current_settings.log_level}")
    # Ejemplo de cómo podrías estar usando una variable de entorno para el puerto
    # y un host fijo para Azure. Esto debería estar en tu config.py realmente.
    print(f"run.py: Objetivo de servidor: Host={current_settings.server_host}, Puerto={current_settings.server_port}")
    # No mostrar tokens completos en logs, incluso los primeros 10 caracteres pueden ser sensibles.
    # Considera solo un log de confirmación si el token está presente o no, si es necesario.
    print(f"run.py DEBUG: WHATSAPP_ACCESS_TOKEN {'está presente' if current_settings.whatsapp_access_token else 'NO está presente'}.")

except ImportError as e_imp:
    print(f"Error CRÍTICO importando 'app' (FastAPI/Starlette instance) o 'get_settings' desde 'app.core.config' en run.py: {e_imp}")
    CONFIG_LOADED_SUCCESSFULLY = False
except Exception as e_cfg:
    print(f"Error CRÍTICO durante la carga inicial de la configuración (get_settings) en run.py: {e_cfg}")
    CONFIG_LOADED_SUCCESSFULLY = False

if __name__ == "__main__":
    if CONFIG_LOADED_SUCCESSFULLY:
        server_host = "0.0.0.0"  # Allows external connections
        server_port = 8000
        
        try:
            uvicorn.run(
                "app:app",
                host=server_host,
                port=server_port,
                log_level="info",
                reload=False  # Set to False for production
            )
        except Exception as e_uvicorn:
            print(f"Error CRÍTICO al intentar iniciar Uvicorn: {e_uvicorn}")
            print("Verifica que 'uvicorn' y todas las dependencias estén en requirements.txt y se hayan instalado.")
            print("Verifica que 'app:app' (o tu objetivo) sea correcto y que el objeto 'app' sea importable.")

    else: 
        print("No se puede iniciar el servidor Uvicorn debido a errores previos en la carga de configuración o importación de la aplicación.")
        print("Revisa los mensajes de error anteriores para más detalles.")
        print("Asegúrate de que tu archivo 'requirements.txt' está completo y en la raíz del proyecto.")