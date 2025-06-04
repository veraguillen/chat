# app/__init__.py
import sys
import logging 
import asyncio # <--- IMPORTACIÓN AÑADIDA
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from datetime import datetime, timezone

# --- 1. Carga de Configuración (settings) ---
try:
    from app.core.config import settings
    if settings is None: 
        raise RuntimeError("La instancia 'settings' es None después de importar desde app.core.config.")
    CONFIG_LOADED_SUCCESSFULLY = True
    # Usar print aquí es más seguro antes de que el logger principal esté configurado
    print(f"DEBUG PRINT [app/__init__.py]: 'settings' importado. PROJECT_NAME: {getattr(settings, 'PROJECT_NAME', 'ERROR AL LEER SETTINGS')}")
except Exception as e_cfg_init:
    emergency_logger_init = logging.getLogger("APP_INIT_SETTINGS_FAILURE")
    if not emergency_logger_init.hasHandlers():
        _h_emerg = logging.StreamHandler(sys.stderr)
        _f_emerg = logging.Formatter('%(asctime)s - %(name)s - CRITICAL - [%(filename)s:%(lineno)d] - %(message)s')
        _h_emerg.setFormatter(_f_emerg); emergency_logger_init.addHandler(_h_emerg); emergency_logger_init.setLevel(logging.CRITICAL)
    emergency_logger_init.critical(f"FALLO CRÍTICO AL CARGAR 'settings' EN app/__init__.py: {e_cfg_init}", exc_info=True)
    print(f"ERROR CRÍTICO [app/__init__.py]: Falló la importación/creación de 'settings': {e_cfg_init}", file=sys.stderr)
    settings = None 
    CONFIG_LOADED_SUCCESSFULLY = False
    sys.exit("Error crítico: Fallo al cargar la configuración. La aplicación no puede continuar.")

# --- 2. Configuración del Logger Principal de la Aplicación ---
logger: logging.Logger 
if CONFIG_LOADED_SUCCESSFULLY and settings:
    try:
        from app.utils.logger import setup_logging, logger as main_app_logger
        setup_logging(settings) 
        logger = main_app_logger 
        logger.info(f"Logger principal '{logger.name}' configurado desde app/__init__.py. Nivel efectivo: {logging.getLevelName(logger.getEffectiveLevel())}.")
    except Exception as e_logger_setup:
        logger_fallback_init = logging.getLogger("APP_INIT_LOGGER_SETUP_FALLBACK")
        if not logger_fallback_init.hasHandlers():
            _h_log_fall = logging.StreamHandler(sys.stdout)
            _f_log_fall = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
            _h_log_fall.setFormatter(_f_log_fall); logger_fallback_init.addHandler(_h_log_fall); logger_fallback_init.setLevel(logging.INFO)
        logger = logger_fallback_init
        logger.error(f"Error configurando el logger principal desde app.utils.logger: {e_logger_setup}. Usando logger de fallback.", exc_info=True)
else:
    logger = logging.getLogger("APP_INIT_NO_SETTINGS_FOR_LOGGER")
    if not logger.hasHandlers():
        _h_no_set = logging.StreamHandler(sys.stdout)
        _f_no_set = logging.Formatter('%(asctime)s - %(name)s - CRITICAL - [%(filename)s:%(lineno)d] - %(message)s')
        _h_no_set.setFormatter(_f_no_set); logger.addHandler(_h_no_set); logger.setLevel(logging.CRITICAL)
    logger.critical("Settings no disponibles, el logger principal no pudo ser configurado con settings.")

