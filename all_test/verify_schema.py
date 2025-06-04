import os
import subprocess
from dotenv import load_dotenv

def run_psql_command(sql):
    """Run a SQL command using psql and return the output."""
    load_dotenv()
    
    # Build the psql command
    cmd = [
        'psql',
        '-h', os.getenv('PGHOST'),
        '-p', str(os.getenv('PGPORT', '5432')),  # Ensure port is a string
        '-d', os.getenv('PGDATABASE'),
        '-U', os.getenv('PGUSER'),
        '-c', sql
    ]
    
    # Set PGPASSWORD in the environment
    env = os.environ.copy()
    env['PGPASSWORD'] = os.getenv('PGPASSWORD', '')
    
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing psql command: {e}")
        print(f"STDERR: {e.stderr}")
        return None

def main():
    print("🔍 Checking database schema...")
    
    # Check if the column exists
    sql = """
    SELECT 
        column_name, 
        data_type 
    FROM 
        information_schema.columns 
    WHERE 
        table_name = 'user_states' 
        AND column_name = 'session_explicitly_ended';
    """
    
    print("\n🔎 Checking for 'session_explicitly_ended' column in 'user_states' table:")
    result = run_psql_command(sql)
    if result:
        if "0 rows" in result:
            print("❌ Column 'session_explicitly_ended' does NOT exist in 'user_states' table.")
        else:
            print("✅ Column 'session_explicitly_ended' exists in 'user_states' table.")
        print(result.strip())
    
    # List all tables
    print("\n📋 Listing all tables in the database:")
    tables = run_psql_command("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    if tables:
        print(tables.strip())

if __name__ == "__main__":
    main()
