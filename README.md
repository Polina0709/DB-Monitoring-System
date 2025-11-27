# DB Monitoring System (PostgreSQL + Prometheus + Grafana + FastAPI + RabbitMQ)

Full-stack система моніторингу, логування та навантажувального тестування мікросервісної інфраструктури.
Включає: **Auth Service, DB App, PostgreSQL, RabbitMQ, Consumer, Prometheus, Grafana, Traffic Simulator**.

## Технології

| Компонент | Опис |
|----------|------|
| **PostgreSQL (Docker)** | Зберігання даних |
| **FastAPI** | API + логіка внесення даних |
| **SQLAlchemy** | ORM для взаємодії з БД |
| **Prometheus** | Збір метрик |
| **Grafana** | Візуалізація |
| **RabbitMQ** | Обмін повідомленнями між сервісами |
| **JWT авторизація** | Доступ до API для зареєстрованих користувачів |
| **Docker Compose** | Запуск усіх сервісів |

## Архітектура
```
┌──────────────────────────────────────────────────────────┐
│                        Grafana (3000)                    │
│                   └── System Dashboard                   │
│                               ↑                          │
│                        Prometheus (9090)                 │
│       ┌───────────────────────┼────────────────────────┐ │
│       │                       │                        │ │
│ traffic_simulator:8011   auth:7100         postgres_exporter:9187
│      ↑ (load tests)          ↑ (register/login)           ↑ (DB metrics)
│                         DB App (8000)                     │
│                             ↑                             │
│                        PostgreSQL (55432)                 │
│                             ↑                             │
│                       RabbitMQ (5672/15672)               │
│                             ↑                             │
│                       Consumer service                    │
└───────────────────────────────────────────────────────────┘
```

## Структура проєкту
```
db-monitoring-system/
│
├── auth/
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt 
│
├── consumer/
│   ├── main.py
│   └── requirements.txt
│
├── db_app/
│   ├── __init__.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── requirements.txt
│
├── grafana/
│   ├── provisioning/
│   │   ├── dashboards/
│   │   │   ├── dashboards.yml
│   │   │   └── system_overview.json
│   │   └── datasources/
│   │       └── datasource.yml
│
├── prometheus/
│   └── prometheus.yml
│
├── traffic_simulator/
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   ├── .env
│   └── .gitignore
│
├── .gitignore
├── docker-compose.yml
└── README.md
```

## Використані технології

| Компонент                  | Технологія                     |
| -------------------------- | ------------------------------ |
| API сервіси                | FastAPI                        |
| Бази даних                 | PostgreSQL + SQLite (для auth) |
| ORM                        | SQLAlchemy                     |
| Моніторинг                 | Prometheus                     |
| Dashboards                 | Grafana                        |
| Брокер повідомлень         | RabbitMQ                       |
| Навантажувальне тестування | Custom Traffic Simulator       |
| Авторизація                | JWT                            |
| Контейнеризація            | Docker + Docker Compose        |

## Запуск

### 1. Клонувати репозиторій
```bash
git clone https://github.com/yourusername/db-monitoring-system.git
cd db-monitoring-system
```
### 2. Створити .env
```bash
POSTGRES_USER=pguser
POSTGRES_PASSWORD=pgpass
POSTGRES_DB=pgdb

JWT_SECRET=supersecretkey
JWT_ALGO=HS256

GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```
### 3. Запустити весь стек
```bash
docker compose up -d --build
```
### 4. Перевірити статус контейнерів
```bash
docker ps --format "table {{.Names}}\t{{.Ports}}"
```
### 5. Зупинити стек
```bash
docker compose down
```

### Порти сервісів

| Сервіс                        | Порт                | Опис                            |
| ----------------------------- | ------------------- | ------------------------------- |
| **Grafana**                   | **3000**            | Панель моніторингу              |
| **Prometheus**                | **9090**            | Метрики всіх сервісів           |
| **Auth Service**              | **7100 → 7000**     | API реєстрації/логіну + метрики |
| **DB App**                    | **8000**            | Метрики + робота з PostgreSQL   |
| **PostgreSQL**                | **55432 → 5432**    | СУБД                            |
| **Postgres Exporter**         | **9187**            | Метрики PostgreSQL              |
| **RabbitMQ**                  | **5672**, **15672** | Broker + UI                     |
| **Traffic Simulator API**     | **8010**            | API запуску тестів              |
| **Traffic Simulator Metrics** | **8011**            | Метрики навантаження            |
| **Consumer**                  | internal            | читає RabbitMQ                  |

