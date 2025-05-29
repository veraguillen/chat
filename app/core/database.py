# app/core/database.py
import ssl
import traceback
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text # Para ejecutar SQL simple como text("SELECT 1")

from app.core.config import settings # Asume que settings es la instancia ya cargada de tu config

# Importar logger de forma segura y configurarlo
try:
    from app.utils.logger import logger # Asume que tienes un logger personalizado
except ImportError:
    import logging
    logger = logging.getLogger("app.core.database")
    if not logger.handlers: # Evitar añadir múltiples handlers
        handler = logging.StreamHandler()
        # Ajusta el formato del log si es necesario
        log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        formatter = logging.Formatter(log_format)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    # Obtener log_level de settings si está disponible, sino default a INFO
    log_level_str = getattr(settings, 'log_level', "INFO").upper()
    logger.setLevel(getattr(logging, log_level_str, logging.INFO))


# --- Variables Globales ---
# Usamos None como tipo para create_async_engine para evitar problemas de importación circular
# si el tipo exacto se usa antes de que SQLAlchemy esté completamente disponible.
# SQLAlchemy Engine es el punto de entrada a la base de datos.
engine: Optional["create_async_engine"] = None # Tipado más genérico para evitar problemas de importación temprana

# AsyncSessionLocal es una fábrica para crear nuevas instancias de AsyncSession.
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None

# Base para los modelos declarativos de SQLAlchemy. Todas tus clases modelo deben heredar de esto.
Base = declarative_base()
# -------------------------

async def initialize_database():
    """
    Inicializa el engine de base de datos y la fábrica de sesiones.
    Esta función debe ser llamada durante el evento 'startup' del lifespan de FastAPI.
    Utiliza asyncpg con configuración SSL explícita.
    """
    global engine, AsyncSessionLocal
    logger.info("Iniciando inicialización de base de datos (asyncpg con SSL explícito)...")

    # Obtener los componentes individuales de la conexión desde settings
    db_user = getattr(settings, 'pguser', None)
    db_password = getattr(settings, 'pgpassword', None)
    db_host = getattr(settings, 'pghost', None)
    db_name = getattr(settings, 'pgdatabase', None)

    if not all([db_user, db_password, db_host, db_name]):
        logger.critical("CRÍTICO: Faltan una o más variables de conexión a la BD (PGUSER, PGPASSWORD, PGHOST, PGDATABASE) en settings. No se puede inicializar la DB.")
        return False # Indica fallo

    # Construir la DSN (Data Source Name) para asyncpg SIN parámetros SSL en la query string
    # asyncpg los tomará de connect_args.
    db_url_for_asyncpg = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    
    # No loguear la URL completa con credenciales por seguridad
    logger.info(f"URL base para asyncpg engine (host/db): {db_host}/{db_name}")

    try:
        # Configurar explícitamente SSL para asyncpg
        # Para Azure, generalmente quieres SSL pero sin verificar el certificado del servidor
        # si no tienes el CA root de Azure configurado localmente.
        # Esto es funcionalmente similar a sslmode=require de psycopg2.
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH) # SERVER_AUTH es apropiado para un cliente conectándose a un servidor
        ssl_context.check_hostname = False # No verificar el hostname contra el certificado del servidor
        ssl_context.verify_mode = ssl.CERT_NONE    # No verificar el certificado del servidor contra un CA

        engine = create_async_engine(
            db_url_for_asyncpg,
            connect_args={
                "ssl": ssl_context  # Pasa el objeto SSLContext configurado
            },
            echo=(getattr(settings, 'log_level', "INFO").upper() == "DEBUG"), # Activar echo SQL solo en DEBUG
            pool_pre_ping=True,  # Verifica la vitalidad de las conexiones antes de usarlas
            pool_recycle=3600,   # Reciclar conexiones cada hora para evitar timeouts de inactividad
            # Future=True es el default en SQLAlchemy 2.0 y no necesita ser especificado
        )
        
        # Realizar una conexión de prueba para verificar que el engine está operativo
        async with engine.connect() as connection:
            # Podrías ejecutar una consulta simple aquí si es necesario, pero conectar es una buena prueba
            # result = await connection.execute(text("SELECT 1")) 
            # if result.scalar_one_or_none() != 1:
            #    raise Exception("La consulta de prueba 'SELECT 1' falló.")
            logger.info("Conexión inicial al pool de la base de datos (asyncpg) establecida exitosamente.")

        logger.info("Motor SQLAlchemy asíncrono (engine) para asyncpg creado exitosamente.")

        AsyncSessionLocal = async_sessionmaker(
            bind=engine, 
            class_=AsyncSession, 
            expire_on_commit=False # Buena práctica para aplicaciones web asíncronas
        )
        logger.info("Fábrica de sesiones (AsyncSessionLocal) creada con éxito.")
        return True # Indica éxito

    except Exception as e:
        logger.critical(f"FALLO CRÍTICO inicializando base de datos (asyncpg): {type(e).__name__} - {e}", exc_info=True)
        engine = None
        AsyncSessionLocal = None
        return False # Indica fallo

