import psycopg2
from dotenv import load_dotenv
import os

def check_and_fix_schema():
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
        
        # Check if user_states table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_name = 'user_states'
            );
        """)
        
        if not cursor.fetchone()[0]:
            print("❌ Error: user_states table does not exist")
            return
            
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
            print("\n❌ Column 'session_explicitly_ended' is missing from 'user_states' table")
            print("🔧 Adding the missing column...")
            
            try:
                cursor.execute("""
                    ALTER TABLE user_states 
                    ADD COLUMN session_explicitly_ended BOOLEAN NOT NULL DEFAULT FALSE;
                """)
                print("✅ Successfully added 'session_explicitly_ended' column to 'user_states' table")
            except Exception as e:
                print(f"❌ Error adding column: {str(e)}")
                return
        else:
            print("\n✅ Column 'session_explicitly_ended' exists in 'user_states' table")
        
        # Verify the column was added
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'user_states' 
            AND column_name = 'session_explicitly_ended';
        """)
        
        column_info = cursor.fetchone()
        if column_info:
            print("\n📋 Column details:")
            print(f"- Name: {column_info[0]}")
            print(f"- Type: {column_info[1]}")
            print(f"- Nullable: {column_info[2]}")
            print(f"- Default: {column_info[3]}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
            print("\n🔌 Database connection closed.")

if __name__ == "__main__":
    check_and_fix_schema()
