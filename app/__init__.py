# app/__init__.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Any # Para el tipo del retriever si no es específico

# 1. Importar configuración y logger PRIMERO
# Asume que estos módulos no tienen dependencias complejas y se pueden importar de forma segura
try:
    from app.core.config import settings
    from app.utils.logger import logger
    CONFIG_OK = True if settings else False
    if not CONFIG_OK:
        print("ERROR CRÍTICO [__init__.py]: El objeto 'settings' no se inicializó correctamente en config.py.")
        import sys
        sys.exit(1)
except ImportError as e:
    import logging
    # Configuración mínima de logging si falla la importación principal
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("init_fallback")
    logger.error(f"ERROR CRÍTICO [__init__.py]: No se pudo importar config o logger: {e}. La aplicación no puede continuar.")
    import sys
    sys.exit(1)
except Exception as e_cfg:
    # Captura otros errores durante la carga de settings
    logger.error(f"ERROR CRÍTICO [__init__.py]: Excepción inesperada al cargar settings: {e_cfg}", exc_info=True)
    import sys
    sys.exit(1)


# 2. Importar funciones de inicialización/cierre de recursos
# Estas funciones se llamarán dentro del lifespan
try:
    from app.core.database import initialize_database, close_database_connection
    DB_FUNCS_OK = True
except ImportError:
    logger.warning("Funciones initialize_database/close_database_connection no encontradas en app.core.database.")
    async def initialize_database(): logger.error("Impl dummy initialize_database"); return False
    async def close_database_connection(): pass
    DB_FUNCS_OK = False

try:
    # Importar función para cargar RAG (debe ser SÍNCRONA para llamar desde lifespan así)
    from app.ai.rag_retriever import load_rag_components
    RAG_LOADER_OK = True
except ImportError:
    logger.warning("Función load_rag_components no encontrada en app.ai.rag_retriever.")
    def load_rag_components(): logger.error("Impl dummy load_rag_components"); return None
    RAG_LOADER_OK = False

# 3. Importar el router principal (DESPUÉS de otras importaciones)
try:
    from app.main.routes import router as main_router
    ROUTER_OK = True
except ImportError as e:
     logger.error(f"Error importando main_router desde app.main.routes: {e}", exc_info=True)
     ROUTER_OK = False
except Exception as e_router: # Capturar otros errores al importar rutas
     logger.error(f"Excepción inesperada importando main_router: {e_router}", exc_info=True)
     ROUTER_OK = False


