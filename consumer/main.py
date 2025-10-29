import time
import pika

def connect():
    while True:
        try:
            print("Trying to connect to RabbitMQ...")
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
            print("Connected to RabbitMQ!")
            return connection
        except:
            print("RabbitMQ not ready, retrying in 3 seconds...")
            time.sleep(3)

def main():
    connection = connect()
    channel = connection.channel()
    channel.queue_declare(queue='measurements')

    def callback(ch, method, properties, body):
        value = body.decode()
        print(f"Consumed value {value}")

    channel.basic_consume(queue='measurements', on_message_callback=callback, auto_ack=True)
    print("Waiting for messages...")
    channel.start_consuming()

if __name__ == "__main__":
    main()
