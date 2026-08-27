"""
telemetry_collector.py
Real-time Laptop Host Telemetry & Synthetic Network Telemetry Collector for CTG-CPM
"""

import time
import math
import random
import psutil
from typing import Dict, Any, List

class LaptopTelemetryCollector:
    """
    Ingests live laptop / desktop performance metrics using psutil:
    - CPU utilization, per-core loads, frequencies
    - Memory usage, swap rate
    - Disk I/O rates
    - Top process thermal/CPU contributions
    """

    def __init__(self):
        self.last_disk_io = psutil.disk_io_counters()
        self.last_time = time.time()

    def get_live_metrics(self) -> Dict[str, Any]:
        current_time = time.time()
        time_delta = max(current_time - self.last_time, 0.001)
        self.last_time = current_time

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_per_core = psutil.cpu_percent(percpu=True)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = round(cpu_freq.current, 1) if cpu_freq else 0.0

        # Memory metrics
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Disk I/O rate
        disk_io = psutil.disk_io_counters()
        read_rate_kb = 0.0
        write_rate_kb = 0.0
        if disk_io and self.last_disk_io:
            read_rate_kb = round((disk_io.read_bytes - self.last_disk_io.read_bytes) / (1024 * time_delta), 2)
            write_rate_kb = round((disk_io.write_bytes - self.last_disk_io.write_bytes) / (1024 * time_delta), 2)
            self.last_disk_io = disk_io

        # Battery / Thermals if available
        battery = psutil.sensors_battery()
        battery_percent = round(battery.percent, 1) if battery else 100.0

        # Top processes by CPU
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

        return {
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
            "top_processes": processes
        }


class SyntheticTelemetryGenerator:
    """
    Generates synthetic multivariate telemetry for network nodes (OSNR, laser bias, thermal stress)
    or simulated laptop stress scenarios for CTG-CPM baseline testing.
    """

    def __init__(self):
        self.step_counter = 0

    def generate_network_telemetry(self, inject_anomaly: bool = False) -> Dict[str, Any]:
        """
        Generates simulated 5G Optical Transceiver / Backhaul link telemetry.
        """
        self.step_counter += 1
        t = self.step_counter * 0.1

        # Baseline metrics with sine waves + random noise
        base_osnr = 22.4 + math.sin(t * 0.5) * 0.5 + random.uniform(-0.1, 0.1)
        base_laser_bias = 45.0 + math.cos(t * 0.3) * 1.0 + random.uniform(-0.2, 0.2)
        base_temp = 52.0 + math.sin(t * 0.2) * 2.0 + random.uniform(-0.3, 0.3)
        base_packet_loss = 0.01 + random.uniform(0.0, 0.02)
        base_throughput_gbps = 9.4 + math.sin(t * 0.1) * 0.3

        if inject_anomaly:
            # Simulate micro-fluctuation degradation in OSNR & Laser Bias spikes
            base_osnr -= random.uniform(3.5, 6.0) # Degrades OSNR below 18dB threshold
            base_laser_bias += random.uniform(15.0, 25.0) # Laser bias overheating
            base_temp += random.uniform(18.0, 25.0) # Thermal spike
            base_packet_loss += random.uniform(2.5, 5.0)

        return {
            "timestamp": time.time(),
            "source": "5G Backhaul Optical Transceiver (Simulated)",
            "osnr_db": round(max(0.0, base_osnr), 2),
            "laser_bias_ma": round(base_laser_bias, 2),
            "temperature_celsius": round(base_temp, 2),
            "packet_loss_percent": round(base_packet_loss, 3),
            "throughput_gbps": round(base_throughput_gbps, 2),
            "anomaly_flag": inject_anomaly or (base_osnr < 18.0 or base_temp > 70.0)
        }

if __name__ == "__main__":
    collector = LaptopTelemetryCollector()
    syn = SyntheticTelemetryGenerator()
    
    print("=== LIVE LAPTOP TELEMETRY SAMPLE ===")
    print(collector.get_live_metrics())

    print("\n=== SYNTHETIC NETWORK TELEMETRY SAMPLE ===")
    print(syn.generate_network_telemetry(inject_anomaly=True))
