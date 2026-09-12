"""
test_reliability_monitor.py - Unit & Integration Tests for Phase 2.

Covers:
1. Valid packet verification.
2. Corrupted packet detection via simulated channel noise.
3. Explicit CRC32 mismatch detection (payload tampering & checksum tampering).
4. Reliability and corruption percentage calculations.
5. Deterministic packet serialization consistency.
6. Sensor field-level error attribution (temperature, humidity, pressure).
"""

import unittest
import json
import zlib

from simulator.device import (
    SensorDevice,
    SensorPacket,
    calculate_crc32,
    serialize_payload
)
from monitor.verifier import PacketVerifier, ReliabilityStats


class TestSensorPacketReliabilityMonitor(unittest.TestCase):
    """Test suite for the IoT Sensor Packet Reliability Monitor."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.device = SensorDevice(device_id="test-sensor-node")
        self.verifier = PacketVerifier()

    # -------------------------------------------------------------------------
    # Test 1: Valid Packet Verification
    # -------------------------------------------------------------------------
    def test_valid_packet(self):
        """Verify that clean packets pass CRC32 verification and increment valid counters."""
        # Generate clean packet with 0% noise probability
        packet = self.device.create_packet(corrupt_probability=0.0)
        
        self.assertFalse(packet.is_simulated_corrupt)
        self.assertEqual(packet.original_crc32, packet.received_crc32)
        
        # Verify through PacketVerifier
        result = self.verifier.verify_packet(packet)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(result.computed_crc, result.received_crc)
        self.assertIn("verified successfully", result.details)
        
        # Check cumulative metrics
        stats = self.verifier.get_stats()
        self.assertEqual(stats.total_received, 1)
        self.assertEqual(stats.total_valid, 1)
        self.assertEqual(stats.total_corrupted, 0)
        self.assertEqual(stats.reliability_percentage, 100.0)
        self.assertEqual(stats.corruption_percentage, 0.0)

    # -------------------------------------------------------------------------
    # Test 2: Corrupted Packet Detection
    # -------------------------------------------------------------------------
    def test_corrupted_packet(self):
        """Verify that packets with injected noise fail CRC32 verification."""
        # Force 100% noise probability
        corrupted_packet = self.device.create_packet(corrupt_probability=1.0)
        
        self.assertTrue(corrupted_packet.is_simulated_corrupt)
        self.assertIsNotNone(corrupted_packet.corrupted_field)
        self.assertIsNotNone(corrupted_packet.original_packet)
        
        # Verify through PacketVerifier
        result = self.verifier.verify_packet(corrupted_packet)
        
        self.assertFalse(result.is_valid)
        self.assertNotEqual(result.computed_crc, result.received_crc)
        self.assertIn("mismatch", result.details)
        
        stats = self.verifier.get_stats()
        self.assertEqual(stats.total_received, 1)
        self.assertEqual(stats.total_valid, 0)
        self.assertEqual(stats.total_corrupted, 1)
        self.assertEqual(stats.reliability_percentage, 0.0)
        self.assertEqual(stats.corruption_percentage, 100.0)

    # -------------------------------------------------------------------------
    # Test 3: CRC32 Mismatch Detection
    # -------------------------------------------------------------------------
    def test_crc32_mismatch_detection(self):
        """Test explicit detection when either payload or checksum is altered."""
        # Test 3a: Tampered payload
        raw_data = {
            "device_id": "test-node",
            "seq_num": 1,
            "timestamp": 1700000000.0,
            "readings": {"temperature_c": 22.5, "humidity_percent": 50.0, "pressure_hpa": 1013.2}
        }
        clean_payload = serialize_payload(raw_data)
        correct_crc = calculate_crc32(clean_payload)
        
        # Tamper payload text
        tampered_payload = clean_payload.replace("22.5", "99.9")
        tampered_packet = SensorPacket(
            device_id="test-node",
            seq_num=1,
            timestamp=1700000000.0,
            payload=tampered_payload,
            crc32=correct_crc,
            is_simulated_corrupt=True
        )
        result_payload_tamper = self.verifier.verify_packet(tampered_packet)
        self.assertFalse(result_payload_tamper.is_valid)
        self.assertNotEqual(result_payload_tamper.computed_crc, correct_crc)

        # Test 3b: Corrupted received checksum
        corrupted_crc_packet = SensorPacket(
            device_id="test-node",
            seq_num=2,
            timestamp=1700000001.0,
            payload=clean_payload,
            crc32=correct_crc,
            received_crc32="badcrc00",
            is_simulated_corrupt=True
        )
        result_crc_tamper = self.verifier.verify_packet(corrupted_crc_packet)
        self.assertFalse(result_crc_tamper.is_valid)
        self.assertEqual(result_crc_tamper.computed_crc, correct_crc)
        self.assertEqual(result_crc_tamper.received_crc, "badcrc00")

    # -------------------------------------------------------------------------
    # Test 4: Reliability Calculation
    # -------------------------------------------------------------------------
    def test_reliability_calculation(self):
        """Test accurate calculation of reliability and corruption percentages."""
        # Baseline: 0 packets
        empty_stats = self.verifier.get_stats()
        self.assertEqual(empty_stats.reliability_percentage, 100.0)
        self.assertEqual(empty_stats.corruption_percentage, 0.0)

        # Simulate 8 valid and 2 corrupted packets
        for _ in range(8):
            pkt = self.device.create_packet(corrupt_probability=0.0)
            self.verifier.verify_packet(pkt)
            
        for _ in range(2):
            pkt = self.device.create_packet(corrupt_probability=1.0)
            self.verifier.verify_packet(pkt)

        stats = self.verifier.get_stats()
        self.assertEqual(stats.total_received, 10)
        self.assertEqual(stats.total_valid, 8)
        self.assertEqual(stats.total_corrupted, 2)
        self.assertEqual(stats.reliability_percentage, 80.0)
        self.assertEqual(stats.corruption_percentage, 20.0)
        self.assertEqual(round(stats.reliability_percentage + stats.corruption_percentage, 1), 100.0)

    # -------------------------------------------------------------------------
    # Test 5: Packet Serialization Consistency
    # -------------------------------------------------------------------------
    def test_packet_serialization_consistency(self):
        """Verify that dictionary key ordering does not alter serialized string or CRC32."""
        dict_a = {
            "device_id": "sensor-01",
            "seq_num": 42,
            "timestamp": 1710000000.123,
            "readings": {"temperature_c": 25.1, "humidity_percent": 60.2, "pressure_hpa": 1012.8}
        }
        
        # Same data with keys inserted in different order
        dict_b = {
            "readings": {"pressure_hpa": 1012.8, "humidity_percent": 60.2, "temperature_c": 25.1},
            "timestamp": 1710000000.123,
            "device_id": "sensor-01",
            "seq_num": 42
        }
        
        str_a = serialize_payload(dict_a)
        str_b = serialize_payload(dict_b)
        
        # Byte-for-byte string equality
        self.assertEqual(str_a, str_b)
        
        # Exact CRC32 equality
        crc_a = calculate_crc32(str_a)
        crc_b = calculate_crc32(str_b)
        self.assertEqual(crc_a, crc_b)

    # -------------------------------------------------------------------------
    # Test 6: Sensor Field-Level Error Attribution
    # -------------------------------------------------------------------------
    def test_field_level_error_attribution(self):
        """Verify that temperature, humidity, and pressure errors are tracked individually."""
        fields = ["temperature", "humidity", "pressure"]
        for field in fields:
            # Create a packet and manually set corrupted field
            pkt = self.device.create_packet(corrupt_probability=0.0)
            tampered = SensorPacket(
                device_id=pkt.device_id,
                seq_num=pkt.seq_num,
                timestamp=pkt.timestamp,
                payload=pkt.payload + "corrupt",
                crc32=pkt.crc32,
                corrupted_field=field,
                is_simulated_corrupt=True
            )
            self.verifier.verify_packet(tampered)
            
        stats = self.verifier.get_stats()
        self.assertEqual(stats.temperature_errors, 1)
        self.assertEqual(stats.humidity_errors, 1)
        self.assertEqual(stats.pressure_errors, 1)
        self.assertEqual(stats.total_corrupted, 3)


if __name__ == "__main__":
    unittest.main()