# --- 3. Resto de Importaciones y Definición de la App ---
# Importar módulos que podrían usar 'logger' o 'settings' DESPUÉS de que estén listos.
# from .core import database as db_module # Importar el módulo completo para el chequeo de AsyncSessionLocal
from .core.database import initialize_database, close_database_engine, AsyncSessionLocal # Importar AsyncSessionLocal para el chequeo
from .ai.rag_retriever import load_rag_components, LANGCHAIN_OK
from .main.routes import router as main_routes_router
# from .api import router as general_api_router # Comentado para simplificar arranque

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info(f"{'='*10} LIFESPAN: Iniciando Aplicación FastAPI {'='*10}")
    app_instance.state.db_ready = False
    app_instance.state.retriever = None
    app_instance.state.is_rag_ready = False

    if settings:
        logger.info("LIFESPAN: Intentando inicializar la base de datos...")
        try:
            db_ok = await initialize_database()
            # Verificar AsyncSessionLocal DESPUÉS de llamar a initialize_database
            # Importar database de nuevo aquí para asegurar que vemos la variable global actualizada
            from .core import database as db_module_lifespan 
            if db_ok and db_module_lifespan.AsyncSessionLocal is not None:
                app_instance.state.is_db_ready = True
                logger.info("LIFESPAN: Base de datos inicializada y db_module_lifespan.AsyncSessionLocal está configurado.")
            elif db_ok and db_module_lifespan.AsyncSessionLocal is None:
                app_instance.state.is_db_ready = False
                logger.critical("LIFESPAN CRITICAL POST-DB-INIT: db_module_lifespan.AsyncSessionLocal SIGUE SIENDO None!")
            else:
                app_instance.state.is_db_ready = False
                logger.error("LIFESPAN: FALLO en inicialización de BD (initialize_database devolvió False).")
        except Exception as e_db:
            app_instance.state.is_db_ready = False
            logger.critical(f"LIFESPAN: EXCEPCIÓN CRÍTICA durante initialize_database: {e_db}", exc_info=True)

        if LANGCHAIN_OK:
            logger.info("LIFESPAN: Intentando cargar componentes RAG (Langchain OK)...")
            try:
                loaded_retriever: Any = await asyncio.to_thread(load_rag_components) # asyncio ya está importado
                if loaded_retriever:
                    app_instance.state.retriever = loaded_retriever
                    app_instance.state.is_rag_ready = True
                    logger.info("LIFESPAN: Componentes RAG cargados exitosamente.")
                else:
                    app_instance.state.is_rag_ready = False
                    logger.warning("LIFESPAN: load_rag_components devolvió None. RAG no funcional.")
            except Exception as e_rag:
                app_instance.state.is_rag_ready = False
                logger.error(f"LIFESPAN: EXCEPCIÓN al cargar componentes RAG: {e_rag}", exc_info=True)
        else:
            logger.warning("LIFESPAN: Langchain no disponible. Componentes RAG no se cargarán.")
            app_instance.state.is_rag_ready = False
    else:
        logger.critical("LIFESPAN: 'settings' no está disponible. Saltando inicialización de DB y RAG.")

    ready_msg = f"DB Lista: {app_instance.state.is_db_ready}, RAG Listo: {app_instance.state.is_rag_ready}"
    logger.info(f"{'='*10} LIFESPAN: Aplicación Lista para servir ({ready_msg}) {'='*10}")
    yield 
    logger.info(f"{'='*10} LIFESPAN: Apagando Aplicación FastAPI {'='*10}")
    if app_instance.state.is_db_ready and callable(close_database_engine):
        try: await close_database_engine()
        except Exception as e: logger.error(f"LIFESPAN: Excepción en close_database_engine: {e}", exc_info=True)
    app_instance.state.retriever = None 
    logger.info("LIFESPAN: Recursos limpiados. Apagado completado.")

# --- Creación de la Instancia FastAPI ---
if not (CONFIG_LOADED_SUCCESSFULLY and settings):
    logger.critical("FALLO CATASTRÓFICO: No se puede crear instancia FastAPI, 'settings' no disponible.")
    app = None # type: ignore 
else:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.PROJECT_VERSION,
        lifespan=lifespan
    )
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    
    try:
        app.include_router(main_routes_router)
        logger.info("Router principal (main_routes_router) incluido.")
        # Si tienes un router para /api y lo necesitas, descomenta y asegúrate que app.api.__init__.py defina 'router'
        # from .api import router as general_api_router
        # app.include_router(general_api_router, prefix="/api") 
        # logger.info("Router general_api_router incluido con prefijo /api.")
    except Exception as e_router_final:
        logger.critical(f"Error al incluir routers en la instancia FastAPI: {e_router_final}", exc_info=True)

    @app.get("/", tags=["Status"], include_in_schema=False)
    async def root_status_endpoint(request: Request):
        db_s = getattr(request.app.state, 'is_db_ready', "desconocido")
        rag_s = getattr(request.app.state, 'is_rag_ready', "desconocido")
        logger.debug("Acceso a endpoint raíz '/' para estado.")
        return {
            "project": settings.PROJECT_NAME, "version": settings.PROJECT_VERSION,
            "status_message": "Servicio Activo",
            "database_status": "lista" if db_s is True else "no_lista" if db_s is False else db_s,
            "rag_status": "listo" if rag_s is True else "no_listo" if rag_s is False else rag_s,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()
        }
    logger.info(f"Instancia FastAPI '{settings.PROJECT_NAME}' v{settings.PROJECT_VERSION} creada y configurada. LOG_LEVEL app: {settings.LOG_LEVEL}.")

if app is None and __name__ == "__main__":
    print("ERROR CRÍTICO: La instancia 'app' de FastAPI es None. No se puede iniciar.", file=sys.stderr)