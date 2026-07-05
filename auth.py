from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from uuid import uuid4

from db import get_db_connection
from volco.security import hash_password, verify_password, needs_rehash

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterReq(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginReq(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register(data: RegisterReq):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")
    
    cur = conn.cursor()
    try:
        # Check if email exists
        cur.execute("SELECT id FROM users WHERE email=%s", (data.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already exists")

        user_id = str(uuid4())
        hashed_password = hash_password(data.password)

        cur.execute(
            "INSERT INTO users (id, email, password, name) VALUES (%s, %s, %s, %s)",
            (user_id, data.email, hashed_password, data.name)
        )
        conn.commit()

        return {
            "id": user_id,
            "email": data.email,
            "name": data.name
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Register Error: {e}")
        # Return generic error to user, log specific error to console
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        cur.close()
        conn.close()

@router.post("/login")
def login(data: LoginReq):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, email, password, name FROM users WHERE email=%s",
            (data.email,)
        )
        user = cur.fetchone()

        # user[2] is the password column (index 2 in the SELECT statement)
        if not user or not verify_password(data.password, user[2]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Opportunistically upgrade the hash if the scheme is outdated
        if needs_rehash(user[2]):
            new_hash = hash_password(data.password)
            cur.execute("UPDATE users SET password = %s WHERE id = %s", (new_hash, user[0]))

        return {
            "id": user[0],
            "email": user[1],
            "name": user[3]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login Error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        cur.close()
        conn.close()