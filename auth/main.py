import os
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
from jose import jwt
from passlib.hash import bcrypt
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")
TOKEN_TTL_MIN = 60

app = FastAPI(title="Auth Service")

# SQLite DB
engine = create_engine("sqlite:///./users.db", connect_args={"check_same_thread": False})

with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT
        );
    """))

# Metrics
REGISTERED_USERS = Gauge("auth_registered_users", "Current number of registered users")
REGISTRATION_TOTAL = Counter("auth_registration_total", "Total registration attempts")
LOGIN_ATTEMPTS = Counter("auth_login_attempts_total", "Total login attempts")
LOGIN_SUCCESS = Counter("auth_successful_logins_total", "Successful logins")
LOGIN_FAILED = Counter("auth_failed_logins_total", "Failed logins")
LOGIN_DURATION = Histogram("auth_login_duration_seconds", "Login duration seconds")


def update_user_count():
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    REGISTERED_USERS.set(count)


class Creds(BaseModel):
    username: str
    password: str


@app.post("/register")
def register(c: Creds):
    REGISTRATION_TOTAL.inc()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users(username, password_hash) VALUES (:u, :p)"),
                {"u": c.username, "p": bcrypt.hash(c.password)},
            )
    except IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists")
    except Exception as e:
        print("REGISTER ERROR:", repr(e))
        raise HTTPException(status_code=500, detail="Registration error")

    update_user_count()
    return {"ok": True}


@app.post("/login")
def login(c: Creds):
    LOGIN_ATTEMPTS.inc()
    start = datetime.utcnow()

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM users WHERE username=:u"),
            {"u": c.username}
        ).fetchone()

    if not row or not bcrypt.verify(c.password, row[0]):
        LOGIN_FAILED.inc()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    LOGIN_SUCCESS.inc()
    LOGIN_DURATION.observe((datetime.utcnow() - start).total_seconds())

    token = jwt.encode(
        {"sub": c.username, "exp": datetime.utcnow() + timedelta(minutes=TOKEN_TTL_MIN)},
        JWT_SECRET,
        algorithm=JWT_ALGO,
    )
    return {"access_token": token, "token_type": "bearer"}


# ================================================
# =============  SIMPLE HTML PAGES  ==============
# ================================================
@app.get("/register_page", response_class=HTMLResponse)
def register_page():
    return """
    <html>
    <body>
        <h2>Register</h2>
        <input id="u" placeholder="Username"><br><br>
        <input id="p" placeholder="Password" type="password"><br><br>
        <button onclick="send()">Register</button>
        <p id="msg"></p>

<script>
function send() {
    const u = document.getElementById("u").value;
    const p = document.getElementById("p").value;

    fetch('/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: u, password: p})
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById("msg").innerText = JSON.stringify(data);
    });
}
</script>
    </body>
    </html>
    """


@app.get("/login_page", response_class=HTMLResponse)
def login_page():
    return """
    <html>
    <body>
        <h2>Login</h2>
        <input id="u" placeholder="Username"><br><br>
        <input id="p" placeholder="Password" type="password"><br><br>
        <button onclick="login()">Login</button>
        <p id="msg"></p>

<script>
function login() {
    const u = document.getElementById("u").value;
    const p = document.getElementById("p").value;

    fetch('/login', {
        method:'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: u, password: p})
    })
    .then(r => r.json())
    .then(data => {
        if (data.access_token) {
            localStorage.setItem('jwt', data.access_token);
        }
        document.getElementById("msg").innerText = JSON.stringify(data);
    });
}
</script>

    </body>
    </html>
    """


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
