"""
telemetry_collector.py
Real-time Laptop Host Telemetry & Synthetic Network Telemetry Collector for CTG-CPM

Provides raw live metrics and dynamic statistical anomaly thresholds, and streams telemetry
events to a REAL Apache Kafka broker. Kafka status is always reported honestly:
  - kafka_status='connected'   : event delivered to a real broker
  - kafka_status='unavailable' : no broker reachable; event was NOT streamed (no fake emulator)
  - kafka_status='offline_debug': delivered to an explicitly-named local debug file only
"""

import time
import math
import random
import psutil
from typing import Dict, Any, List, Tuple

try:
    from kafka_telemetry_streaming import (
        TelemetryKafkaProducer, TOPIC_RAW_TELEMETRY, TOPIC_NETWORK_TELEMETRY,
        KafkaUnavailableError,
    )
    KAFKA_STREAMING_ENABLED = True
except ImportError:
    KAFKA_STREAMING_ENABLED = False


def _kafka_status_from(result) -> str:
    if isinstance(result, dict):
        return result.get("kafka_status", "unknown")
    return "unavailable"


class LaptopTelemetryCollector:
    """
    Ingests live laptop / desktop performance metrics using psutil:
    - CPU utilization, per-core loads, frequencies
    - Memory usage, swap rate
    - Disk I/O rates
    - Top process thermal/CPU contributions
    Calculates dynamic statistical anomaly score based on moving baseline z-scores.
    Streams telemetry events live to a REAL Apache Kafka topic (reports honestly).
    """

    def __init__(self, stream_to_kafka: bool = True):
        self.last_disk_io = psutil.disk_io_counters()
        self.last_time = time.time()
        self.stream_to_kafka = stream_to_kafka and KAFKA_STREAMING_ENABLED
        self.producer = None
        if self.stream_to_kafka:
            try:
                self.producer = TelemetryKafkaProducer()
            except KafkaUnavailableError:
                self.producer = None

        self.cpu_history: List[float] = []
        self.mem_history: List[float] = []
        self.history_window = 50

    def _update_baseline(self, cpu: float, mem: float):
        self.cpu_history.append(cpu)
        self.mem_history.append(mem)
        if len(self.cpu_history) > self.history_window:
            self.cpu_history.pop(0)
            self.mem_history.pop(0)

    def compute_dynamic_anomaly_flag(self, cpu: float, mem: float) -> Tuple[bool, float]:
        """
        Computes dynamic anomaly score using a statistical Z-score: Z = (X - mu) / sigma
        Combined with an absolute CPU+memory stress threshold.
        """
        self._update_baseline(cpu, mem)

        if len(self.cpu_history) < 5:
            stress_score = (cpu / 100.0) * 0.6 + (mem / 100.0) * 0.4
            return stress_score > 0.80, round(stress_score, 3)

        mean_cpu = sum(self.cpu_history) / len(self.cpu_history)
        var_cpu = sum((x - mean_cpu) ** 2 for x in self.cpu_history) / len(self.cpu_history)
        std_cpu = math.sqrt(var_cpu) if var_cpu > 1e-4 else 5.0

        z_cpu = (cpu - mean_cpu) / std_cpu
        combined_stress = (cpu / 100.0) * 0.5 + (mem / 100.0) * 0.5
        anomaly_flag = z_cpu > 2.2 or combined_stress > 0.82

        return anomaly_flag, round(z_cpu, 3)

    def get_live_metrics(self) -> Dict[str, Any]:
        current_time = time.time()
        time_delta = max(current_time - self.last_time, 0.001)
        self.last_time = current_time

        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_per_core = psutil.cpu_percent(percpu=True)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = round(cpu_freq.current, 1) if cpu_freq else 0.0

        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        disk_io = psutil.disk_io_counters()
        read_rate_kb = 0.0
        write_rate_kb = 0.0
        if disk_io and self.last_disk_io:
            read_rate_kb = round((disk_io.read_bytes - self.last_disk_io.read_bytes) / (1024 * time_delta), 2)
            write_rate_kb = round((disk_io.write_bytes - self.last_disk_io.write_bytes) / (1024 * time_delta), 2)
            self.last_disk_io = disk_io

        battery = psutil.sensors_battery()
        battery_percent = round(battery.percent, 1) if battery else 100.0

        processes = []
        try:
            for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                               key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:3]:
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "cpu_percent": proc.info['cpu_percent'],
                    "memory_percent": round(proc.info['memory_percent'] or 0, 2)
                })
        except Exception:
            pass

        anomaly_flag, z_score = self.compute_dynamic_anomaly_flag(cpu_percent, mem.percent)

        telemetry_dict = {
            "timestamp": time.time(),
            "source": "Live Laptop Host",
            "cpu_overall_percent": cpu_percent,
            "cpu_per_core": cpu_per_core,
            "cpu_frequency_mhz": cpu_freq_current,
            "memory_percent": mem.percent,
            "memory_used_mb": round(mem.used / (1024 * 1024), 1),
            "memory_available_mb": round(mem.available / (1024 * 1024), 1),
            "swap_percent": swap.percent,
            "disk_read_kbps": read_rate_kb,
            "disk_write_kbps": write_rate_kb,
            "battery_percent": battery_percent,
            "top_processes": processes,
            "anomaly_flag": anomaly_flag,
            "dynamic_z_score": z_score,
        }

        # Stream event to REAL Kafka (honest status)
        kafka_status = "disabled"
        if self.producer is not None:
            result = self.producer.send_telemetry(TOPIC_RAW_TELEMETRY, telemetry_dict)
            kafka_status = _kafka_status_from(result)
            if not isinstance(result, dict) or not result.get("ok", True):
                kafka_status = _kafka_status_from(result)
        else:
            kafka_status = "unavailable_no_broker" if (self.stream_to_kafka and KAFKA_STREAMING_ENABLED) else "disabled"

        telemetry_dict["kafka_status"] = kafka_status
        return telemetry_dict


