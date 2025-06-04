import psycopg2
from dotenv import load_dotenv
import os

def drop_backup_tables():
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
    
    tables_to_drop = [
        'companies_backup_raw',
        'companies_backup_20240604'
    ]
    
    print("🔍 Connecting to the database...")
    
    try:
        # Connect to the database
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True  # Enable autocommit for DDL statements
        cursor = conn.cursor()
        print("✅ Successfully connected to the database")
        
        # Check which tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name = ANY(%s);
        """, (tables_to_drop,))
        
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        if not existing_tables:
            print("\nℹ️ No backup tables to drop.")
            return
            
        print("\n📋 Found the following backup tables to drop:")
        for table in existing_tables:
            print(f"- {table}")
            
        # Ask for confirmation
        confirm = input("\n⚠️  Are you sure you want to drop these tables? (y/n): ")
        if confirm.lower() != 'y':
            print("\n❌ Operation cancelled by user")
            return
            
        # Drop the tables
        for table in existing_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                print(f"✅ Dropped table: {table}")
            except Exception as e:
                print(f"❌ Error dropping table {table}: {str(e)}")
        
        print("\n✅ All specified backup tables have been dropped")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Database connection closed.")

if __name__ == "__main__":
    drop_backup_tables()
