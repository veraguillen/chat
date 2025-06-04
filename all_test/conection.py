import os
import psycopg2 # O asyncpg si lo estás usando y el script es asíncrono
import ssl
from dotenv import load_dotenv

load_dotenv() # Carga variables desde .env

# Usar valores directos que sabemos que funcionan
# Estos son los valores oficiales correctos
HOST = "chatbot-iram.postgres.database.azure.com"  # Host correcto
DATABASE = "chatbot_db"  # Base de datos correcta
USER = "useradmin"
PASSWORD = "Chat8121943."  # Usando la contraseña del .env
PORT = "5432"

# La URL oficial completa
DATABASE_URL = f"postgresql+asyncpg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"

print("\n🔄 Attempting database connection...")
print(f"Host: {HOST}")
print(f"Database: {DATABASE}")
print(f"User: {USER}")
print(f"Port: {PORT}")
print(f"SSL Mode: require")
print(f"Using corrected values from user input")

# Crear un contexto SSL menos estricto
ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

conn = None
try:
    print("Intentando conexión con configuración SSL menos estricta y valores corregidos...")
    conn_params = {
        "host": HOST,
        "dbname": DATABASE,
        "user": USER,
        "password": PASSWORD,
        "port": PORT,
        "sslmode": 'require',
        "connect_timeout": 60  # Aumentar el timeout a 60 segundos
    }
    
    # Usar el contexto SSL personalizado
    conn = psycopg2.connect(**conn_params, sslrootcert=None)
    
    # Si la conexión es exitosa, puedes hacer una consulta simple
    cur = conn.cursor()
    cur.execute("SELECT version();")
    db_version = cur.fetchone()
    print(f"✅ Connection successful! PostgreSQL version: {db_version[0]}")
    cur.close()

except psycopg2.Error as e: # Captura específicamente errores de psycopg2
    print(f"❌ Connection failed (psycopg2.Error): {e}")
    # e.pgcode y e.pgerror pueden dar más detalles específicos de PostgreSQL
    if hasattr(e, 'pgcode') and e.pgcode:
        print(f"   PostgreSQL Error Code: {e.pgcode}")
    if hasattr(e, 'diag') and e.diag and hasattr(e.diag, 'message_detail') and e.diag.message_detail:
         print(f"   Detail: {e.diag.message_detail}")
except Exception as e: # Captura cualquier otro error
    print(f"❌ Connection failed (General Exception): {type(e).__name__} - {e}")
finally:
    if conn:
        conn.close()
    # Las sugerencias de troubleshooting que ya tenías son buenas
    if not conn: # Si la conexión no se estableció
        print("\n⚠️ Troubleshooting steps:")
        print("1. Check if the server is accepting connections (Azure Portal > Your DB Server > Overview > Status).")
        print("2. Verify your current public IP is allowed in Azure PostgreSQL firewall rules (Azure Portal > Your DB Server > Networking).")
        print("3. Confirm SSL mode is properly configured (should be 'require' for Azure).")
        print("4. Double-check if the host is correct. The current host is: " + HOST)
        print("5. Ensure password does not contain special characters that need URL encoding.")
        print("6. Verify that your IP address is allowed in the Azure PostgreSQL firewall rules.")