class SyntheticTelemetryGenerator:
    """
    Generates synthetic multivariate telemetry for network nodes (OSNR, laser bias, thermal
    stress) and streams network events live to a REAL Apache Kafka topic (honest status).
    NOTE: The telemetry values are synthetic (simulated transceiver); the Kafka transport is real.
    """

    def __init__(self, stream_to_kafka: bool = True):
        self.step_counter = 0
        self.stream_to_kafka = stream_to_kafka and KAFKA_STREAMING_ENABLED
        self.producer = None
        if self.stream_to_kafka:
            try:
                self.producer = TelemetryKafkaProducer()
            except KafkaUnavailableError:
                self.producer = None

    def compute_dynamic_network_anomaly(self, osnr: float, temp: float, packet_loss: float) -> Tuple[bool, float]:
        osnr_opt, scale_osnr = 22.4, 4.0
        temp_opt, scale_temp = 50.0, 20.0
        scale_loss = 2.0

        d_osnr = max(0.0, (osnr_opt - osnr) / scale_osnr)
        d_temp = max(0.0, (temp - temp_opt) / scale_temp)
        d_loss = packet_loss / scale_loss

        anomaly_index = math.sqrt(d_osnr**2 + d_temp**2 + d_loss**2)
        anomaly_flag = anomaly_index > 0.85
        return anomaly_flag, round(anomaly_index, 3)

    def generate_network_telemetry(self, inject_anomaly: bool = False) -> Dict[str, Any]:
        self.step_counter += 1
        t = self.step_counter * 0.1

        base_osnr = 22.4 + math.sin(t * 0.5) * 0.5 + random.uniform(-0.1, 0.1)
        base_laser_bias = 45.0 + math.cos(t * 0.3) * 1.0 + random.uniform(-0.2, 0.2)
        base_temp = 52.0 + math.sin(t * 0.2) * 2.0 + random.uniform(-0.3, 0.3)
        base_packet_loss = 0.01 + random.uniform(0.0, 0.02)
        base_throughput_gbps = 9.4 + math.sin(t * 0.1) * 0.3

        if inject_anomaly:
            base_osnr -= random.uniform(3.5, 6.0)
            base_laser_bias += random.uniform(15.0, 25.0)
            base_temp += random.uniform(18.0, 25.0)
            base_packet_loss += random.uniform(2.5, 5.0)

        anomaly_flag, anomaly_index = self.compute_dynamic_network_anomaly(base_osnr, base_temp, base_packet_loss)

        telemetry_dict = {
            "timestamp": time.time(),
            "source": "5G Backhaul Optical Transceiver (Simulated)",
            "osnr_db": round(max(0.0, base_osnr), 2),
            "laser_bias_ma": round(base_laser_bias, 2),
            "temperature_celsius": round(base_temp, 2),
            "packet_loss_percent": round(base_packet_loss, 3),
            "throughput_gbps": round(base_throughput_gbps, 2),
            "anomaly_flag": inject_anomaly or anomaly_flag,
            "dynamic_anomaly_index": anomaly_index,
        }

        kafka_status = "disabled"
        if self.producer is not None:
            result = self.producer.send_telemetry(TOPIC_NETWORK_TELEMETRY, telemetry_dict)
            kafka_status = _kafka_status_from(result)
        else:
            kafka_status = "unavailable_no_broker" if (self.stream_to_kafka and KAFKA_STREAMING_ENABLED) else "disabled"

        telemetry_dict["kafka_status"] = kafka_status
        return telemetry_dict


if __name__ == "__main__":
    collector = LaptopTelemetryCollector()
    syn = SyntheticTelemetryGenerator()

    print("=== LIVE LAPTOP TELEMETRY SAMPLE (KAFKA STREAMED) ===")
    print(collector.get_live_metrics())

    print("\n=== SYNTHETIC NETWORK TELEMETRY SAMPLE (KAFKA STREAMED) ===")
    print(syn.generate_network_telemetry(inject_anomaly=True))
