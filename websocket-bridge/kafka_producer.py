from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KafkaProducer")

# Create Kafka Producer with batching & retries
producer = KafkaProducer(
    bootstrap_servers="kafka:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    linger_ms=10,         # Small delay to batch messages
    retries=3,            # Retry 3 times if broker unavailable
    acks=1              # Wait for leader ack
)

def send_to_kafka(topic: str, data: dict):
    """Send data to Kafka with error handling."""
    future = producer.send(topic, value=data)

    # Optional: Add a callback for delivery confirmation
    future.add_callback(on_send_success, topic=topic)
    future.add_errback(on_send_error, topic=topic)

def on_send_success(record_metadata, topic):
    logger.info(
        f"✅ Message delivered to {topic} partition {record_metadata.partition} offset {record_metadata.offset}"
    )

def on_send_error(excp, topic):
    logger.error(f"❌ Failed to deliver message to {topic}: {excp}")

def close_producer():
    """Gracefully close producer on shutdown."""
    producer.flush()
    producer.close()
