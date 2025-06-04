# app/core/database.py
import ssl # Solo si necesitas configurar SSLContext manualmente, lo cual intentaremos evitar
import traceback # Lo mantendremos para el logging de excepciones si es necesario
import json
from typing import AsyncGenerator, Optional
from urllib.parse import parse_qs, urlencode

from sqlalchemy.ext.asyncio import (
    AsyncEngine, 
    AsyncSession,
    async_sessionmaker, # Correcto para SQLAlchemy 2.0+
    create_async_engine
)
from sqlalchemy.orm import declarative_base # Si usas modelos SQLAlchemy ORM
from sqlalchemy.sql import text # Para ejecutar SQL crudo como la prueba de conexión

# Importar settings y logger (asumiendo que ya están configurados cuando se llama a las funciones de este módulo)
try:
    from app.core.config import settings # Importa la instancia global 'settings'
    from app.utils.logger import logger # Importa el logger principal de la app
    MODULE_INIT_OK = True
except ImportError as e:
    import logging
    logger = logging.getLogger("app.core.database_fallback")
    if not logger.handlers:
        _h = logging.StreamHandler()
        _f = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        _h.setFormatter(_f); logger.addHandler(_h); logger.setLevel(logging.INFO)
    logger.error(f"Error importando settings o logger en database.py: {e}. Usando fallback logger. La funcionalidad de BD puede estar limitada.")
    settings = None # type: ignore
    MODULE_INIT_OK = False

# Configuración global para SQLAlchemy
Base = declarative_base() # Base para tus modelos ORM si los tienes

