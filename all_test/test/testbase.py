# test_asyncpg_connection.py
import asyncio
import asyncpg
import os
import ssl # Importar ssl
from dotenv import load_dotenv

load_dotenv()

# Usar valores directos que sabemos que funcionan
PGHOST = "chatbot-iram.postgres.database.azure.com"
PGDATABASE = "chatbot_db"
PGUSER = "useradmin"
PGPASSWORD = "Chat8121943."
PGPORT = "5432"

# DSN SIN el parámetro ?ssl=require, ya que lo pasaremos explícitamente
DSN_NO_SSL_PARAM = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
# DSN CON el parámetro ssl=require para probar como alternativa
DSN_WITH_SSL_PARAM = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}?ssl=require"

async def main():
    conn = None
    print("\n🔄 Attempting asyncpg database connection (passing ssl explicitly)...")
    print(f"Host: {PGHOST}")
    print(f"Database: {PGDATABASE}")
    print(f"User: {PGUSER}")
    print(f"Port: {PGPORT}")
    print(f"DSN base (sin password ni SSL param): postgresql://{PGUSER}:***@{PGHOST}:{PGPORT}/{PGDATABASE}")

    # Intentar múltiples métodos de conexión
    methods_to_try = []
    
    # Método 1: SSL menos estricto con SSLContext
    ssl_context_less_strict = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context_less_strict.check_hostname = False
    ssl_context_less_strict.verify_mode = ssl.CERT_NONE
    methods_to_try.append({
        "name": "SSL menos estricto con SSLContext",
        "params": {
            "dsn": DSN_NO_SSL_PARAM,
            "ssl": ssl_context_less_strict,
            "timeout": 10.0
        }
    })
    
    # Método 2: Usando ssl='require' como string
    methods_to_try.append({
        "name": "Usando ssl='require' como string",
        "params": {
            "dsn": DSN_NO_SSL_PARAM,
            "ssl": 'require',
            "timeout": 10.0
        }
    })
    
    # Método 3: Usando DSN con ssl=require ya incluido
    methods_to_try.append({
        "name": "Usando DSN con ssl=require ya incluido",
        "params": {
            "dsn": DSN_WITH_SSL_PARAM,
            "timeout": 10.0
        }
    })
    
    # Método 4: Usando parámetros individuales
    methods_to_try.append({
        "name": "Usando parámetros individuales",
        "params": {
            "user": PGUSER,
            "password": PGPASSWORD,
            "database": PGDATABASE,
            "host": PGHOST,
            "port": int(PGPORT),
            "ssl": 'require',
            "timeout": 10.0
        }
    })

    # Probar cada método
    for method in methods_to_try:
        print(f"\n🔄 Intentando método: {method['name']}")
        try:
            conn = await asyncpg.connect(**method["params"])
            version = await conn.fetchval("SELECT version();")
            print(f"✅ Conexión exitosa con {method['name']}! PostgreSQL version: {version}")
            await conn.close()
            return  # Si la conexión es exitosa, terminar
        except Exception as e:
            print(f"❌ Conexión fallida con {method['name']}: {type(e).__name__} - {e}")
            if conn:
                await conn.close()
                conn = None

    print("\n❌ Todos los métodos de conexión fallaron.")
    print("\nRecomendaciones para solucionar el problema:")
    print("1. Verificar que la dirección IP de tu computadora esté permitida en el firewall de Azure PostgreSQL")
    print("2. Comprobar que el servidor PostgreSQL esté activo y funcionando")
    print("3. Verificar que el nombre de host sea correcto")
    print("4. Asegurarse de que no haya un firewall local bloqueando la conexión")
    print("5. Intentar conectarse desde otra red para descartar problemas de red locales")

if __name__ == "__main__":
    asyncio.run(main())