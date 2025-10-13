import os
import sys
import psycopg2
import glob
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def execute_sql_files(connection_string):
    """Execute all SQL files in the current directory in numerical order."""
    try:
        # Connect to the database
        print("[MANUAL SETUP] Connecting to database...")
        conn = psycopg2.connect(connection_string)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Enable pgvector extension first
        print("[MANUAL SETUP] Enabling pgvector extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("[MANUAL SETUP] pgvector extension enabled")
        
        # Get all SQL files and sort them numerically
        sql_files = glob.glob(os.path.join(os.path.dirname(__file__), "*.sql"))
        sql_files.sort(key=lambda f: int(os.path.basename(f).split('_')[0]))
        
        # Execute each SQL file in order
        for sql_file in sql_files:
            file_name = os.path.basename(sql_file)
            print(f"[MANUAL SETUP] Executing {file_name}...")
            
            with open(sql_file, 'r') as f:
                sql_content = f.read()
                cursor.execute(sql_content)
            
            print(f"[MANUAL SETUP] {file_name} executed successfully")
        
        cursor.close()
        conn.close()
        print("[MANUAL SETUP] Database setup completed successfully!")
        
    except Exception as e:
        print(f"[MANUAL SETUP] Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    execute_sql_files(DATABASE_URL)