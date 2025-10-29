import os
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from passlib.hash import bcrypt
from jose import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")
TOKEN_TTL_MIN = 60

app = FastAPI(title="Auth Service")

engine = create_engine("sqlite:///./users.db", connect_args={"check_same_thread": False})

# Ініціалізуємо таблицю користувачів
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT
        );
    """))

class Creds(BaseModel):
    username: str
    password: str

@app.post("/register")
def register(c: Creds):
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users(username, password_hash) VALUES (:u, :p)"
            ), {"u": c.username, "p": bcrypt.hash(c.password)})
        return {"ok": True}
    except:
        raise HTTPException(status_code=400, detail="User already exists")

@app.post("/login")
def login(c: Creds):
    with engine.begin() as conn:
        row = conn.execute(text(
            "SELECT password_hash FROM users WHERE username=:u"
        ), {"u": c.username}).fetchone()

    if not row or not bcrypt.verify(c.password, row[0]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    now = datetime.utcnow()
    token = jwt.encode(
        {"sub": c.username, "exp": now + timedelta(minutes=TOKEN_TTL_MIN)},
        JWT_SECRET,
        algorithm=JWT_ALGO,
    )
    return {"access_token": token, "token_type": "bearer"}
