"""
app.py - Dashboard for Visualizing Packet Reliability (Phase 2).

Provides:
1. Formatted terminal logging of sensor telemetry, CRC32 verification, and noise status.
2. Comprehensive summary card displaying overall reliability, corruption rate,
   and error frequency breakdown by sensor field.
"""

from typing import List, Optional
from monitor.verifier import VerificationResult, ReliabilityStats


def render_banner() -> None:
    """Print the ASCII banner for the IoT Reliability Monitor."""
    banner = """
========================================================================================
    📡  IoT SENSOR PACKET RELIABILITY MONITOR (CRC32) - PHASE 2
========================================================================================
  Monitors transmission integrity, detects noise corruption using CRC32,
  tracks field-level error attribution (temperature, humidity, pressure),
  and computes real-time packet reliability & corruption percentages.
========================================================================================
"""
    print(banner)


def render_packet_row(result: VerificationResult) -> None:
    """
    Print a formatted log line for a single packet verification.
    
    Displays:
    - Sequence number
    - Sensor node ID
    - Sensor readings (temperature, humidity, pressure)
    - Original CRC32
    - Received CRC32
    - Calculated CRC32
    - VALID or CORRUPT status
    - Noise injection flag and affected field
    
    Args:
        result: The VerificationResult for the packet.
    """
    if result.is_valid:
        status_tag = "\033[92m[ VALID ]\033[0m"  # Green
        noise_info = "Noise: None"
    else:
        status_tag = "\033[91m[CORRUPT]\033[0m"  # Red
        field_tag = f"({result.corrupted_field})" if result.corrupted_field else ""
        noise_info = f"\033[93mNoise: INJECTED {field_tag}\033[0m"

    # Format sensor readings cleanly
    if result.readings:
        t = result.readings.get("temperature_c", 0.0)
        h = result.readings.get("humidity_percent", 0.0)
        p = result.readings.get("pressure_hpa", 0.0)
        readings_str = f"T:{t:5.1f}°C H:{h:4.1f}% P:{p:6.1f}hPa"
    else:
        readings_str = "Readings: [corrupted payload]"

    crc_info = f"Orig:{result.original_crc} | Rx:{result.received_crc} | Calc:{result.computed_crc}"

    print(
        f"  Seq #{result.seq_num:03d} | Node: {result.device_id:<14} | "
        f"{readings_str} | {status_tag} | {crc_info} | {noise_info}"
    )


def render_summary_card(stats: ReliabilityStats) -> None:
    """
    Render a clean summary card with the cumulative packet reliability metrics.
    
    Args:
        stats: Current ReliabilityStats instance.
    """
    bar_length = 30
    valid_fraction = (stats.total_valid / stats.total_received) if stats.total_received > 0 else 1.0
    filled = int(round(bar_length * valid_fraction))
    progress_bar = "█" * filled + "░" * (bar_length - filled)

    print("\n" + "=" * 88)
    print("                          RELIABILITY METRICS SUMMARY                           ")
    print("=" * 88)
    print(f"  • Total Packets Transmitted : {stats.total_received}")
    print(f"  • Valid Packets (Clean)     : {stats.total_valid}")
    print(f"  • Corrupted Packets (Noise) : {stats.total_corrupted}")
    print(f"  • Packet Reliability Rate   : {stats.reliability_percentage:.2f}%")
    print(f"  • Packet Corruption Rate    : {stats.corruption_percentage:.2f}%")
    print("-" * 88)
    print("  📊 ERROR BREAKDOWN BY SENSOR FIELD:")
    print(f"     - Temperature Errors     : {stats.temperature_errors}")
    print(f"     - Humidity Errors        : {stats.humidity_errors}")
    print(f"     - Pressure Errors        : {stats.pressure_errors}")
    print("-" * 88)
    print(f"  • Channel Health Visualizer : [{progress_bar}] {stats.reliability_percentage:.1f}%")
    print("=" * 88 + "\n")
