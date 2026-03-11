import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load variables from the root .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_volco_db():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"❌ Volco DB Connection Failed: {e}")
        return None

def authenticate_mobile_user(email, password):
    """
    Checks the database for the user's email and password.
    Returns the User ID if successful, or None if it fails.
    """
    conn = get_volco_db()
    if not conn: 
        return None

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Search the Users table for a match
        cur.execute("""
            SELECT id, name, email FROM users 
            WHERE email = %s AND password = %s
        """, (email, password))
        
        user = cur.fetchone()
        return user 
        
    except Exception as e:
        print(f"❌ Authentication Error: {e}")
        return None
    finally:
        cur.close()
        conn.close()