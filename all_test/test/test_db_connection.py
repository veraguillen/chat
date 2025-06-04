import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_connection():
    load_dotenv()
    
    # Obtener DATABASE_URL del entorno
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL no está definida en las variables de entorno")
        return
        
    logger.info(f"Intentando conectar a: {db_url.split('@')[-1]}")
    
    try:
        # Crear motor asíncrono
        engine = create_async_engine(
            db_url,
            echo=True,  # Habilita logging de SQL
            pool_pre_ping=True  # Verifica la conexión antes de usarla
        )
        
        # Crear una sesión asíncrona
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Probar la conexión
        async with async_session() as session:
            logger.info("Conexión exitosa. Probando consulta...")
            result = await session.execute(text("SELECT version();"))
            version = result.scalar()
            logger.info(f"Versión de PostgreSQL: {version}")
            
            # Verificar si la tabla de mensajes existe
            try:
                result = await session.execute(
                    text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'mensajes'
                    )
                    """)
                )
                exists = result.scalar()
                logger.info(f"¿Existe la tabla 'mensajes'? {'Sí' if exists else 'No'}")
            except Exception as e:
                logger.error(f"Error al verificar tablas: {e}")
                
    except Exception as e:
        logger.error(f"Error de conexión: {e}")
        if "password authentication failed" in str(e).lower():
            logger.error("Error de autenticación: Verifica el usuario y contraseña")
        elif "does not exist" in str(e).lower():
            logger.error("La base de datos no existe o el nombre es incorrecto")
        elif "connection refused" in str(e).lower():
            logger.error("No se pudo conectar al servidor. Verifica el host y puerto")
        elif "ssl" in str(e).lower():
            logger.error("Error de SSL. Intenta agregar '?sslmode=require' a la URL de conexión")
    finally:
        if 'engine' in locals():
            await engine.dispose()
            logger.info("Conexión cerrada")

if __name__ == "__main__":
    asyncio.run(test_connection())
