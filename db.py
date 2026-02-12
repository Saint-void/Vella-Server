import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Use the environment variable, or fallback to your string if .env fails
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:Donaldefe1.@localhost:5432/vella")

def get_db_connection():
    """Establishes a new connection to the database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"❌ Database Connection Failed: {e}")
        return None

def init_db():
    """
    Creates the necessary tables (Users, History & Sessions) if they don't exist.
    Run this when the app starts.
    """
    conn = get_db_connection()
    if not conn:
        return

    cur = conn.cursor()
    
    try:
        # 0. Users Table (Auth) - ADDED THIS
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 1. Sessions Table (The Sidebar List)
        # Stores the "Title" and "ID" of each conversation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 2. Messages Table (The Actual Chat)
        # Stores every message linked to a session_id
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL, -- 'user' or 'model'
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        print("✅ Database Tables Initialized (Users, Sessions & Messages)")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
    finally:
        cur.close()
        conn.close()

# --- HELPER FUNCTIONS ---

def save_message(session_id, user_id, role, content, title=None):
    """Saves a single message to the database."""
    conn = get_db_connection()
    if not conn: return

    cur = conn.cursor()
    try:
        # 1. Ensure the Session exists. If not, create it.
        cur.execute("SELECT id FROM sessions WHERE id = %s", (session_id,))
        if not cur.fetchone():
            # If title isn't provided, use the first 30 chars of the message
            clean_title = title if title else (content[:30] + "...")
            cur.execute(
                "INSERT INTO sessions (id, user_id, title) VALUES (%s, %s, %s)",
                (session_id, user_id, clean_title)
            )

        # 2. Save the Message
        cur.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
            (session_id, role, content)
        )
    except Exception as e:
        print(f"❌ Error saving message: {e}")
    finally:
        cur.close()
        conn.close()

def get_user_sessions(user_id):
    """Fetches list of chats for the sidebar."""
    conn = get_db_connection()
    if not conn: return []

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT * FROM sessions 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def get_chat_history(session_id):
    """Fetches all messages for a specific chat."""
    conn = get_db_connection()
    if not conn: return []

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT role, content, created_at 
            FROM messages 
            WHERE session_id = %s 
            ORDER BY created_at ASC
        """, (session_id,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()