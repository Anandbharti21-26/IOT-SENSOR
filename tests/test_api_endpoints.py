"""
test_api_endpoints.py - Integration tests for the FastAPI backend (Phase 3).

Tests:
1. GET /api/health
2. GET /api/metrics
3. GET /api/history
4. POST /api/simulate (step, start, stop)
5. POST /api/reset
6. CRC32 verification through the API simulation pipeline
"""

import unittest
from fastapi.testclient import TestClient
from api.server import app, engine


class TestApiEndpoints(unittest.TestCase):
    """Test suite for FastAPI backend endpoints."""

    @classmethod
    def setUpClass(cls):
        """Initialize TestClient."""
        cls.client = TestClient(app)

    def setUp(self):
        """Reset simulation engine state before each test."""
        engine.reset()

    def tearDown(self):
        """Ensure background worker is stopped after each test."""
        engine.stop()

    def test_health_endpoint(self):
        """Test GET /api/health returns 200 and healthy status."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)
        self.assertIn("service", data)

    def test_metrics_endpoint(self):
        """Test GET /api/metrics returns accurate initial metrics."""
        response = self.client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        
        metrics = data["data"]["metrics"]
        self.assertEqual(metrics["total_received"], 0)
        self.assertEqual(metrics["total_valid"], 0)
        self.assertEqual(metrics["total_corrupted"], 0)
        self.assertEqual(metrics["reliability_percentage"], 100.0)
        self.assertEqual(metrics["corruption_percentage"], 0.0)

    def test_simulate_step_and_history_endpoint(self):
        """Test POST /api/simulate with step action and GET /api/history."""
        # Step 5 clean packets (0% noise)
        sim_response = self.client.post(
            "/api/simulate",
            json={"action": "step", "count": 5, "corruption_probability": 0.0}
        )
        self.assertEqual(sim_response.status_code, 200)
        sim_data = sim_response.json()
        self.assertEqual(len(sim_data["packets"]), 5)
        self.assertEqual(sim_data["metrics"]["total_received"], 5)
        self.assertEqual(sim_data["metrics"]["total_valid"], 5)

        # Query history endpoint
        hist_response = self.client.get("/api/history?limit=10")
        self.assertEqual(hist_response.status_code, 200)
        hist_data = hist_response.json()
        self.assertEqual(hist_data["status"], "success")
        self.assertEqual(hist_data["count"], 5)
        self.assertEqual(len(hist_data["history"]), 5)
        
        # Verify first packet format
        first_pkt = hist_data["history"][0]
        self.assertEqual(first_pkt["status"], "VALID")
        self.assertTrue(first_pkt["is_valid"])
        self.assertIn("temperature_c", first_pkt["readings"])

    def test_crc32_verification_via_api(self):
        """Test that POST /api/simulate with 100% noise records corrupted packets."""
        sim_response = self.client.post(
            "/api/simulate",
            json={"action": "step", "count": 3, "corruption_probability": 1.0}
        )
        self.assertEqual(sim_response.status_code, 200)
        
        # Check metrics for corrupted packets
        metrics_response = self.client.get("/api/metrics")
        metrics = metrics_response.json()["data"]["metrics"]
        self.assertEqual(metrics["total_corrupted"], 3)
        self.assertEqual(metrics["total_valid"], 0)
        self.assertEqual(metrics["reliability_percentage"], 0.0)
        self.assertEqual(metrics["corruption_percentage"], 100.0)

        # Check history shows CORRUPT status and CRC mismatch
        hist_response = self.client.get("/api/history?limit=3")
        records = hist_response.json()["history"]
        for r in records:
            self.assertEqual(r["status"], "CORRUPT")
            self.assertFalse(r["is_valid"])
            self.assertNotEqual(r["received_crc"], r["computed_crc"])

    def test_reset_endpoint(self):
        """Test POST /api/reset clears history and metric counters."""
        # Generate 4 packets first
        self.client.post(
            "/api/simulate",
            json={"action": "step", "count": 4, "corruption_probability": 0.5}
        )
        # Verify history has 4 items
        self.assertEqual(self.client.get("/api/history").json()["count"], 4)
        
        # Send reset request
        reset_response = self.client.post("/api/reset")
        self.assertEqual(reset_response.status_code, 200)
        
        # Verify state is cleared
        metrics = self.client.get("/api/metrics").json()["data"]["metrics"]
        self.assertEqual(metrics["total_received"], 0)
        self.assertEqual(metrics["total_valid"], 0)
        self.assertEqual(metrics["total_corrupted"], 0)
        self.assertEqual(self.client.get("/api/history").json()["count"], 0)

    def test_start_and_stop_streaming(self):
        """Test POST /api/simulate start and stop actions."""
        # Start background stream
        start_res = self.client.post(
            "/api/simulate",
            json={"action": "start", "interval_seconds": 0.1, "corruption_probability": 0.2}
        )
        self.assertEqual(start_res.status_code, 200)
        self.assertTrue(start_res.json()["state"]["is_running"])

        # Stop stream
        stop_res = self.client.post("/api/simulate", json={"action": "stop"})
        self.assertEqual(stop_res.status_code, 200)
        self.assertFalse(stop_res.json()["state"]["is_running"])


if __name__ == "__main__":
    unittest.main()
