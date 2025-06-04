import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import os

def check_database():
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
        
        # Check if user_states table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user_states'
            );
        """)
        
        if cursor.fetchone()[0]:
            print("\n📋 user_states table columns:")
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'user_states';
            """)
            
            for col in cursor.fetchall():
                print(f"- {col[0]} ({col[1]})")
        else:
            print("❌ user_states table does not exist")
            
        # Check if alembic_version table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            );
        """)
        
        if cursor.fetchone()[0]:
            cursor.execute("SELECT version_num FROM alembic_version;")
            version = cursor.fetchone()
            if version:
                print(f"\n✅ Alembic version: {version[0]}")
        else:
            print("\n❌ alembic_version table does not exist")
            
        # Show all tables in the database
        print("\n📋 All tables in the database:")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        
        for table in cursor.fetchall():
            print(f"- {table[0]}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Database connection closed.")

if __name__ == "__main__":
    check_database()
