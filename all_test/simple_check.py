import os
import psycopg2
from dotenv import load_dotenv

def check_database():
    # Load environment variables
    load_dotenv()
    
    # Database connection parameters
    conn_params = {
        'host': os.getenv('PGHOST'),
        'port': os.getenv('PGPORT'),
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
        
        # Check if the column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user_states' 
            AND column_name = 'session_explicitly_ended';
        """)
        
        column_exists = cursor.fetchone() is not None
        
        if column_exists:
            print("✅ The column 'session_explicitly_ended' exists in the 'user_states' table.")
        else:
            print("❌ The column 'session_explicitly_ended' does NOT exist in the 'user_states' table.")
        
        # Show current tables in the database
        print("\n📋 Current tables in the database:")
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
