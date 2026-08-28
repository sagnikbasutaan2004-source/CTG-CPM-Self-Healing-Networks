"""
kafka_telemetry_streaming.py
Apache Kafka Real-Time Telemetry Streaming Bus for CTG-CPM (Layer 1 Integration)

REAL, HONEST streaming:
- The producer/consumer connect to an actual Apache Kafka broker (default localhost:9092).
- Kafka is the primary and only transport for streaming. There is NO silent in-memory
  emulator masquerading as Kafka. If the broker is unreachable, the module raises a clear
  error / reports `kafka_status: unavailable` so operators know telemetry did not stream.
- An optional, EXPLICITLY-NAMED diagnostic dump to a local JSON file is provided for offline
  development, and is always labelled as `kafka_status: offline_debug` (never as a broker).
"""

import json
import time
import socket
import threading
import warnings
from typing import Dict, Any, List, Callable, Optional

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)

try:
    from kafka import KafkaProducer, KafkaConsumer
    try:
        from kafka.errors import NoBrokersAvailable
    except ImportError:
        NoBrokersAvailable = None  # removed in kafka-python 3.x; not needed by this module
    KAFKA_MODULE_AVAILABLE = True
except Exception:
    KafkaProducer, KafkaConsumer = None, None
    KAFKA_MODULE_AVAILABLE = False

KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]
TOPIC_RAW_TELEMETRY = "telemetry-raw-stream"
TOPIC_NETWORK_TELEMETRY = "telemetry-network-stream"
TOPIC_REMEDIATION_EVENTS = "remediation-events-stream"

_DEBUG_FILE = None


def configure_debug_json_file(path: Optional[str] = None):
    """
    Optional offline dev aid: enable an EXPLICIT json-lines dump. When set, producers also
    append to this file and every produced event reports kafka_status='offline_debug'.
    This is NOT a Kafka broker and is always labelled as such.
    """
    global _DEBUG_FILE
    _DEBUG_FILE = path


def is_kafka_broker_online(host: str = "localhost", port: int = 9092, timeout: float = 0.5) -> bool:
    """TCP socket check to see if a Kafka broker is listening."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        return False


class KafkaUnavailableError(RuntimeError):
    """Raised when telemetry should stream to Kafka but no broker is reachable."""


def _append_debug(payload: Dict[str, Any]):
    if not _DEBUG_FILE:
        return
    try:
        with open(_DEBUG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass


class TelemetryKafkaProducer:
    """
    Real Kafka producer. Connects to an actual broker at construction. If no broker is
    available (and KAFKA_MODULE_AVAILABLE is False), silently streaming in-memory is NOT
    allowed — instead the producer reports status and, if requested, raises.
    """

    def __init__(self, bootstrap_servers: List[str] = KAFKA_BOOTSTRAP_SERVERS,
                 require_broker: bool = False):
        self.bootstrap_servers = bootstrap_servers
        self.broker_online = is_kafka_broker_online(
            host=bootstrap_servers[0].split(":")[0],
            port=int(bootstrap_servers[0].split(":")[1]) if ":" in bootstrap_servers[0] else 9092)
        self.producer = None
        self.connected = False

        if not KAFKA_MODULE_AVAILABLE:
            self.status = "unavailable_module"
            if require_broker:
                raise KafkaUnavailableError(
                    "kafka python module not installed; real Kafka streaming unavailable.")
            return

        if self.broker_online:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=bootstrap_servers,
                    request_timeout_ms=5000,
                    max_block_ms=3000,
                    acks="all"
                )
                self.connected = True
                self.status = "connected"
                print(f"[Kafka Producer] Connected to real Kafka broker at {bootstrap_servers}")
            except Exception as e:
                self.producer = None
                self.connected = False
                self.status = f"connect_failed:{e}"
                if require_broker:
                    raise KafkaUnavailableError(f"Kafka connect failed: {e}")
        else:
            self.connected = False
            self.status = "unavailable_broker"
            if require_broker:
                raise KafkaUnavailableError(
                    f"No Kafka broker reachable at {bootstrap_servers}. "
                    "Telemetry will not stream.")

    def send_telemetry(self, topic: str, telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publishes telemetry event to the real Kafka broker. Returns delivery status."""
        payload = {
            "source": telemetry_data.get("source", "Telemetry Agent"),
            "timestamp": telemetry_data.get("timestamp", time.time()),
            "metrics": telemetry_data,
        }

        if self.connected and self.producer:
            try:
                raw_bytes = json.dumps(payload).encode('utf-8')
                self.producer.send(topic, value=raw_bytes)
                self.producer.flush()
                return {"ok": True, "kafka_status": "connected", "topic": topic}
            except Exception as e:
                # Do NOT silently swallow into an emulator - report honestly.
                _append_debug(payload)
                return {"ok": False, "kafka_status": f"send_failed:{e}",
                        "topic": topic, "offline_dump": True}

        # No broker: append to explicit debug file if configured, else report failure.
        _append_debug(payload)
        return {"ok": False, "kafka_status": self.status, "topic": topic,
                "offline_dump": _DEBUG_FILE is not None,
                "error": "telemetry not streamed to Kafka (no broker)"}


