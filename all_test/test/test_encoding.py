import psycopg2
from psycopg2 import sql

# Configuración de la conexión
conn_params = {
    "host": "bot.writer.postgres.database.azure.com",
    "database": "chatbot_db",
    "user": "useradmin",
    "password": "Chat8121943.",
    "port": "5432",
    "client_encoding": "UTF8",
    "options": "-c client_encoding=UTF8"
}

try:
    # Conectar a la base de datos
    conn = psycopg2.connect(**conn_params)
    cursor = conn.cursor()
    
    # Insertar datos con caracteres especiales
    cursor.execute("""
        INSERT INTO test_encoding (texto) 
        VALUES (%s)
    """, ('áéíóúñÑ ¿?¡!',))
    
    # Confirmar la transacción
    conn.commit()
    print("¡Inserción exitosa!")
    
    # Verificar los datos
    cursor.execute("SELECT * FROM test_encoding")
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, Texto: {row[1]}")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()