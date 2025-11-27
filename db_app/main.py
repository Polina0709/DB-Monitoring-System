import os
import random
import time
from threading import Thread

import psutil
import pika
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.responses import Response
from jose import jwt, JWTError
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal, engine
from models import Base, Measurement, Item

# ---- Init DB ----
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


# ---- Prometheus metrics ----
REQUESTS = Counter("db_app_requests_total", "Total API requests")
QUERY_TIME = Histogram("db_app_query_seconds", "DB query duration seconds")

GEN_OP_DURATION = Histogram(
    "generator_operation_duration_seconds",
    "Synthetic generator operation duration",
)
GEN_CPU_USAGE = Gauge(
    "generator_cpu_usage_percent",
    "Generator CPU usage percent",
)

RABBIT_PUBLISHED = Counter(
    "rabbitmq_messages_published_total",
    "Messages published to RabbitMQ from db_app",
)

app = FastAPI(title="DB App with Metrics, Auth & Generator")


# ---- RabbitMQ ----
def get_rabbit_channel():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq")
    )
    channel = connection.channel()
    channel.queue_declare(queue="measurements")
    return connection, channel


# ---- Background Data Generator ----
def writer_loop():
    rabbit_conn = None
    rabbit_channel = None

    while True:
        # 1) Operation duration (for Grafana)
        op_start = time.perf_counter()
        time.sleep(random.uniform(0.03, 0.07))
        GEN_OP_DURATION.observe(time.perf_counter() - op_start)

        # CPU usage metric
        GEN_CPU_USAGE.set(psutil.cpu_percent(interval=None))

        # 2) Insert into DB
        db: Session = SessionLocal()
        start = time.perf_counter()

        try:
            value = random.uniform(0, 100)
            db.add(Measurement(value=value))
            db.commit()
        finally:
            QUERY_TIME.observe(time.perf_counter() - start)
            db.close()

        # 3) Publish to RabbitMQ
        try:
            if rabbit_conn is None or rabbit_conn.is_closed:
                rabbit_conn, rabbit_channel = get_rabbit_channel()

            body = f"New measurement: {value:.2f}"
            rabbit_channel.basic_publish(
                exchange="",
                routing_key="measurements",
                body=body,
            )
            RABBIT_PUBLISHED.inc()

        except Exception:
            rabbit_conn = None
            rabbit_channel = None

        time.sleep(1)


@app.on_event("startup")
def start_background_tasks():
    Thread(target=writer_loop, daemon=True).start()


# ---- MODELS ----
from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    value: int


# ---- ENDPOINTS ----
@app.get("/health")
def health():
    REQUESTS.inc()
    return {"status": "ok"}


@app.get("/count")
def count(user=Depends(auth_required), db: Session = Depends(get_db)):
    REQUESTS.inc()
    result = db.query(func.count(Measurement.id)).scalar()
    return {"rows": result}


# ---------- NEW ENDPOINTS (Traffic Simulator Compatibility) ----------

@app.post("/items")
def create_item(payload: ItemCreate, user=Depends(auth_required), db: Session = Depends(get_db)):
    REQUESTS.inc()
    start = time.perf_counter()

    try:
        item = Item(name=payload.name, value=payload.value)
        db.add(item)
        db.commit()
        QUERY_TIME.observe(time.perf_counter() - start)
        return {"id": item.id, "name": item.name, "value": item.value}

    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Insert error")


@app.get("/items")
def get_items(user=Depends(auth_required), db: Session = Depends(get_db)):
    REQUESTS.inc()
    start = time.perf_counter()

    items = db.query(Item).all()
    QUERY_TIME.observe(time.perf_counter() - start)

    return [
        {"id": i.id, "name": i.name, "value": i.value}
        for i in items
    ]


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
