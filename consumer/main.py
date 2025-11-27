import time
import pika
from prometheus_client import Counter, start_http_server

MESSAGES_CONSUMED = Counter(
    "consumer_messages_total",
    "Messages consumed from RabbitMQ"
)

RABBIT_HOST = "rabbitmq"
QUEUE_NAME = "measurements"


def connect_with_retry():
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBIT_HOST)
            )
            print("[CONSUMER] Connected to RabbitMQ")
            return connection
        except Exception as e:
            print(f"[CONSUMER] RabbitMQ not ready, retrying in 3 seconds... Error: {e}")
            time.sleep(3)


def callback(ch, method, properties, body):
    """Обробка повідомлення з черги."""
    MESSAGES_CONSUMED.inc()
    print(f"[CONSUMER] Received: {body.decode()}")


def main():
    print("[CONSUMER] Starting Prometheus metrics server on port 9100...")
    start_http_server(9100)

    while True:
        connection = connect_with_retry()
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME)

        print("[CONSUMER] Waiting for messages...")
        try:
            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=callback,
                auto_ack=True
            )
            channel.start_consuming()
        except Exception as e:
            print(f"[CONSUMER] Lost connection, reconnecting... Error: {e}")
            time.sleep(3)
            continue


if __name__ == "__main__":
    main()
