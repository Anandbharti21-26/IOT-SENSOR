"""
verifier.py - Packet Integrity Verifier and Reliability Metrics Tracker (Phase 2).

This module inspects incoming IoT sensor packets:
1. Re-computes CRC32 on the received payload string.
2. Compares the re-computed CRC32 with the sender's transmitted CRC32 checksum.
3. Classifies packet integrity as VALID (clean) or CORRUPTED (noise detected).
4. Maintains rolling reliability metrics (total, valid, corrupted, reliability %, corruption %).
5. Tracks error frequencies broken down by individual sensor field:
   - temperature_errors
   - humidity_errors
   - pressure_errors
"""

import json
from dataclasses import dataclass
from typing import Dict, Any, Optional

from simulator.device import SensorPacket, calculate_crc32


@dataclass
class VerificationResult:
    """
    Result of a single packet integrity check.
    
    Attributes:
        seq_num: Packet sequence number.
        device_id: Sending sensor node identifier.
        is_valid: True if computed CRC32 matches received CRC32.
        original_crc: Sender's original CRC32 checksum.
        received_crc: Checksum received across the channel.
        computed_crc: Checksum recalculated by receiver from payload.
        details: Human-readable verification explanation.
        corrupted_field: Name of sensor field affected by corruption (if any).
        readings: Sensor reading values extracted from the packet.
        noise_injected: Whether simulation injected noise into this packet.
    """
    seq_num: int
    device_id: str
    is_valid: bool
    original_crc: str
    received_crc: str
    computed_crc: str
    details: str
    corrupted_field: Optional[str] = None
    readings: Optional[Dict[str, float]] = None
    noise_injected: bool = False