# Variables globales para el engine y la fábrica de sesiones
# Se inicializarán en initialize_database()
engine: Optional[AsyncEngine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None # El tipo correcto es async_sessionmaker

async def initialize_database() -> bool:
    """
    Inicializa el motor de base de datos (engine) y la fábrica de sesiones (AsyncSessionLocal).
    Debe ser llamado una vez durante el lifespan de la aplicación ANTES de que lleguen las solicitudes.
    """
    global engine, AsyncSessionLocal # Indicar que estamos modificando las variables globales
    
    logger.info("DB_LIFESPAN_INIT: Iniciando inicialización de la base de datos...")
    
    if not MODULE_INIT_OK or not settings or not settings.DATABASE_URL:
        logger.critical("DB_LIFESPAN_INIT: Settings o DATABASE_URL no disponibles. No se puede inicializar la BD.")
        return False

    try:
        db_url_to_use = str(settings.DATABASE_URL) # Asegurarse que es string
        
        url_parts_for_log = db_url_to_use.split('@')
        log_db_url_display = f"...@{url_parts_for_log[-1]}" if len(url_parts_for_log) > 1 else db_url_to_use
        logger.info(f"DB_LIFESPAN_INIT: Usando DATABASE_URL (ofuscada): {log_db_url_display}")

        # Configuración para manejo de codificación y conexión segura
        connect_args = {
            "server_settings": {
                "client_encoding": "utf8"
            },
            "ssl": "require"
        }
        
        # Asegurar que la URL no tenga parámetros duplicados
        db_url_parts = db_url_to_use.split('?')
        base_url = db_url_parts[0]
        query_params = {}
        
        if len(db_url_parts) > 1:
            query_params = parse_qs(db_url_parts[1])
        
        # Eliminar cualquier parámetro ssl existente para evitar conflictos
        query_params.pop('ssl', None)
        
        # Reconstruir la URL sin parámetros duplicados
        if query_params:
            db_url_to_use = f"{base_url}?{urlencode(query_params, doseq=True)}"
        else:
            db_url_to_use = base_url
        
        logger.info(f"DB_LIFESPAN_INIT: Configurando conexión a la base de datos...")
        
        try:
            engine = create_async_engine(
                db_url_to_use,
                echo=getattr(settings, 'DEBUG', False),
                pool_pre_ping=True,
                pool_recycle=300,  # Reciclar conexiones cada 5 minutos
                connect_args=connect_args,
                json_serializer=lambda x: json.dumps(x, ensure_ascii=False),
                pool_size=5,  # Número máximo de conexiones en el pool
                max_overflow=10,  # Número máximo de conexiones que pueden crearse por encima de pool_size
                pool_timeout=30,  # Tiempo de espera para obtener una conexión del pool
            )
            
            # Probar la conexión con una consulta simple
            async with engine.connect() as conn:
                # Configurar la codificación para esta sesión
                await conn.execute(text("SET client_encoding = 'UTF8'"))
                await conn.execute(text("SET application_name = 'chatbot_app'"))
                result = await conn.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    logger.info("DB_LIFESPAN_INIT: Conexión de prueba exitosa")
            
            # Configurar la fábrica de sesiones
            AsyncSessionLocal = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False, 
            )
            
            if AsyncSessionLocal:
                logger.info("DB_LIFESPAN_INIT: Fábrica de sesiones (AsyncSessionLocal) creada exitosamente.")
            else:
                logger.critical("DB_LIFESPAN_INIT CRITICAL: AsyncSessionLocal es None DESPUÉS de llamar a async_sessionmaker.")
                engine = None # Limpiar engine si la sesión falla
                return False # Fallo si no se crea la fábrica de sesiones
            
            logger.info("DB_LIFESPAN_INIT: Inicialización de base de datos completada exitosamente.")
            return True
            
        except Exception as e:
            logger.critical(f"DB_LIFESPAN_INIT: Error al conectar a la base de datos: {str(e)}")
            logger.debug("DB_LIFESPAN_INIT: Traceback:", exc_info=True)
            engine = None 
            AsyncSessionLocal = None
            return False

    except Exception as e_init_db:
        logger.critical(f"DB_LIFESPAN_INIT: ❌ Error CRÍTICO al inicializar la conexión a la base de datos: {str(e_init_db)}", exc_info=True)
        engine = None 
        AsyncSessionLocal = None
        return False

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependencia de FastAPI para obtener una sesión de base de datos asíncrona.
    Asegura que la sesión se cierre después de su uso.
    """
    if AsyncSessionLocal is None:
        # Este log es importante para saber que la inicialización no ocurrió como se esperaba.
        logger.error("GET_DB_SESSION: AsyncSessionLocal es None. La inicialización de la BD falló o no se ejecutó durante el lifespan.")
        raise RuntimeError("La base de datos no está disponible (Fábrica de sesiones AsyncSessionLocal no inicializada).")
    
    # logger.debug("GET_DB_SESSION: Solicitando nueva sesión de BD desde AsyncSessionLocal...")
    async with AsyncSessionLocal() as session: # async_sessionmaker crea un gestor de contexto
        # logger.debug(f"GET_DB_SESSION: Sesión {id(session)} obtenida.")
        try:
            yield session
            # El commit explícito debe hacerse en la lógica del endpoint/servicio si es necesario.
            # No hacer commit automático aquí a menos que sea un requisito muy específico.
            # await session.commit() 
        except Exception as e_session_yield:
            logger.error(f"GET_DB_SESSION: Excepción dentro del bloque 'yield' de la sesión {id(session)}, realizando rollback: {e_session_yield}", exc_info=True)
            await session.rollback()
            raise # Relanzar para que FastAPI o el código del endpoint lo manejen
        # 'finally' no es estrictamente necesario para session.close() porque
        # 'async with AsyncSessionLocal() as session:' ya se encarga del cierre.
        # else:
        #     logger.debug(f"GET_DB_SESSION: Sesión {id(session)} completada sin excepciones (antes de cerrar).")
    # logger.debug(f"GET_DB_SESSION: Sesión {id(session)} cerrada por el context manager.")


# --- ESTA ES LA FUNCIÓN QUE SE IMPORTA EN app/__init__.py PARA EL LIFESPAN SHUTDOWN ---
async def close_database_engine():
    """
    Desecha el pool de conexiones del motor de base de datos.
    Debe ser llamado durante el apagado del lifespan de la aplicación.
    """
    global engine, AsyncSessionLocal # Para modificar las variables globales
    if engine:
        logger.info("DB_LIFESPAN_SHUTDOWN: Intentando desechar el pool de conexiones del engine (engine.dispose())...")
        await engine.dispose()
        logger.info("DB_LIFESPAN_SHUTDOWN: Pool de conexiones del engine desechado.")
    else:
        logger.info("DB_LIFESPAN_SHUTDOWN: No hay engine de base de datos para desechar (ya era None o no se inicializó).")
    
    # Limpiar las referencias globales
    engine = None
    AsyncSessionLocal = None 
    logger.debug("DB_LIFESPAN_SHUTDOWN: Referencias globales 'engine' y 'AsyncSessionLocal' puestas a None.")