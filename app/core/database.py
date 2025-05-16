# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings
# Importar logger de forma segura
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("database")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.WARNING)
import traceback
from typing import AsyncGenerator, Optional

# --- Variables Globales ---
engine: Optional[create_async_engine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None
Base = declarative_base()
# -------------------------

async def initialize_database():
    """Inicializa el engine y la fábrica de sesiones. Llamar desde lifespan."""
    global engine, AsyncSessionLocal
    logger.info("Iniciando inicialización de base de datos...")

    db_url = getattr(settings, 'database_url', None)
    if not db_url:
        logger.critical("DATABASE_URL no configurada en settings. No se puede inicializar la DB.")
        return False

    logger.info(f"Intentando crear engine para DB...")
    try:
        engine = create_async_engine(
            db_url, echo=False, pool_pre_ping=True, pool_recycle=3600
        )
        # Verificar conexión
        async with engine.connect() as connection:
             logger.info("Conexión inicial a la base de datos exitosa.")
        logger.info("Motor SQLAlchemy asíncrono creado.")

        AsyncSessionLocal = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("Fábrica de sesiones (AsyncSessionLocal) creada con éxito.")
        return True

    except Exception as e:
        logger.critical(f"FALLO CRÍTICO inicializando base de datos: {e}", exc_info=True)
        engine = None
        AsyncSessionLocal = None
        return False

async def close_database_connection():
    """Cierra la conexión del engine."""
    global engine, AsyncSessionLocal
    if engine:
        logger.info("Cerrando conexiones del engine de base de datos...")
        await engine.dispose()
        logger.info("Conexiones cerradas.")
    engine = None
    AsyncSessionLocal = None

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI para obtener una sesión de DB."""
    if AsyncSessionLocal is None:
        logger.error("Fábrica de sesiones (AsyncSessionLocal) no inicializada.")
        raise RuntimeError("La inicialización de la base de datos falló o no se ejecutó.")

    session: AsyncSession = AsyncSessionLocal()
    logger.debug(f"Sesión DB {id(session)} creada.")
    try:
        yield session
        logger.debug(f"Commit para sesión DB {id(session)}...")
        await session.commit()
        logger.debug(f"Commit exitoso sesión DB {id(session)}.")
    except Exception as e:
        logger.error(f"Rollback sesión DB {id(session)} debido a: {e}")
        await session.rollback()
        logger.error(traceback.format_exc()) # Loguear traceback completo del error
        raise # Re-lanzar para que FastAPI maneje el error HTTP
    finally:
        logger.debug(f"Cerrando sesión DB {id(session)}.")
        await session.close()

# --- Función Opcional para Crear Tablas (Llamar Manualmente o desde Lifespan con cuidado) ---
async def create_db_tables():
    """Crea tablas definidas en Base.metadata si no existen."""
    if engine is None:
         logger.error("No se pueden crear tablas, el engine no está inicializado.")
         return
    logger.info("Verificando/Creando tablas de base de datos...")
    async with engine.begin() as conn:
         try:
             # Importar modelos aquí para asegurar que Base los conozca
             from app.models.user_state import UserState
             from app.models.scheduling_models import Company, Interaction, Appointment
             logger.info(f"Metadata Tables: {Base.metadata.tables.keys()}")
             await conn.run_sync(Base.metadata.create_all)
             logger.info("Tablas verificadas/creadas.")
         except Exception as e:
              logger.error(f"Error durante create_all: {e}", exc_info=True)