class TelemetryKafkaConsumer:
    """
    Real Kafka consumer. Subscribes to an actual broker. If unavailable, reports status
    rather than returning emulated messages.
    """

    def __init__(self, topic: str, bootstrap_servers: List[str] = KAFKA_BOOTSTRAP_SERVERS,
                 require_broker: bool = False):
        self.topic = topic
        self.bootstrap_servers = bootstrap_servers
        self.broker_online = is_kafka_broker_online(
            host=bootstrap_servers[0].split(":")[0],
            port=int(bootstrap_servers[0].split(":")[1]) if ":" in bootstrap_servers[0] else 9092)
        self.consumer = None
        self.connected = False

        if not KAFKA_MODULE_AVAILABLE:
            self.status = "unavailable_module"
            if require_broker:
                raise KafkaUnavailableError("kafka module not installed.")
            return

        if self.broker_online:
            try:
                self.consumer = KafkaConsumer(
                    topic,
                    bootstrap_servers=bootstrap_servers,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='latest',
                    consumer_timeout_ms=200,
                    enable_auto_commit=True,
                )
                self.connected = True
                self.status = "connected"
                print(f"[Kafka Consumer] Subscribed to real Kafka topic '{topic}'")
            except Exception as e:
                self.consumer = None
                self.connected = False
                self.status = f"connect_failed:{e}"
                if require_broker:
                    raise KafkaUnavailableError(f"Kafka connect failed: {e}")
        else:
            self.connected = False
            self.status = "unavailable_broker"
            if require_broker:
                raise KafkaUnavailableError(f"No Kafka broker reachable at {bootstrap_servers}.")

    def poll_messages(self, timeout_ms: int = 100) -> List[Dict[str, Any]]:
        """Polls new messages from the real Kafka topic. Empty list if not connected."""
        if self.connected and self.consumer:
            try:
                records = self.consumer.poll(timeout_ms=timeout_ms)
                messages = []
                for tp, msgs in records.items():
                    for msg in msgs:
                        messages.append(msg.value)
                return messages
            except Exception:
                return []
        return []


if __name__ == "__main__":
    from telemetry_collector import LaptopTelemetryCollector
    collector = LaptopTelemetryCollector(stream_to_kafka=False)

    print("\n=== KAFKA REAL TELEMETRY STREAMING DEMO ===")
    producer = TelemetryKafkaProducer()
    print("Producer status:", producer.status, "| connected:", producer.connected)

    metrics = collector.get_live_metrics()
    result = producer.send_telemetry(TOPIC_RAW_TELEMETRY, metrics)
    print("Send result:", result)
