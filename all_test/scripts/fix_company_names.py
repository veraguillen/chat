import psycopg2
from psycopg2.extras import DictCursor

def fix_encoding(text):
    if not text:
        return text
        
    # Mapeo de códigos hexadecimales problemáticos a caracteres correctos
    char_map = {
        '\xa0': 'á',  # Espacio duro antes de 'n' en "Baz n"
        '\xed': 'í',   # í en "Consultoría"
        '\xe9': 'é',   # é en "Ehécatl"
        '\xf3': 'ó',   # ó en "tecnológicas"
        '\xe1': 'á',   # á en "Filantropía"
        '\xed': 'í',   # í en "político"
        '\xed': 'í',   # í en "tecnologías"
    }
    
    # Reemplazar caracteres problemáticos
    for bad, good in char_map.items():
        text = text.replace(bad, good)
        
    # Corregir espacios duros
    text = text.replace('Baz n', 'Bazán')
    
    # Corregir " reas" -> "áreas"
    text = text.replace(' reas', ' áreas')
    
    return text

try:
    # Conectar a la base de datos
    conn = psycopg2.connect(
        host="bot.writer.postgres.database.azure.com",
        database="chatbot_db",
        user="useradmin",
        password="Chat8121943.",
        port="5432",
        client_encoding='utf8'
    )
    
    cur = conn.cursor(cursor_factory=DictCursor)

    # Obtener los datos
    print("=== Actualizando registros con problemas de codificación ===")
    cur.execute("SELECT id, name, description FROM companies")
    rows = cur.fetchall()
    
    updates = []
    
    for row in rows:
        original_name = row['name']
        original_desc = row['description']
        
        fixed_name = fix_encoding(original_name)
        fixed_desc = fix_encoding(original_desc)
        
        if fixed_name != original_name or fixed_desc != original_desc:
            updates.append((fixed_name, fixed_desc, row['id']))
            print(f"\nID: {row['id']}")
            print(f"Antes - Nombre: {original_name}")
            print(f"Después - Nombre: {fixed_name}")
            if original_desc:
                print(f"Antes - Desc: {original_desc[:60]}...")
                print(f"Después - Desc: {fixed_desc[:60]}...")
    
    if updates:
        confirm = input("\n¿Deseas aplicar estos cambios? (s/n): ")
        if confirm.lower() == 's':
            cur.executemany("""
                UPDATE companies 
                SET name = %s, 
                    description = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, updates)
            conn.commit()
            print(f"\n¡Se actualizaron {len(updates)} registros!")
        else:
            print("\nOperación cancelada.")
    else:
        print("\nNo se encontraron registros que necesiten corrección.")

except Exception as e:
    print(f"\nError: {e}")
    if 'conn' in locals():
        conn.rollback()
finally:
    if 'cur' in locals():
        cur.close()
    if 'conn' in locals():
        conn.close()