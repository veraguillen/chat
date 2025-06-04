import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import os

def add_missing_column():
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
        conn.autocommit = True  # Enable autocommit for DDL statements
        cursor = conn.cursor()
        print("✅ Successfully connected to the database")
        
        # Add the missing column
        print("\n🔧 Adding missing column 'session_explicitly_ended' to 'user_states' table...")
        
        cursor.execute("""
            ALTER TABLE user_states 
            ADD COLUMN IF NOT EXISTS session_explicitly_ended BOOLEAN NOT NULL DEFAULT FALSE;
        """)
        
        print("✅ Column 'session_explicitly_ended' added successfully")
        
        # Verify the column was added
        print("\n🔍 Verifying the column was added...")
        cursor.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'user_states' 
            AND column_name = 'session_explicitly_ended';
        """)
        
        column_info = cursor.fetchone()
        if column_info:
            print(f"✅ Column verified:")
            print(f"   - Name: {column_info[0]}")
            print(f"   - Type: {column_info[1]}")
            print(f"   - Default: {column_info[2]}")
            print(f"   - Nullable: {column_info[3]}")
        else:
            print("❌ Column was not added successfully")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Database connection closed.")

if __name__ == "__main__":
    add_missing_column()