# --- Definición del Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el inicio y cierre de recursos (DB, RAG)."""
    logger.info(f"{'='*10} Iniciando Aplicación FastAPI {'='*10}")
    # Inicializar el estado de la app donde guardaremos recursos
    app.state.retriever = None
    app.state.is_rag_ready = False
    app.state.is_db_ready = False # Flag para estado DB

    # 1. Inicializar Base de Datos
    if DB_FUNCS_OK:
        logger.info("Intentando inicializar la conexión a la base de datos...")
        db_initialized_ok = await initialize_database()
        if not db_initialized_ok:
            logger.critical("FALLO CRÍTICO: Inicialización de la base de datos falló.")
            # Considera no marcar la app como lista o salir si DB es esencial
        else:
            logger.info("Conexión a base de datos inicializada.")
            app.state.is_db_ready = True
            # Opcional: Crear tablas (Descomentar CON CUIDADO)
            # try:
            #     from app.core.database import create_db_tables, Base
            #     # IMPORTANTE: Importar TODOS los modelos aquí para que Base los conozca
            #     from app.models import user_state, scheduling_models
            #     logger.info("Intentando crear/verificar tablas...")
            #     await create_db_tables()
            # except Exception as table_err:
            #      logger.error(f"Error al crear/verificar tablas durante lifespan: {table_err}", exc_info=True)
    else:
        logger.error("La función initialize_database no está disponible o falló al importar.")

    # 2. Cargar Componentes RAG
    if RAG_LOADER_OK:
        logger.info("Intentando cargar componentes RAG...")
        try:
            # Ejecutar la función síncrona de carga
            loaded_retriever: Any = load_rag_components()
            if loaded_retriever:
                app.state.retriever = loaded_retriever # Guardar en el estado
                app.state.is_rag_ready = True
                logger.info(f"Componentes RAG cargados y retriever guardado en app.state.")
            else:
                logger.warning("FALLO AL CARGAR COMPONENTES RAG (load_rag_components devolvió None).")
        except Exception as rag_load_err:
             logger.error(f"Excepción al llamar a load_rag_components: {rag_load_err}", exc_info=True)
             logger.warning("FALLO CRÍTICO AL CARGAR COMPONENTES RAG debido a excepción.")
    else:
         logger.warning("La función load_rag_components no está disponible o falló al importar.")

    # Mensaje final de inicio con estado de componentes
    ready_msg = f"DB Lista: {app.state.is_db_ready}, RAG Listo: {app.state.is_rag_ready}"
    logger.info(f"{'='*10} Aplicación Lista ({ready_msg}) {'='*10}")
    yield # <-- La aplicación se ejecuta aquí

    # --- Código al cerrar la app ---
    logger.info(f"{'='*10} Apagando Aplicación FastAPI {'='*10}")
    # Cerrar conexión de base de datos (si existe la función)
    if DB_FUNCS_OK and 'close_database_connection' in globals() and callable(close_database_connection):
        await close_database_connection()
    # Limpiar estado de la app
    app.state.retriever = None
    app.state.is_rag_ready = False
    app.state.is_db_ready = False
    logger.info("Recursos limpiados. Apagado completado.")
    logger.info("="*30)
# --- FIN Lifespan ---

# --- Crear la Instancia de la App FastAPI ---
# Salir si la configuración falló críticamente
if settings is None:
     print("ERROR FATAL: Settings no se pudieron cargar. La aplicación no puede iniciar.")
     import sys
     sys.exit(1)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API para procesar mensajes de WhatsApp/Messenger con estado, RAG y Calendly.",
    version=settings.VERSION, # Leer versión de settings
    lifespan=lifespan # Asociar el lifespan
)
# -----------------------------------------

# --- Configuración CORS ---
# Ajustar origins según sea necesario para producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Ejemplo permisivo
    allow_credentials=True,
    allow_methods=["GET", "POST"], # Métodos usados por el webhook
    allow_headers=["*"], # Permitir todos los headers por ahora
)
# ---------------------------

# --- Incluir Routers ---
# Incluir solo si la importación fue exitosa
if ROUTER_OK:
    app.include_router(main_router) # Incluir tu router principal (ej. el de webhook)
    logger.info("Router principal incluido.")
else:
    logger.critical("Router principal no se pudo importar. La API no tendrá endpoints /webhook funcionales.")
# ----------------------

# --- Ruta Raíz (Status Check) ---
@app.get("/", tags=["Status"], summary="Verifica el estado de la API y sus componentes")
async def root(request: Request):
    """Devuelve el estado básico de la API, DB y RAG."""
    # Acceder al estado de forma segura usando getattr con default
    is_rag_ready = getattr(request.app.state, 'is_rag_ready', False)
    is_db_ready = getattr(request.app.state, 'is_db_ready', False)

    rag_status = "listo" if is_rag_ready else "no_disponible_o_fallo"
    db_status = "conectada" if is_db_ready else "fallo_inicializacion_o_no_disponible"

    # Construir el mensaje de bienvenida con nombre y versión del proyecto
    project_name = getattr(settings, 'PROJECT_NAME', 'Chatbot API')
    project_version = getattr(settings, 'VERSION', 'N/A')

    return {
        "status": "ok",
        "message": f"Bienvenido a {project_name} v{project_version}",
        "database_status": db_status,
        "rag_status": rag_status
        }
# -----------------------------