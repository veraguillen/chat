import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

def check_database():
    # Load environment variables
    load_dotenv()
    
    # Get DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Parse DATABASE_URL
    if database_url.startswith('postgresql+asyncpg'):
        database_url = database_url.replace('postgresql+asyncpg', 'postgresql')
    
    print(f"🔗 Using DATABASE_URL: {database_url[:50]}...")
    
    try:
        # Connect to the database
        conn = psycopg2.connect(database_url, sslmode='require')
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
