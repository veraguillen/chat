import asyncio
import asyncpg
from app.core.config import settings

async def check_column():
    # Parse the DATABASE_URL to get connection parameters
    conn_params = {
        'host': settings.PGHOST,
        'port': settings.PGPORT,
        'database': settings.PGDATABASE,
        'user': settings.PGUSER,
        'password': settings.PGPASSWORD,
        'ssl': 'require'
    }
    
    conn = await asyncpg.connect(**conn_params)
    
    try:
        # Check if the column exists
        result = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'user_states' 
                AND column_name = 'session_explicitly_ended'
            );
            """
        )
        
        if result:
            print("✅ The column 'session_explicitly_ended' exists in the 'user_states' table.")
        else:
            print("❌ The column 'session_explicitly_ended' does NOT exist in the 'user_states' table.")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_column())
