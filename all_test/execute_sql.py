import psycopg2
from dotenv import load_dotenv
import os

def execute_sql():
    load_dotenv()
    
    # Get database connection parameters
    conn_params = {
        'host': os.getenv('PGHOST'),
        'port': 5432,
        'database': os.getenv('PGDATABASE'),
        'user': os.getenv('PGUSER'),
        'password': os.getenv('PGPASSWORD'),
        'sslmode': 'require'
    }
    
    print("🔍 Connecting to the database...")
    
    try:
        # Connect to the database
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        print("✅ Successfully connected to the database")
        
        # Check user_states table
        print("\n🔍 Checking user_states table...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'user_states';
        """)
        
        print("\n📋 user_states table columns:")
        for col in cursor.fetchall():
            print(f"- {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'} "
                  f"DEFAULT {col[3] if col[3] else 'None'}")
        
        # Check alembic_version table
        print("\n🔍 Checking alembic_version table...")
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            );
        """)
        
        if cursor.fetchone()[0]:
            cursor.execute("SELECT version_num FROM alembic_version;")
            version = cursor.fetchone()
            if version:
                print(f"✅ Alembic version: {version[0]}")
        else:
            print("❌ alembic_version table does not exist")
        
        # Check if session_explicitly_ended column exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'user_states' 
                AND column_name = 'session_explicitly_ended'
            );
        """)
        
        column_exists = cursor.fetchone()[0]
        if not column_exists:
            print("\n❌ Column 'session_explicitly_ended' does not exist. Adding it now...")
            cursor.execute("""
                ALTER TABLE user_states 
                ADD COLUMN session_explicitly_ended BOOLEAN NOT NULL DEFAULT FALSE;
            """)
            conn.commit()
            print("✅ Column 'session_explicitly_ended' added successfully")
        else:
            print("\n✅ Column 'session_explicitly_ended' already exists")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Database connection closed.")

if __name__ == "__main__":
    execute_sql()
