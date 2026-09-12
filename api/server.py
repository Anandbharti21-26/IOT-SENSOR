"""
server.py - FastAPI Backend for IoT Sensor Packet Reliability Monitor (Phase 3).

Provides REST endpoints to:
- Monitor health and status: GET /api/health
- Fetch real-time reliability metrics: GET /api/metrics
- Retrieve recent packet history: GET /api/history
- Control live packet simulation: POST /api/simulate
- Reset state and metrics: POST /api/reset
Includes full CORS support for the Streamlit dashboard or any web frontend.
"""

from collections import deque
import threading
import time
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Query, HTTPException

try:
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:  # pragma: no cover - compatibility fallback for environments with Starlette-only installs
    from starlette.middleware.cors import CORSMiddleware

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - compatibility fallback for environments using Pydantic v1
    from pydantic.v1 import BaseModel, Field

from simulator.device import SensorDevice, SensorPacket, calculate_crc32, serialize_payload
from monitor.verifier import PacketVerifier, VerificationResult, ReliabilityStats


# -----------------------------------------------------------------------------
# Simulation Engine: Thread-Safe State & Background Streaming
# -----------------------------------------------------------------------------

class SimulationEngine:
    """
    Manages continuous or step-based sensor packet generation and CRC32 verification.
    Stores sliding-window packet history and rolling reliability metrics.
    """

    def __init__(
        self,
        device_id: str = "esp32-bme280-node01",
        default_corruption_prob: float = 0.30,
        history_size: int = 150
    ):
        self.device_id = device_id
        self.corruption_probability = max(0.0, min(1.0, float(default_corruption_prob)))
        self.interval_seconds = 0.5
        
        self.device = SensorDevice(
            device_id=self.device_id,
            transmission_interval=self.interval_seconds,
            default_corrupt_probability=self.corruption_probability
        )
        self.verifier = PacketVerifier()
        self.history: deque = deque(maxlen=history_size)
        
        # Concurrency management
        self.lock = threading.Lock()
        self.is_running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def generate_and_verify_single(
        self,
        corrupt_prob: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate one packet, verify its CRC32 checksum, record metrics,
        and append to recent history. Must be called under self.lock.
        """
        prob = self.corruption_probability if corrupt_prob is None else corrupt_prob
        packet: SensorPacket = self.device.create_packet(corrupt_probability=prob)
        result: VerificationResult = self.verifier.verify_packet(packet)
        
        record = {
            "seq_num": result.seq_num,
            "device_id": result.device_id,
            "timestamp": packet.timestamp,
            "is_valid": result.is_valid,
            "status": "VALID" if result.is_valid else "CORRUPT",
            "readings": result.readings or {},
            "original_crc": result.original_crc,
            "received_crc": result.received_crc,
            "computed_crc": result.computed_crc,
            "corrupted_field": result.corrupted_field,
            "noise_injected": result.noise_injected,
            "details": result.details,
            "payload": packet.payload
        }
        self.history.appendleft(record)  # Newest first
        return record

    def step(
        self,
        count: int = 1,
        corrupt_prob: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Generate and verify 'count' packets on demand."""
        generated = []
        with self.lock:
            if corrupt_prob is not None:
                self.corruption_probability = max(0.0, min(1.0, float(corrupt_prob)))
            for _ in range(count):
                rec = self.generate_and_verify_single(self.corruption_probability)
                generated.append(rec)
        return generated

    def start(
        self,
        corruption_prob: Optional[float] = None,
        interval_seconds: Optional[float] = None
    ) -> None:
        """Start the continuous background packet streaming worker."""
        with self.lock:
            if corruption_prob is not None:
                self.corruption_probability = max(0.0, min(1.0, float(corruption_prob)))
            if interval_seconds is not None:
                self.interval_seconds = max(0.05, float(interval_seconds))
                
            if self.is_running:
                return

            self.is_running = True
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="SimulationWorkerThread"
            )
            self._worker_thread.start()

    def stop(self) -> None:
        """Stop the background streaming worker."""
        with self.lock:
            if not self.is_running:
                return
            self.is_running = False
            self._stop_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def _worker_loop(self) -> None:
        """Background thread execution loop generating packets at interval_seconds."""
        while not self._stop_event.is_set():
            with self.lock:
                self.generate_and_verify_single(self.corruption_probability)
                sleep_time = self.interval_seconds
            time.sleep(sleep_time)

    def reset(self) -> None:
        """Reset all metrics, history, and sequence counters."""
        was_running = self.is_running
        if was_running:
            self.stop()
            
        with self.lock:
            self.device = SensorDevice(
                device_id=self.device_id,
                transmission_interval=self.interval_seconds,
                default_corrupt_probability=self.corruption_probability
            )
            self.verifier.reset_stats()
            self.history.clear()

    def get_metrics(self) -> Dict[str, Any]:
        """Fetch current reliability statistics and simulation status."""
        with self.lock:
            stats: ReliabilityStats = self.verifier.get_stats()
            latest_reading = self.history[0]["readings"] if self.history else None
            
            return {
                "simulation": {
                    "is_running": self.is_running,
                    "device_id": self.device_id,
                    "corruption_probability": self.corruption_probability,
                    "interval_seconds": self.interval_seconds,
                    "total_history_count": len(self.history)
                },
                "metrics": {
                    "total_received": stats.total_received,
                    "total_valid": stats.total_valid,
                    "total_corrupted": stats.total_corrupted,
                    "reliability_percentage": stats.reliability_percentage,
                    "corruption_percentage": stats.corruption_percentage,
                    "temperature_errors": stats.temperature_errors,
                    "humidity_errors": stats.humidity_errors,
                    "pressure_errors": stats.pressure_errors
                },
                "latest_readings": latest_reading
            }

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent packet records up to 'limit'."""
        with self.lock:
            limit = max(1, min(limit, len(self.history)))
            return list(self.history)[:limit]


# Global simulation engine instance
engine = SimulationEngine()


# -----------------------------------------------------------------------------
# FastAPI App & Middleware
# -----------------------------------------------------------------------------

app = FastAPI(
    title="IoT Sensor Packet Reliability Monitor API",
    description="Real-time REST API for CRC32-based IoT packet verification and reliability monitoring.",
    version="3.0.0"
)

# Enable Cross-Origin Resource Sharing (CORS) for local web dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits requests from Streamlit, localhost, etc.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Request Models
# -----------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    action: str = Field(
        default="step",
        description="Action to perform: 'start', 'stop', or 'step'."
    )
    corruption_probability: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional corruption probability (0.0 to 1.0)."
    )
    interval_seconds: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Transmission delay in seconds between packets (for streaming)."
    )
    count: Optional[int] = Field(
        default=1,
        ge=1,
        le=100,
        description="Number of packets to generate if action is 'step'."
    )


# -----------------------------------------------------------------------------
# REST Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    """
    Health check endpoint verifying the API server is operational.
    """
    return {
        "status": "healthy",
        "service": "IoT Sensor Packet Reliability Monitor API",
        "version": "3.0.0",
        "timestamp": round(time.time(), 3)
    }


@app.get("/api/metrics")
def get_metrics() -> Dict[str, Any]:
    """
    Retrieve current real-time packet reliability metrics and sensor status.
    """
    return {
        "status": "success",
        "data": engine.get_metrics()
    }


@app.get("/api/history")
def get_history(limit: int = Query(50, ge=1, le=150)) -> Dict[str, Any]:
    """
    Retrieve recent packet transmission and verification records.
    """
    history_records = engine.get_history(limit=limit)
    return {
        "status": "success",
        "count": len(history_records),
        "history": history_records
    }


@app.post("/api/simulate")
def post_simulate(request: SimulateRequest) -> Dict[str, Any]:
    """
    Control packet simulation:
    - action='start': Start continuous packet streaming.
    - action='stop': Stop continuous packet streaming.
    - action='step': Generate a batch of 'count' packets immediately.
    """
    action = request.action.lower()
    
    if action == "start":
        engine.start(
            corruption_prob=request.corruption_probability,
            interval_seconds=request.interval_seconds
        )
        return {
            "status": "success",
            "message": "Continuous packet simulation started",
            "state": engine.get_metrics()["simulation"]
        }
        
    elif action == "stop":
        engine.stop()
        return {
            "status": "success",
            "message": "Continuous packet simulation stopped",
            "state": engine.get_metrics()["simulation"]
        }
        
    elif action == "step":
        generated = engine.step(
            count=request.count or 1,
            corrupt_prob=request.corruption_probability
        )
        return {
            "status": "success",
            "message": f"Generated and verified {len(generated)} packet(s)",
            "packets": generated,
            "metrics": engine.get_metrics()["metrics"]
        }
        
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported action: '{request.action}'. Use 'start', 'stop', or 'step'."
        )


@app.post("/api/reset")
def post_reset() -> Dict[str, Any]:
    """
    Reset all simulation statistics, sliding-window packet history, and counters.
    """
    engine.reset()
    return {
        "status": "success",
        "message": "Simulation metrics and packet history have been reset."
    }
