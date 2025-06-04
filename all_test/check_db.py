import asyncio
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def check_schema():
    # Create an async engine
    engine = create_async_engine(settings.DATABASE_URL)
    
    # Get the inspector
    async with engine.connect() as conn:
        inspector = await conn.run_sync(
            lambda conn: inspect(conn)
        )
        
        # Get table info
        tables = await conn.run_sync(
            lambda conn: inspector.get_table_names()
        )
        print("\nTables in database:", tables)
        
        if 'user_states' in tables:
            columns = await conn.run_sync(
                lambda conn: inspector.get_columns('user_states')
            )
            print("\nColumns in user_states table:")
            for column in columns:
                print(f"- {column['name']} ({column['type']})")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_schema())