### Основні Endpoints

#### - Auth Service (http://localhost:7100)
| Endpoint           | Опис                |
| ------------------ | ------------------- |
| **POST /register** | Реєстрація          |
| **POST /login**    | Логін               |
| **GET /metrics**   | Метрики авторизації |

#### - DB App (http://localhost:8000)
| Endpoint         | Опис                                            |
| ---------------- | ----------------------------------------------- |
| **GET /health**  | Перевірка статусу                               |
| **GET /count**   | Підрахунок записів у БД (потрібен Bearer Token) |
| **GET /metrics** | Метрики генератора + RabbitMQ + DB              |

#### - Traffic Simulator (http://localhost:8010)
| Endpoint           | Опис                         |
| ------------------ | ---------------------------- |
| **POST /run_test** | Запуск сценарію навантаження |
| **GET /status**    | Статус поточного тесту       |
| **GET (on 8011)**  | Метрики симулятора           |

#### - Prometheus
| Endpoint                                                       | Опис          |
| -------------------------------------------------------------- | ------------- |
| [http://localhost:9090](http://localhost:9090)                 | Web UI        |
| [http://localhost:9090/targets](http://localhost:9090/targets) | Стан таргетів |

#### - Grafana
| URL                                            | Опис               |
| ---------------------------------------------- | ------------------ |
| [http://localhost:3000](http://localhost:3000) | Панель моніторингу |

#### - PostgreSQL Exporter
| URL                                                            | Опис               |
| -------------------------------------------------------------- | ------------------ |
| [http://localhost:9187/metrics](http://localhost:9187/metrics) | Метрики PostgreSQL |

### Конфігурація Prometheus

```
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: "db_app"
    static_configs:
      - targets: ["db_app:8000"]

  - job_name: "postgres"
    static_configs:
      - targets: ["postgres_exporter:9187"]

  - job_name: "auth"
    static_configs:
      - targets: ["auth:7000"]

  - job_name: "consumer"
    static_configs:
      - targets: ["consumer:9100"]

  - job_name: "rabbitmq"
    static_configs:
      - targets: ["rabbitmq_exporter:9419"]

  - job_name: "traffic_simulator"
    static_configs:
      - targets: [ "traffic_simulator:8010" ]

```

### Grafana Dashboard

**Dashboard** розташований у:
```bash
grafana/provisioning/dashboards/system_overview.json
```
#### Автопідхоплення включає:
- Successful Logins
- Registered Users
- Postgres Active Connections
- Generator CPU Usage
- Operation Duration
- Login Attempt Rate
- Traffic Simulator Load
- RabbitMQ publish rate

Оновлення графіків: **кожні 5 секунд**.

### Traffic Simulator

#### Traffic Simulator доступний за:

```bash
http://localhost:8010
```

#### Запуск навантаження

```bash
curl -X POST http://localhost:8010/run_test \
  -H "Content-Type: application/json" \
  -d '{"duration": 20, "users": 50, "threads": 10}'
  ```

#### Перевірити статус

```bash
curl http://localhost:8010/status
```

#### Метрики навантаження

```bash
curl http://localhost:8011
```

#### Simulator виконує:
- створення користувачів через /register
- масові логіни через /login
- читання/запис даних у DB App
- надсилання повідомлень у RabbitMQ
- оновлення графіків Grafana

### Screenshots
![Screenshot 2025-11-27 at 23.58.56.png](../Screenshot%202025-11-27%20at%2023.58.56.png)
![Screenshot 2025-11-27 at 23.59.04.png](../Screenshot%202025-11-27%20at%2023.59.04.png)

![Screenshot 2025-11-27 at 23.58.42.png](../Screenshot%202025-11-27%20at%2023.58.42.png)
![Screenshot 2025-11-27 at 23.58.49.png](../Screenshot%202025-11-27%20at%2023.58.49.png)

### Виконані вимоги

| Вимога                                    | Статус         |
| ----------------------------------------- | -------------- |
| PostgreSQL у Docker                       | ✅              |
| Python сервіс працює з БД                 | ✅              |
| Prometheus збирає метрики з усіх сервісів | ✅              |
| Метрики збережені у Time Series Storage   | ✅              |
| Grafana відображає дашборд                | ✅ (автодеплой) |
| Авторизація через окремий Auth Service    | ✅              |
| Контейнеризація всіх сервісів             | ✅              |
| RabbitMQ як брокер повідомлень            | ✅              |
| Traffic Simulator генерує навантаження    | ✅              |
| Повний автозапуск у docker-compose        | ✅              |


