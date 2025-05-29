import os
import psycopg2 # O asyncpg si lo estás usando y el script es asíncrono
from dotenv import load_dotenv

load_dotenv() # Carga variables desde .env

PGHOST = os.getenv('PGHOST')
PGDATABASE = os.getenv('PGDATABASE')
PGUSER = os.getenv('PGUSER')
PGPASSWORD = os.getenv('PGPASSWORD')
PGSSLMODE = os.getenv('PGSSLMODE', 'require') # Default a 'require' si no está en .env

print("\n🔄 Attempting database connection...")
print(f"Host: {PGHOST}")
print(f"Database: {PGDATABASE}")
print(f"User: {PGUSER}")
# No imprimas la contraseña en los logs por seguridad
# print(f"Password: {'Present' if PGPASSWORD else 'Not set'}") 
print(f"SSL Mode: {PGSSLMODE}")

conn = None
try:
    if not all([PGHOST, PGDATABASE, PGUSER, PGPASSWORD]):
        print("❌ Connection failed: Missing one or more connection parameters (PGHOST, PGDATABASE, PGUSER, PGPASSWORD).")
    else:
        conn_params = {
            "host": PGHOST,
            "dbname": PGDATABASE, # psycopg2 usa 'dbname'
            "user": PGUSER,
            "password": PGPASSWORD,
            "sslmode": PGSSLMODE
        }
        conn = psycopg2.connect(**conn_params)
        
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
        print("4. Double-check PGHOST, PGDATABASE, PGUSER, PGPASSWORD for typos or incorrect values.")
        print("5. Ensure password does not contain special characters that need URL encoding if used in a full DATABASE_URL (though less relevant here).")