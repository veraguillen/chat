import psycopg2
import ssl

# Usar valores directos que sabemos que funcionan
HOST = "chatbot-iram.postgres.database.azure.com"
DATABASE = "chatbot_db"
USER = "useradmin"
PASSWORD = "Chat8121943."
PORT = "5432"

print("\n🔄 Intentando conexión a PostgreSQL con psycopg2...")
print(f"Host: {HOST}")
print(f"Database: {DATABASE}")
print(f"User: {USER}")
print(f"Port: {PORT}")

# Crear un contexto SSL menos estricto
ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Intentar diferentes métodos de conexión
methods = [
    {
        "name": "Método 1: sslmode=require",
        "params": {
            "host": HOST,
            "dbname": DATABASE,
            "user": USER,
            "password": PASSWORD,
            "port": PORT,
            "sslmode": "require",
            "connect_timeout": 10
        }
    },
    {
        "name": "Método 2: sslmode=verify-ca",
        "params": {
            "host": HOST,
            "dbname": DATABASE,
            "user": USER,
            "password": PASSWORD,
            "port": PORT,
            "sslmode": "verify-ca",
            "connect_timeout": 10
        }
    },
    {
        "name": "Método 3: SSL Context personalizado",
        "params": {
            "host": HOST,
            "dbname": DATABASE,
            "user": USER,
            "password": PASSWORD,
            "port": PORT,
            "sslmode": "require",
            "connect_timeout": 10
        },
        "ssl_context": ssl_context
    }
]

success = False

for method in methods:
    print(f"\n🔄 Intentando {method['name']}...")
    conn = None
    try:
        if "ssl_context" in method:
            conn = psycopg2.connect(**method["params"], sslrootcert=None)
        else:
            conn = psycopg2.connect(**method["params"])
        
        # Si la conexión es exitosa, hacer una consulta simple
        cur = conn.cursor()
        cur.execute("SELECT version();")
        db_version = cur.fetchone()
        print(f"✅ Conexión exitosa con {method['name']}! PostgreSQL version: {db_version[0]}")
        cur.close()
        success = True
        break  # Salir del bucle si la conexión es exitosa
    except psycopg2.Error as e:
        print(f"❌ Conexión fallida con {method['name']}: {e}")
        if hasattr(e, 'pgcode') and e.pgcode:
            print(f"   PostgreSQL Error Code: {e.pgcode}")
        if hasattr(e, 'diag') and e.diag and hasattr(e.diag, 'message_detail') and e.diag.message_detail:
            print(f"   Detail: {e.diag.message_detail}")
    except Exception as e:
        print(f"❌ Error general con {method['name']}: {type(e).__name__} - {e}")
    finally:
        if conn:
            conn.close()

if not success:
    print("\n❌ Todos los métodos de conexión fallaron.")
    print("\nRecomendaciones para solucionar el problema:")
    print("1. Verificar que la dirección IP de tu computadora esté permitida en el firewall de Azure PostgreSQL")
    print("   - En el portal de Azure, ve a tu servidor PostgreSQL")
    print("   - Selecciona 'Seguridad de conexión' o 'Networking'")
    print("   - Añade tu dirección IP actual a las reglas del firewall")
    print("2. Comprobar que el servidor PostgreSQL esté activo y funcionando")
    print("3. Verificar que el nombre de host sea correcto")
    print("4. Comprobar si hay un firewall local o antivirus bloqueando la conexión")
    print("5. Intentar conectarse desde otra red para descartar problemas de red locales")
