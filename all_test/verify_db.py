import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def check_database():
    # Load environment variables
    load_dotenv()
    
    # Get database connection parameters
    db_params = {
        'host': os.getenv('PGHOST'),
        'port': int(os.getenv('PGPORT', '5432')),  # Convert port to integer
        'database': os.getenv('PGDATABASE'),
        'user': os.getenv('PGUSER'),
        'password': os.getenv('PGPASSWORD'),
        'ssl': 'require'
    }
    
    print("🔍 Connecting to the database...")
    
    try:
        # Connect to the database
        conn = await asyncpg.connect(**db_params)
        print("✅ Successfully connected to the database")
        
        # Check if the column exists
        column_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'user_states' 
                AND column_name = 'session_explicitly_ended'
            );
            """
        )
        
        if column_exists:
            print("✅ The column 'session_explicitly_ended' exists in the 'user_states' table.")
        else:
            print("❌ The column 'session_explicitly_ended' does NOT exist in the 'user_states' table.")
        
        # Show current tables in the database
        print("\n📋 Current tables in the database:")
        tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        for table in tables:
            print(f"- {table['table_name']}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        if 'conn' in locals():
            await conn.close()
            print("\n🔌 Database connection closed.")

if __name__ == "__main__":
    asyncio.run(check_database())
