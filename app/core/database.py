# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker # sessionmaker ya estaba
from app.core.config import settings
# Añadir logger para debug de sesión
from app.utils.logger import logger
import traceback # Para loguear tracebacks de rollback

# Crear engine (asumiendo que settings.database_url está definido y es correcto)
try:
    engine = create_async_engine(
        settings.database_url,
        # future=True, # 'future=True' es por defecto en SQLAlchemy 2.0+, redundante si usas >=2.0
        echo=False,  # Poner a True para depurar SQL si es necesario
        pool_pre_ping=True,
        pool_recycle=3600
    )
    logger.info("Motor SQLAlchemy asíncrono creado.")
except Exception as e:
    logger.error(f"Error creando el motor SQLAlchemy: {e}", exc_info=True)
    engine = None # Marcar como None si falla la creación

# Crear fábrica de sesiones (sessionmaker)
if engine:
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False # Importante para async y FastAPI
    )
    logger.info("Fábrica de sesiones SQLAlchemy asíncrona creada.")
else:
    AsyncSessionLocal = None
    logger.error("No se pudo crear la fábrica de sesiones porque el motor falló.")


# Crear Base declarativa para modelos
Base = declarative_base()
logger.info("Base declarativa de SQLAlchemy creada.")


# Dependencia de FastAPI para gestionar la sesión
async def get_db_session():
    if AsyncSessionLocal is None:
        logger.error("Intento de obtener sesión DB, pero la fábrica de sesiones no está inicializada.")
        raise RuntimeError("La configuración de la base de datos falló.")

    # logger.debug("Creando nueva sesión de base de datos...")
    async with AsyncSessionLocal() as session:
        logger.debug(f"Sesión DB {id(session)} abierta.")
        try:
            yield session # Entrega la sesión a la función de la ruta
            # --- ¡CORRECCIÓN CLAVE! ---
            logger.debug(f"Ruta/Handler completado para sesión DB {id(session)}. Ejecutando commit...")
            await session.commit() # Guarda los cambios si no hubo excepciones
            logger.debug(f"Commit exitoso para sesión DB {id(session)}.")
            # -------------------------
        except Exception as e:
            logger.error(f"Excepción durante la sesión DB {id(session)}, ejecutando rollback: {e}")
            logger.error(traceback.format_exc()) # Loguea el traceback completo
            await session.rollback() # Deshace los cambios en caso de error
            raise # Re-lanza la excepción para que FastAPI la maneje
        finally:
            logger.debug(f"Cerrando sesión DB {id(session)}.")
            await session.close() # Cierra la sesión al final