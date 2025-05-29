import asyncio
import asyncpg
from dotenv import load_dotenv
import os

async def test_azure_connection():
    load_dotenv()

    print(f"Attempting to connect with:")
    print(f"Host: {os.getenv('PGHOST')}")
    print(f"User: {os.getenv('PGUSER')}")
    print(f"Database: {os.getenv('PGDATABASE')}")
    print(f"Port: {os.getenv('PGPORT')}")

    try:
        conn = await asyncpg.connect(
            host=os.getenv('PGHOST'),
            port=os.getenv('PGPORT'),
            user=os.getenv('PGUSER'),
            password=os.getenv('PGPASSWORD'),
            database=os.getenv('PGDATABASE'),
            ssl='require'
        )

        # First get version
        version = await conn.fetchval('SELECT version()')
        print(f"\n✅ Connected to Azure PostgreSQL!")
        print(f"Version: {version}")

        # Then check tables
        required_tables = ['companies', 'conversations', 'messages']
        for table in required_tables:
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                );
            """, table)
            if table_exists:
                columns = await conn.fetch("""
                    SELECT column_name, data_type, character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = 'public' 
                    AND table_name = $1
                    ORDER BY ordinal_position;
                """, table)
                print(f"\n✅ Table '{table}' exists with columns:")
                for col in columns:
                    print(f"   - {col['column_name']}: {col['data_type']}")

                # Check row count for each table
                row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"   → Total rows: {row_count}")
            else:
                print(f"\n❌ Table '{table}' does not exist")

        # Close connection only at the end
        await conn.close()
        print("\n✅ Connection closed successfully")

    except asyncpg.exceptions.InvalidPasswordError:
        print(f"\n❌ Connection failed: Invalid password for user {os.getenv('PGUSER')}")
    except asyncpg.exceptions.CannotConnectNowError as e:
        print(f"\n❌ Connection failed: Cannot connect to server. {e}")
    except Exception as e:
        print(f"\n❌ Connection failed: {type(e).__name__} - {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_azure_connection())