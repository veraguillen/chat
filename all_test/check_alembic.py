import asyncio
import asyncpg
from dotenv import load_dotenv

async def check_alembic_version():
    load_dotenv()
    
    conn = await asyncpg.connect(
        host=os.getenv('PGHOST'),
        port=5432,
        database=os.getenv('PGDATABASE'),
        user=os.getenv('PGUSER'),
        password=os.getenv('PGPASSWORD'),
        ssl='require'
    )
    
    try:
        # Check if alembic_version table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            );
            """
        )
        
        if table_exists:
            version = await conn.fetchval("SELECT version_num FROM alembic_version;")
            print(f"✅ Alembic version: {version}")
        else:
            print("❌ alembic_version table does not exist")
            
        # Check if user_states table exists and has the column
        user_states_columns = await conn.fetch(
            """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_states';
            """
        )
        
        print("\n📋 user_states table columns:")
        for col in user_states_columns:
            print(f"- {col['column_name']} ({col['data_type']})")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        await conn.close()

if __name__ == "__main__":
    import os
    asyncio.run(check_alembic_version())
