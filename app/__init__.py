# app/__init__.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Any 
import os # Mover import os aquí si se usa en el endpoint raíz
import sys # Para sys.exit
from datetime import datetime, timezone

# 1. Importar configuración y logger PRIMERO
try:
    from app.core.config import settings
    from app.utils.logger import logger # Asumiendo que este es tu logger configurado
    CONFIG_OK = True if settings else False
    if not CONFIG_OK:
        # Loguear usando print porque el logger podría no estar listo
        print("ERROR CRÍTICO [__init__.py]: El objeto 'settings' no se inicializó correctamente en config.py.")
        sys.exit(1) # Salir si la configuración es crítica
except ImportError as e:
    import logging # Fallback logging si todo lo demás falla
    logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.critical(f"ERROR CRÍTICO [__init__.py]: No se pudo importar 'settings' o 'logger': {e}. La aplicación no puede continuar.")
    sys.exit(1)
except Exception as e_cfg:
    # Captura otros errores durante la carga de settings (settings ya debería loguear esto)
    # logger.error(f"ERROR CRÍTICO [__init__.py]: Excepción inesperada al cargar settings: {e_cfg}", exc_info=True)
    print(f"ERROR CRÍTICO [__init__.py]: Excepción inesperada al cargar settings: {e_cfg}") # Usar print si logger no está
    sys.exit(1)


# 2. Importar funciones de inicialización/cierre de recursos
DB_FUNCS_OK = False
try:
    from app.core.database import initialize_database, close_database_connection
    DB_FUNCS_OK = True
except ImportError:
    logger.warning("Funciones initialize_database/close_database_connection no encontradas. La funcionalidad de DB estará deshabilitada.")
    async def initialize_database(): logger.error("Dummy: initialize_database no disponible."); return False
    async def close_database_connection(): pass

RAG_LOADER_OK = False
try:
    from app.ai.rag_retriever import load_rag_components
    RAG_LOADER_OK = True
except ImportError:
    logger.warning("Función load_rag_components no encontrada. La funcionalidad RAG estará deshabilitada.")
    def load_rag_components(): logger.error("Dummy: load_rag_components no disponible."); return None

# 3. Importar el router principal
ROUTER_OK = False
try:
    from app.main.routes import router as main_router
    ROUTER_OK = True
except ImportError as e:
     logger.error(f"Error importando main_router desde app.main.routes: {e}", exc_info=True)
except Exception as e_router:
     logger.error(f"Excepción inesperada importando main_router: {e_router}", exc_info=True)


# --- Definición del Lifespan ---
@asynccontextmanager
async def lifespan(app_instance: FastAPI): # Cambiado 'app' a 'app_instance' para evitar shadowing
    """Gestiona el inicio y cierre de recursos (DB, RAG)."""
    logger.info(f"{'='*10} Iniciando Aplicación FastAPI (Lifespan) {'='*10}")
    app_instance.state.retriever = None
    app_instance.state.is_rag_ready = False
    app_instance.state.is_db_ready = False

    if DB_FUNCS_OK:
        logger.info("Lifespan: Intentando inicializar la base de datos...")
        db_initialized_ok = await initialize_database()
        if db_initialized_ok:
            logger.info("Lifespan: Conexión a base de datos inicializada.")
            app_instance.state.is_db_ready = True
        else:
            logger.critical("Lifespan: FALLO CRÍTICO en la inicialización de la base de datos.")
    else:
        logger.error("Lifespan: initialize_database no disponible.")

    if RAG_LOADER_OK:
        logger.info("Lifespan: Intentando cargar componentes RAG...")
        try:
            loaded_retriever: Any = load_rag_components() # Esta es una llamada síncrona
            if loaded_retriever:
                app_instance.state.retriever = loaded_retriever
                app_instance.state.is_rag_ready = True
                logger.info("Lifespan: Componentes RAG cargados y retriever guardado en app.state.")
            else:
                logger.warning("Lifespan: FALLO AL CARGAR COMPONENTES RAG (load_rag_components devolvió None).")
        except Exception as rag_load_err:
             logger.error(f"Lifespan: Excepción al llamar a load_rag_components: {rag_load_err}", exc_info=True)
    else:
         logger.warning("Lifespan: load_rag_components no disponible.")

    ready_msg = f"DB Lista: {app_instance.state.is_db_ready}, RAG Listo: {app_instance.state.is_rag_ready}"
    logger.info(f"{'='*10} Aplicación Lista para servir ({ready_msg}) {'='*10}")
    yield 

    logger.info(f"{'='*10} Apagando Aplicación FastAPI (Lifespan) {'='*10}")
    if DB_FUNCS_OK and callable(close_database_connection):
        await close_database_connection()
    app_instance.state.retriever = None # Limpiar estado
    logger.info("Lifespan: Recursos limpiados. Apagado completado.")
# --- FIN Lifespan ---


# --- Crear la Instancia ÚNICA de la App FastAPI ---
# settings ya fue verificado al inicio del archivo
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API para procesar mensajes de WhatsApp/Messenger con estado, RAG y Calendly.",
    version=settings.VERSION,
    lifespan=lifespan # Asociar el lifespan
)
# -----------------------------------------

# --- Configuración CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"], 
)
logger.info("Middleware CORS configurado (permitiendo todos los orígenes para desarrollo).")
# ---------------------------

# --- Incluir Routers ---
if ROUTER_OK and main_router: # Añadido check para main_router
    app.include_router(main_router)
    logger.info("Router principal (app.main.routes) incluido.")
else:
    logger.critical("Router principal no se pudo importar o no está definido. La API no tendrá endpoints /webhook funcionales.")
# ----------------------

# --- Ruta Raíz (Status Check) ---
@app.get("/", tags=["Status"], summary="Verifica el estado de la API y sus componentes")
async def root(request: Request):
    """Devuelve el estado básico de la API, DB y RAG."""
    is_rag_ready = getattr(request.app.state, 'is_rag_ready', False)
    is_db_ready = getattr(request.app.state, 'is_db_ready', False)
    rag_status = "listo" if is_rag_ready else "no_disponible_o_fallo"
    db_status = "conectada" if is_db_ready else "fallo_inicializacion_o_no_disponible"
    project_name = getattr(settings, 'PROJECT_NAME', 'Chatbot API')
    project_version = getattr(settings, 'VERSION', 'N/A')

    logger.debug("Accediendo a endpoint raíz '/'") # Log para saber que se accede
    return {
        "status": "ok",
        "message": f"Bienvenido a {project_name} v{project_version}",
        "database_status": db_status,
        "rag_status": rag_status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat() # Añadir timestamp
    }
# -----------------------------

logger.info(f"Instancia FastAPI '{settings.PROJECT_NAME}' creada y configurada en app/__init__.py.")