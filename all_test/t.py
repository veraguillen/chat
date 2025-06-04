# t.py
import asyncio
import sys
from pathlib import Path

# Asegurarse de que el directorio raíz esté en el PYTHONPATH
sys.path.append(str(Path(__file__).parent))

try:
    from app.core.database import initialize_database
    from app.core.config import settings
    print("✅ Configuración cargada correctamente")
    print(f"Configuración: {settings.dict()}")
except Exception as e:
    print(f"❌ Error al cargar la configuración: {e}")
    raise

async def test():
    try:
        print("🔌 Iniciando prueba de conexión a la base de datos...")
        if await initialize_database():
            print("✅ Conexión exitosa")
        else:
            print("❌ Error en la conexión")
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test())