@dataclass
class ReliabilityStats:
    """
    Cumulative packet transmission reliability statistics.
    """
    total_received: int
    total_valid: int
    total_corrupted: int
    reliability_percentage: float
    corruption_percentage: float
    temperature_errors: int = 0
    humidity_errors: int = 0
    pressure_errors: int = 0

    def summary(self) -> str:
        """Format stats into a clean, human-readable summary string."""
        return (
            f"Total: {self.total_received} | "
            f"Valid: {self.total_valid} ({self.reliability_percentage:.1f}%) | "
            f"Corrupted: {self.total_corrupted} ({self.corruption_percentage:.1f}%) | "
            f"Errors [Temp: {self.temperature_errors}, Hum: {self.humidity_errors}, Pres: {self.pressure_errors}]"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to a standard dictionary for API or JSON export."""
        return {
            "total_received": self.total_received,
            "total_valid": self.total_valid,
            "total_corrupted": self.total_corrupted,
            "reliability_percentage": self.reliability_percentage,
            "corruption_percentage": self.corruption_percentage,
            "temperature_errors": self.temperature_errors,
            "humidity_errors": self.humidity_errors,
            "pressure_errors": self.pressure_errors,
        }


class PacketVerifier:
    """
    Verifies CRC32 checksums for incoming sensor packets, detects data corruption,
    and tracks rolling reliability metrics with sensor field-level error attribution.
    """

    def __init__(self):
        """Initialize the packet verifier with zeroed counters."""
        self.total_received = 0
        self.total_valid = 0
        self.total_corrupted = 0
        self.temperature_errors = 0
        self.humidity_errors = 0
        self.pressure_errors = 0

    def verify_packet(self, packet: SensorPacket) -> VerificationResult:
        """
        Verify the integrity of a received sensor packet using CRC32.
        
        Steps:
        1. Recalculate CRC32 on the received packet payload bytes.
        2. Compare newly computed CRC32 against received CRC32.
        3. If checksums match, mark packet as VALID.
        4. If checksums differ, mark packet as CORRUPTED and attribute error
           to the appropriate sensor field (temperature, humidity, or pressure).

        Args:
            packet: The SensorPacket received across the channel.

        Returns:
            VerificationResult containing full validation details.
        """
        self.total_received += 1
        
        # 1. Recalculate CRC32 on the received payload
        computed_crc = calculate_crc32(packet.payload)
        
        # 2. Extract received and original checksums
        received_crc = (packet.received_crc32 or packet.crc32).lower()
        original_crc = (packet.original_crc32 or packet.crc32).lower()
        
        # 3. Compare received checksum against calculated checksum
        is_valid = (computed_crc.lower() == received_crc)
        
        # 4. Extract readings if available or parse from payload
        readings = packet.readings
        if readings is None:
            try:
                parsed = json.loads(packet.payload)
                readings = parsed.get("readings")
            except Exception:
                readings = None

        corrupted_field = packet.corrupted_field

        if is_valid:
            self.total_valid += 1
            details = f"CRC32 verified successfully ({computed_crc}). Payload integrity is intact."
        else:
            self.total_corrupted += 1
            # Attribute error to sensor field
            corrupted_field = self._detect_corrupted_field(packet)
            self._increment_field_error(corrupted_field)
            
            details = (
                f"CRC32 mismatch! Received '{received_crc}', computed '{computed_crc}'. "
                f"Data corruption detected in field: '{corrupted_field or 'unknown'}'."
            )

        return VerificationResult(
            seq_num=packet.seq_num,
            device_id=packet.device_id,
            is_valid=is_valid,
            original_crc=original_crc,
            received_crc=received_crc,
            computed_crc=computed_crc,
            details=details,
            corrupted_field=corrupted_field,
            readings=readings,
            noise_injected=packet.is_simulated_corrupt
        )

    def _detect_corrupted_field(self, packet: SensorPacket) -> Optional[str]:
        """
        Identify which sensor field was altered by channel noise.
        
        Uses packet metadata if present, or compares original payload readings
        against corrupted payload readings.
        
        Args:
            packet: The corrupted SensorPacket.
            
        Returns:
            Field name ('temperature', 'humidity', 'pressure') or None.
        """
        if packet.corrupted_field:
            return packet.corrupted_field
            
        # If original packet reference is available, compare readings directly
        if packet.original_packet and packet.original_packet.readings and packet.readings:
            orig = packet.original_packet.readings
            curr = packet.readings
            if orig.get("temperature_c") != curr.get("temperature_c"):
                return "temperature"
            if orig.get("humidity_percent") != curr.get("humidity_percent"):
                return "humidity"
            if orig.get("pressure_hpa") != curr.get("pressure_hpa"):
                return "pressure"
                
        # If original payload string is available, compare JSON reading values
        if packet.original_payload:
            try:
                orig_json = json.loads(packet.original_payload).get("readings", {})
                curr_json = json.loads(packet.payload).get("readings", {})
                for field_key, field_name in [
                    ("temperature_c", "temperature"),
                    ("humidity_percent", "humidity"),
                    ("pressure_hpa", "pressure"),
                ]:
                    if orig_json.get(field_key) != curr_json.get(field_key):
                        return field_name
            except Exception:
                pass

        return None

    def _increment_field_error(self, field_name: Optional[str]) -> None:
        """Increment the error counter for a specific sensor field."""
        if not field_name:
            return
            
        normalized = field_name.lower()
        if "temp" in normalized:
            self.temperature_errors += 1
        elif "hum" in normalized:
            self.humidity_errors += 1
        elif "pres" in normalized:
            self.pressure_errors += 1

    def get_stats(self) -> ReliabilityStats:
        """
        Calculate and return current reliability statistics.
        
        Returns:
            ReliabilityStats object with totals, percentages, and field error counts.
        """
        if self.total_received == 0:
            rel_pct = 100.0
            corrupt_pct = 0.0
        else:
            rel_pct = round((self.total_valid / self.total_received) * 100.0, 2)
            corrupt_pct = round((self.total_corrupted / self.total_received) * 100.0, 2)
            
        return ReliabilityStats(
            total_received=self.total_received,
            total_valid=self.total_valid,
            total_corrupted=self.total_corrupted,
            reliability_percentage=rel_pct,
            corruption_percentage=corrupt_pct,
            temperature_errors=self.temperature_errors,
            humidity_errors=self.humidity_errors,
            pressure_errors=self.pressure_errors
        )

    def reset_stats(self) -> None:
        """Reset all metric counters and error breakdown counters back to zero."""
        self.total_received = 0
        self.total_valid = 0
        self.total_corrupted = 0
        self.temperature_errors = 0
        self.humidity_errors = 0
        self.pressure_errors = 0