async def close_database_connection():
    """Cierra las conexiones del engine de base de datos. Llamar desde el evento 'shutdown' del lifespan."""
    global engine, AsyncSessionLocal
    if engine:
        logger.info("Cerrando conexiones del engine de base de datos...")
        await engine.dispose() # Cierra todas las conexiones en el pool del engine
        logger.info("Conexiones del engine de base de datos cerradas.")
    engine = None # Limpiar la referencia global
    AsyncSessionLocal = None # Limpiar la referencia global

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependencia de FastAPI para obtener una sesión de base de datos.
    Maneja el ciclo de vida de la sesión: creación, commit/rollback, y cierre.
    """
    if AsyncSessionLocal is None:
        logger.error("Fábrica de sesiones (AsyncSessionLocal) no inicializada. La inicialización de la DB pudo haber fallado.")
        raise RuntimeError("La base de datos no está disponible. AsyncSessionLocal no fue inicializada.")

    session: AsyncSession = AsyncSessionLocal()
    logger.debug(f"Sesión de base de datos {id(session)} creada y entregada.")
    try:
        yield session # Entrega la sesión al endpoint/código que la solicitó
        await session.commit() # Intenta hacer commit si no hubo excepciones durante el uso de la sesión
        logger.debug(f"Commit para sesión de base de datos {id(session)} realizado.")
    except Exception as e:
        logger.error(f"Error durante la sesión de base de datos {id(session)}, realizando rollback: {type(e).__name__} - {e}")
        logger.error(traceback.format_exc()) # Loguear el traceback completo para depuración
        await session.rollback()
        raise # Re-lanza la excepción para que FastAPI la maneje y devuelva una respuesta HTTP de error apropiada
    finally:
        logger.debug(f"Cerrando sesión de base de datos {id(session)}.")
        await session.close()

# --- Función Opcional para Crear Tablas (Llamar Manualmente o desde Lifespan con mucho cuidado) ---
async def create_db_tables():
    """
    Crea todas las tablas definidas en Base.metadata si no existen.
    ¡USAR CON CUIDADO EN PRODUCCIÓN! Es mejor usar herramientas de migración como Alembic.
    """
    if engine is None:
         logger.error("No se pueden crear tablas, el engine de base de datos no está inicializado.")
         return
    
    logger.info("Intentando verificar/crear tablas de base de datos (Base.metadata.create_all)...")
    async with engine.begin() as conn: # engine.begin() inicia una transacción para DDL
         try:
             # Asegúrate de que todos tus modelos SQLAlchemy que heredan de Base
             # hayan sido importados en algún punto ANTES de que esta función se llame,
             # para que Base.metadata los conozca.
             logger.info("Importando modelos para la creación de tablas (asegúrate de que estén todos)...")
             # Ejemplos (debes importar los tuyos):
             # from app.models.user_state import UserState 
             # from app.models.scheduling_models import Company, Interaction, Appointment
             # ... importa todos tus otros modelos SQLAlchemy ...

             # Este log es útil para depurar qué tablas conoce Base.metadata
             if Base.metadata.tables:
                logger.info(f"Tablas conocidas por Base.metadata antes de create_all: {list(Base.metadata.tables.keys())}")
             else:
                logger.warning("Base.metadata no parece conocer ninguna tabla. ¿Se importaron los modelos?")

             await conn.run_sync(Base.metadata.create_all)
             logger.info("Operación Base.metadata.create_all completada. Tablas verificadas/creadas.")
         except Exception as e:
              logger.error(f"Error durante la operación Base.metadata.create_all: {e}", exc_info=True)