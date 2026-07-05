import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

from volco.security import hash_password

load_dotenv()

# No hardcoded fallback — a leaked credential in source is a compromised
# credential. Fail loudly instead so it's caught in dev, not production.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to your .env file — "
        "no fallback credential is used for security reasons."
    )

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

# --- USER / AUTH HELPERS ---

def create_user(email: str, password: str, name: str | None = None):
    """
    Creates a new user with a hashed password.
    This is the ONLY place a user row should be inserted — never insert
    into `users` directly elsewhere, or you'll end up with a plaintext
    password again.
    """
    conn = get_db_connection()
    if not conn:
        return None

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Reject duplicate emails with a clean error rather than a raw
        # IntegrityError bubbling up.
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            print(f"❌ User creation failed: email already registered ({email})")
            return None

        user_id = str(uuid.uuid4())
        hashed = hash_password(password)

        cur.execute("""
            INSERT INTO users (id, email, password, name)
            VALUES (%s, %s, %s, %s)
            RETURNING id, email, name, created_at
        """, (user_id, email, hashed, name))

        return cur.fetchone()

    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return None
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