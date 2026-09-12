"""
device.py - IoT Sensor Simulator with CRC32 Checksum Generation (Phase 2).

This module models an IoT sensor device that:
1. Samples environmental data (temperature, humidity, and atmospheric pressure).
2. Formats readings into a standardized data payload with deterministic serialization.
3. Computes a 32-bit Cyclic Redundancy Check (CRC32) over the payload.
4. Simulates transmission noise by deliberately corrupting sensor fields or payload bytes.
5. Preserves both original and corrupted packet metadata for end-to-end monitoring.
"""

import json
import random
import time
import zlib
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List


def serialize_payload(data: Dict[str, Any]) -> str:
    """
    Serialize reading payload deterministically into a JSON string.
    
    Uses sorted keys and uniform separators without superfluous whitespace
    to ensure that identical data always produces the exact same string
    and therefore the exact same CRC32 checksum.
    
    Args:
        data: Dictionary containing packet telemetry and metadata.
        
    Returns:
        Canonical JSON string representation.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def calculate_crc32(payload: str) -> str:
    """
    Calculate the CRC32 checksum of a string payload.

    CRC32 (Cyclic Redundancy Check 32-bit) processes the raw bytes of the
    message and returns an 8-character hexadecimal string representing the checksum.
    
    Args:
        payload: The raw string data to check.

    Returns:
        Hexadecimal string formatted as 8 lowercase hex characters (e.g. '4a2f8b1c').
    """
    # Convert string payload to raw UTF-8 bytes
    data_bytes = payload.encode("utf-8")
    
    # Calculate CRC32 using Python's built-in zlib module
    # & 0xFFFFFFFF ensures an unsigned 32-bit integer across all platforms
    checksum = zlib.crc32(data_bytes) & 0xFFFFFFFF
    
    # Format as an 8-character zero-padded hexadecimal string
    return f"{checksum:08x}"


@dataclass
class SensorPacket:
    """
    Represents an IoT sensor transmission packet.
    
    Attributes:
        device_id: Unique identifier for the sensor node.
        seq_num: Monotonically increasing sequence number to track packets.
        timestamp: Unix epoch timestamp when the reading was taken.
        payload: Serialized reading data string (transmitted payload).
        crc32: 8-character hexadecimal CRC32 checksum computed at transmission.
        is_simulated_corrupt: Flag indicating if channel noise was injected.
        original_crc32: The original CRC32 checksum before any transmission.
        received_crc32: The CRC32 checksum arriving at the receiver.
        original_payload: The clean, uncorrupted payload string.
        corrupted_field: Name of the sensor field corrupted by channel noise (if any).
        readings: Dictionary of sensor readings (temperature, humidity, pressure).
        original_packet: Reference to the uncorrupted packet instance.
    """
    device_id: str
    seq_num: int
    timestamp: float
    payload: str
    crc32: str
    is_simulated_corrupt: bool = False
    original_crc32: Optional[str] = None
    received_crc32: Optional[str] = None
    original_payload: Optional[str] = None
    corrupted_field: Optional[str] = None
    readings: Optional[Dict[str, float]] = None
    original_packet: Optional[Any] = None

    def __post_init__(self):
        """Populate default values for original/received CRC if not explicitly provided."""
        if self.original_crc32 is None:
            self.original_crc32 = self.crc32
        if self.received_crc32 is None:
            self.received_crc32 = self.crc32
        if self.original_payload is None:
            self.original_payload = self.payload

    def to_dict(self) -> Dict[str, Any]:
        """Convert packet to a dictionary representation excluding recursive references."""
        data = asdict(self)
        data.pop("original_packet", None)
        return data


class SensorDevice:
    """
    Simulates a physical IoT environmental sensor node (e.g. BME280 on ESP32).
    Generates realistic temperature, humidity, and atmospheric pressure readings.
    """

    def __init__(
        self,
        device_id: str = "sensor-node-01",
        transmission_interval: float = 1.0,
        default_corrupt_probability: float = 0.30
    ):
        """
        Initialize the sensor device.
        
        Args:
            device_id: Unique identifier for this sensor node.
            transmission_interval: Time in seconds between successive transmissions.
            default_corrupt_probability: Default chance (0.0 to 1.0) of channel corruption.
        """
        self.device_id = device_id
        self.transmission_interval = max(0.0, float(transmission_interval))
        self.default_corrupt_probability = float(default_corrupt_probability)
        self._seq_counter = 0

    @property
    def current_sequence_number(self) -> int:
        """Return the last generated sequence number."""
        return self._seq_counter

    def generate_reading(self) -> Dict[str, float]:
        """
        Simulate sampling sensors for physical environmental values:
        - Temperature: Realistic indoor/outdoor range (18.00 to 32.00 °C)
        - Humidity: Relative humidity percentage (35.00 to 75.00 %)
        - Pressure: Atmospheric barometric pressure (980.00 to 1025.00 hPa)
        
        Returns:
            Dictionary containing temperature_c, humidity_percent, and pressure_hpa.
        """
        temperature = round(random.uniform(18.0, 32.0), 2)
        humidity = round(random.uniform(35.0, 75.0), 2)
        pressure = round(random.uniform(980.0, 1025.0), 2)
        
        return {
            "temperature_c": temperature,
            "humidity_percent": humidity,
            "pressure_hpa": pressure,
        }

    def create_packet(
        self,
        corrupt_probability: Optional[float] = None
    ) -> SensorPacket:
        """
        Create a new sensor packet with telemetry data and CRC32 checksum.
        
        Args:
            corrupt_probability: Float between 0.0 and 1.0 indicating the chance
                                 of simulating channel noise / corruption.
                                 Defaults to self.default_corrupt_probability if None.

        Returns:
            A SensorPacket ready for transmission, containing metadata for both
            the transmitted payload and the original clean packet.
        """
        if corrupt_probability is None:
            corrupt_probability = self.default_corrupt_probability
            
        self._seq_counter += 1
        seq_num = self._seq_counter
        timestamp = round(time.time(), 3)
        
        # 1. Generate clean sensor readings
        readings = self.generate_reading()
        reading_data = {
            "device_id": self.device_id,
            "seq_num": seq_num,
            "timestamp": timestamp,
            "readings": readings
        }
        
        # 2. Serialize clean payload deterministically
        clean_payload_str = serialize_payload(reading_data)
        
        # 3. Calculate sender's CRC32 checksum over the clean payload
        original_crc = calculate_crc32(clean_payload_str)
        
        # 4. Construct the clean baseline packet
        clean_packet = SensorPacket(
            device_id=self.device_id,
            seq_num=seq_num,
            timestamp=timestamp,
            payload=clean_payload_str,
            crc32=original_crc,
            is_simulated_corrupt=False,
            original_crc32=original_crc,
            received_crc32=original_crc,
            original_payload=clean_payload_str,
            corrupted_field=None,
            readings=readings,
            original_packet=None
        )
        
        # 5. Check if channel noise should be simulated
        should_corrupt = (corrupt_probability > 0.0 and random.random() < corrupt_probability)
        
        if not should_corrupt:
            clean_packet.original_packet = clean_packet
            return clean_packet

        # 6. Inject channel noise targeting a specific sensor field
        corrupted_packet = self._inject_channel_noise(
            clean_packet=clean_packet,
            reading_data=reading_data
        )
        return corrupted_packet

    def _inject_channel_noise(
        self,
        clean_packet: SensorPacket,
        reading_data: Dict[str, Any]
    ) -> SensorPacket:
        """
        Simulate channel noise affecting one of the sensor fields.
        
        Alters the value of temperature, humidity, or pressure in the transmitted
        payload while retaining the sender's original CRC32 checksum, causing a
        CRC32 verification failure on the receiving end.
        
        Args:
            clean_packet: The uncorrupted baseline SensorPacket.
            reading_data: The dictionary of sensor data to corrupt.
            
        Returns:
            Corrupted SensorPacket with references to the original packet.
        """
        # Choose which sensor field to corrupt
        fields = ["temperature", "humidity", "pressure"]
        target_field = random.choice(fields)
        
        corrupted_readings = dict(reading_data["readings"])
        
        if target_field == "temperature":
            # Add an erratic temperature spike or drop
            corrupted_readings["temperature_c"] = round(
                corrupted_readings["temperature_c"] + random.choice([45.5, -60.0, 99.9]), 2
            )
        elif target_field == "humidity":
            # Push humidity out of valid physical bounds
            corrupted_readings["humidity_percent"] = round(
                corrupted_readings["humidity_percent"] + random.choice([55.0, -45.0, 80.0]), 2
            )
        elif target_field == "pressure":
            # Distort atmospheric pressure reading
            corrupted_readings["pressure_hpa"] = round(
                corrupted_readings["pressure_hpa"] + random.choice([250.0, -300.0, 500.0]), 2
            )
            
        corrupted_data = dict(reading_data)
        corrupted_data["readings"] = corrupted_readings
        
        corrupted_payload = serialize_payload(corrupted_data)
        
        return SensorPacket(
            device_id=self.device_id,
            seq_num=clean_packet.seq_num,
            timestamp=clean_packet.timestamp,
            payload=corrupted_payload,
            crc32=clean_packet.crc32,  # Sender computed this over clean payload!
            is_simulated_corrupt=True,
            original_crc32=clean_packet.crc32,
            received_crc32=clean_packet.crc32,
            original_payload=clean_packet.payload,
            corrupted_field=target_field,
            readings=corrupted_readings,
            original_packet=clean_packet
        )
