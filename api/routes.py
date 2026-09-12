"""
routes.py - API Endpoints for the Packet Reliability Monitor (Phase 2).

Provides helper endpoints and JSON response formatting for:
1. Receiving packets from remote IoT nodes.
2. Querying comprehensive reliability metrics and field-level error breakdowns.
3. Health check for the monitoring service.
"""

from typing import Dict, Any
from monitor.verifier import PacketVerifier


def get_api_status() -> Dict[str, Any]:
    """
    Return basic status and health information about the API service.
    """
    return {
        "service": "IoT Sensor Packet Reliability Monitor API",
        "status": "online",
        "phase": 2,
        "supported_features": [
            "CRC32 checksum verification",
            "Deterministic payload serialization",
            "Multi-sensor telemetry (temperature, humidity, pressure)",
            "Field-level error breakdown tracking",
            "Real-time packet reliability & corruption rates"
        ]
    }


def format_metrics_response(verifier: PacketVerifier) -> Dict[str, Any]:
    """
    Helper function to format reliability metrics into an API-ready JSON response.
    
    Args:
        verifier: An instance of PacketVerifier.

    Returns:
        Dictionary formatted for JSON response.
    """
    stats = verifier.get_stats()
    return {
        "status": "success",
        "metrics": {
            "total_packets_received": stats.total_received,
            "valid_packets": stats.total_valid,
            "corrupted_packets": stats.total_corrupted,
            "reliability_percentage": f"{stats.reliability_percentage:.2f}%",
            "corruption_percentage": f"{stats.corruption_percentage:.2f}%",
            "sensor_field_errors": {
                "temperature_errors": stats.temperature_errors,
                "humidity_errors": stats.humidity_errors,
                "pressure_errors": stats.pressure_errors,
            }
        }
    }
