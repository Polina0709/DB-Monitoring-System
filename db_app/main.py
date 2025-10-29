import os
import random
import time
from threading import Thread

from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.responses import Response
from jose import jwt, JWTError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import func
from sqlalchemy.orm import Session

import pika

from database import SessionLocal, engine
from models import Base, Measurement

# ---- Ініціалізація БД ----
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---- JWT ----
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
JWT_ALGO = os.getenv("JWT_ALGO", "HS256")

def auth_required(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = auth.split(" ")[1]
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# ---- Метрики Prometheus ----
REQUESTS = Counter("db_app_requests_total", "Total API requests")
QUERY_TIME = Histogram("db_app_query_seconds", "DB query duration seconds")

# ---- FastAPI ----
app = FastAPI(title="DB App with Metrics, Auth & RabbitMQ")

# ---- RabbitMQ ----
def get_rabbit_channel():
    """
    Створює з’єднання та чергу. Якщо RabbitMQ ще не піднявся — повертає None.
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        channel = connection.channel()
        channel.queue_declare(queue='measurements')
        return channel
    except:
        return None

# ---- Фоновий процес: записує дані в БД + відправляє повідомлення ----
def writer_loop():
    channel = None

    while True:
        db: Session = SessionLocal()
        start = time.perf_counter()
        try:
            value = random.uniform(0, 100)

            # Запис у БД
            db.add(Measurement(value=value))
            db.commit()

            # Спроба встановити канал якщо ще None
            if channel is None:
                channel = get_rabbit_channel()

            # Спроба відправити повідомлення
            if channel:
                try:
                    channel.basic_publish(exchange='', routing_key='measurements', body=f"{value:.2f}")
                except:
                    channel = None  # якщо RabbitMQ перезапустився → відновимо на наступній ітерації

        finally:
            QUERY_TIME.observe(time.perf_counter() - start)
            db.close()

        time.sleep(1)

# Запускаємо фонову задачу
@app.on_event("startup")
def start_background_task():
    Thread(target=writer_loop, daemon=True).start()

# ---- API ----

@app.get("/health")
def health():
    REQUESTS.inc()
    return {"status": "ok"}

@app.get("/count")
def count(user=Depends(auth_required), db: Session = Depends(get_db)):
    REQUESTS.inc()
    result = db.query(func.count(Measurement.id)).scalar()
    return {"rows": result}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
