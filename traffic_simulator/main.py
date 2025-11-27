import time
import random
import string
import threading
from datetime import datetime, timedelta

import requests
import pika
from fastapi import FastAPI
from pydantic import BaseModel

from prometheus_client import (
    start_http_server,
    Counter,
    Gauge,
    Histogram
)

AUTH_URL = "http://auth:7000"
DB_APP_URL = "http://db_app:8000"
RABBIT_HOST = "rabbitmq"


# ----------------------- METRICS -----------------------
REQUESTS_TOTAL = Counter(
    "traffic_requests_total",
    "Total requests generated",
    ["service", "endpoint", "status"]
)

ERRORS_TOTAL = Counter(
    "traffic_errors_total",
    "Total errors generated",
    ["service", "endpoint"]
)

SCENARIO_DURATION = Histogram(
    "traffic_scenario_duration_seconds",
    "Duration of one scenario run"
)

ACTIVE_USERS = Gauge("traffic_active_users", "Active generated users")
ACTIVE_THREADS = Gauge("traffic_active_threads", "Active threads")


# --------------------- STATE -----------------------
# user storage: (username, password, token)
users = []

test_running = False
stop_time = None


def rand_str(n=6):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


# --------------------- SCENARIOS -----------------------

def scenario_register():
    """Register user and immediately log them in."""
    username = f"user_{rand_str()}"
    password = "test123"

    try:
        r = requests.post(
            f"{AUTH_URL}/register",
            json={"username": username, "password": password}
        )

        REQUESTS_TOTAL.labels("auth", "register", r.status_code).inc()

        if r.status_code != 200:
            return

        # Now LOGIN this user immediately
        token = scenario_login_user(username, password)
        if token:
            users.append((username, password, token))
            ACTIVE_USERS.set(len(users))

    except Exception:
        ERRORS_TOTAL.labels("auth", "register").inc()


def scenario_login_user(username, password):
    """Login specific user, return token or None."""
    try:
        r = requests.post(
            f"{AUTH_URL}/login",
            json={"username": username, "password": password}
        )

        REQUESTS_TOTAL.labels("auth", "login", r.status_code).inc()

        if r.status_code == 200:
            return r.json().get("access_token", None)

    except Exception:
        ERRORS_TOTAL.labels("auth", "login").inc()

    return None


def scenario_login():
    """Login random user, update stored token."""
    if not users:
        return scenario_register()

    idx = random.randrange(len(users))
    username, password, _ = users[idx]

    token = scenario_login_user(username, password)
    if token:
        users[idx] = (username, password, token)


def scenario_db_insert():
    if not users:
        return

    username, password, token = random.choice(users)

    try:
        r = requests.post(
            f"{DB_APP_URL}/insert",
            json={"name": rand_str(), "value": random.randint(1, 100)},
            headers={"Authorization": f"Bearer {token}"}
        )

        REQUESTS_TOTAL.labels("db_app", "insert", r.status_code).inc()

    except Exception:
        ERRORS_TOTAL.labels("db_app", "insert").inc()


def scenario_db_read():
    if not users:
        return

    _, _, token = random.choice(users)

    try:
        r = requests.get(
            f"{DB_APP_URL}/items",
            headers={"Authorization": f"Bearer {token}"}
        )

        REQUESTS_TOTAL.labels("db_app", "read", r.status_code).inc()

    except Exception:
        ERRORS_TOTAL.labels("db_app", "read").inc()


def scenario_rabbit():
    try:
        conn = pika.BlockingConnection(pika.ConnectionParameters(RABBIT_HOST))
        channel = conn.channel()
        channel.queue_declare(queue="events")
        channel.basic_publish(exchange="", routing_key="events", body="hello")
        conn.close()

        REQUESTS_TOTAL.labels("rabbitmq", "publish", 200).inc()

    except Exception:
        ERRORS_TOTAL.labels("rabbitmq", "publish").inc()


# Scenario weights
SCENARIOS = [
    (scenario_login, 0.50),
    (scenario_register, 0.10),
    (scenario_db_read, 0.20),
    (scenario_db_insert, 0.15),
    (scenario_rabbit, 0.05),
]


def pick_scenario():
    r = random.random()
    acc = 0
    for scen, w in SCENARIOS:
        acc += w
        if r <= acc:
            return scen
    return scenario_login


# ------------------ THREAD WORKER ------------------

def worker():
    global stop_time

    while datetime.utcnow() < stop_time:
        scen = pick_scenario()

        start = time.time()
        scen()
        SCENARIO_DURATION.observe(time.time() - start)

        time.sleep(0.2)

    ACTIVE_THREADS.dec()


# ----------------------- API -----------------------

app = FastAPI(title="Traffic Simulator")


class TestParams(BaseModel):
    duration: int
    users: int
    threads: int


@app.post("/run_test")
def run_test(params: TestParams):
    global stop_time, test_running, users

    if test_running:
        return {"error": "Test already running"}

    test_running = True
    stop_time = datetime.utcnow() + timedelta(seconds=params.duration)

    # reset user list for each test
    users = []

    # PRELOAD users
    for _ in range(params.users):
        scenario_register()

    ACTIVE_USERS.set(len(users))

    # START THREADS
    for _ in range(params.threads):
        ACTIVE_THREADS.inc()
        threading.Thread(target=worker, daemon=True).start()

    return {
        "status": "running",
        "duration": params.duration,
        "threads": params.threads,
        "users": len(users)
    }


@app.get("/status")
def status():
    return {"running": test_running, "stop_time": stop_time}


if __name__ == "__main__":
    start_http_server(8010, addr="0.0.0.0")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
