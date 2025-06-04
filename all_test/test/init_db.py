# init_db.py
import asyncio
import sys
from pathlib import Path

# Asegurar que el directorio de la aplicación esté en el PYTHONPATH
sys.path.append(str(Path(__file__).parent))

from app.core.database import initialize_database, create_db_tables

async def init_models():
    # Inicializar la conexión a la base de datos
    if not await initialize_database():
        print("❌ No se pudo inicializar la base de datos")
        return False
    
    # Crear tablas si no existen
    try:
        await create_db_tables()
        print("✅ Base de datos inicializada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error al crear tablas: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(init_models())