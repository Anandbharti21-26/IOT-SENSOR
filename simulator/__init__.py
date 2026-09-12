"""
Simulator package for IoT Sensor Packet Reliability Monitor.
Responsible for simulating IoT sensor hardware, telemetry generation,
and channel noise/packet corruption.
"""

from .device import SensorDevice, SensorPacket, calculate_crc32, serialize_payload

__all__ = ["SensorDevice", "SensorPacket", "calculate_crc32", "serialize_payload"]
