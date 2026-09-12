#!/usr/bin/env python3
"""
main.py - IoT Sensor Packet Reliability Monitor Using CRC32 (Phase 2)

This script demonstrates an end-to-end IoT transmission reliability pipeline:
1. Simulates an environmental sensor node (ESP32 with BME280) collecting
   temperature, humidity, and barometric pressure readings.
2. Canonical JSON serialization of sensor payloads.
3. 32-bit Cyclic Redundancy Check (CRC32) calculation before packet transmission.
4. Transmission over a simulated noisy wireless channel with configurable
   corruption probability (default 30%).
5. Receiver-side verification: recalculates CRC32 on incoming payloads, compares
   it with the transmitted CRC32, and flags corrupted packets.
6. Sensor field-level error attribution (tracks temperature, humidity, pressure errors).
7. Comprehensive reliability statistics and terminal dashboard visualization.
"""

import sys
import time
from typing import Optional

# Import simulator and monitor components
from simulator.device import SensorDevice, SensorPacket
from monitor.verifier import PacketVerifier
from dashboard.app import render_banner, render_packet_row, render_summary_card
from api.routes import get_api_status, format_metrics_response


def run_reliability_simulation(
    total_packets: int = 25,
    corruption_probability: float = 0.30,
    device_id: str = "esp32-bme280-node01",
    interval_seconds: float = 0.05
) -> int:
    """
    Run the Phase 2 IoT packet reliability monitoring simulation.
    
    Args:
        total_packets: Number of packets to stream (minimum 20 required).
        corruption_probability: Float (0.0 to 1.0) probability of channel noise.
        device_id: Identifier for the simulated IoT sensor node.
        interval_seconds: Delay between packet transmissions.
        
    Returns:
        0 on successful completion.
    """
    # 1. Display dashboard banner
    render_banner()
    
    # 2. Check and log API service readiness
    api_info = get_api_status()
    print(f"[*] API Service Initialized: {api_info['service']} (Phase {api_info['phase']})")
    print(f"[*] Active Capabilities    : {', '.join(api_info['supported_features'])}\n")
    
    # 3. Configure the IoT sensor node and the gateway packet verifier
    print(f"[*] Initializing IoT Sensor Node: '{device_id}'")
    print(f"[*] Configured Packet Count    : {total_packets} packets")
    print(f"[*] Channel Noise Probability  : {corruption_probability * 100:.1f}%")
    print(f"[*] Transmission Interval      : {interval_seconds}s per packet\n")
    
    sensor = SensorDevice(
        device_id=device_id,
        transmission_interval=interval_seconds,
        default_corrupt_probability=corruption_probability
    )
    verifier = PacketVerifier()
    
    print("-" * 88)
    print("  LIVE TRANSMISSION & VERIFICATION LOG:")
    print("-" * 88)
    
    # 4. Stream and verify the configured number of sensor packets
    for _ in range(total_packets):
        # Generate packet: includes readings, canonical serialization, and original CRC32.
        # If noise is triggered, packet carries the corrupted payload and tags the corrupted field,
        # while keeping the original uncorrupted packet metadata.
        packet: SensorPacket = sensor.create_packet(corrupt_probability=corruption_probability)
        
        # Verify packet integrity on the receiver side
        result = verifier.verify_packet(packet)
        
        # Render packet details: Seq #, Node ID, Readings, VALID/CORRUPT status,
        # Original CRC32, Received CRC32, Calculated CRC32, and Noise info.
        render_packet_row(result)
        
        # Pause briefly to simulate real-world transmission intervals
        time.sleep(interval_seconds)

    # 5. Display comprehensive reliability statistics and field-level error breakdown
    stats = verifier.get_stats()
    render_summary_card(stats)
    
    # 6. Verify and output API JSON payload representation
    api_payload = format_metrics_response(verifier)
    print("[*] API Metrics Response Export:")
    print(f"    {api_payload}\n")
    
    print("✅ Phase 2 execution completed successfully!")
    return 0


def main() -> int:
    """
    Main entry point for Phase 2 execution.
    Configured to run 25 packets (>= 20) with a 30% default corruption probability.
    """
    # Configuration parameters
    TOTAL_PACKETS = 25              # Runs at least 20 packets as requested
    CORRUPTION_PROBABILITY = 0.30   # 30% default channel noise probability
    NODE_ID = "esp32-bme280-node01" # Configurable sensor node identifier
    INTERVAL_SECONDS = 0.04         # Transmission cadence
    
    try:
        return run_reliability_simulation(
            total_packets=TOTAL_PACKETS,
            corruption_probability=CORRUPTION_PROBABILITY,
            device_id=NODE_ID,
            interval_seconds=INTERVAL_SECONDS
        )
    except Exception as err:
        print(f"❌ Execution failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
