# IoT Sensor Packet Reliability Monitor Using CRC32

A complete Python-based IoT reliability and packet integrity monitoring platform. This system simulates multi-sensor IoT telemetry over noisy communication channels, detects data corruption in transit using 32-bit Cyclic Redundancy Checks (CRC32), provides a high-performance **FastAPI backend REST service**, and visualizes live channel reliability through an **interactive Streamlit web dashboard**.

---

## 🎯 Project Objective

In real-world Internet of Things (IoT) deployments—such as smart environmental sensing, industrial IoT, and agricultural monitoring—microcontroller nodes (ESP32, Arduino, Raspberry Pi) transmit sensor readings across wireless links (Wi-Fi, Bluetooth, Zigbee, LoRa, cellular).

These channels frequently suffer from:
- **Radio frequency interference and channel noise**
- **Bit-level corruption caused by voltage fluctuations or electrical noise**
- **Packet truncation and dropped frames**

This platform provides:
1. **Multi-sensor telemetry packaging** (temperature, humidity, atmospheric pressure) with deterministic canonical JSON serialization and timestamps.
2. **Sender-side CRC32 checksum computation** prior to transmission.
3. **Configurable simulated channel noise** targeting individual sensor fields.
4. **Receiver-side verification gateway** comparing recalculations against transmitted checksums.
5. **FastAPI backend** exposing REST endpoints for health, live telemetry, metrics, history, and simulation control.
6. **Interactive Streamlit Web Dashboard** providing live streaming controls, real-time gauges, field-level error charts, and history tables.

---

## 🚀 Phase Breakdown

### Phase 1: Core Foundation & CRC32 Logic
- Clean modular structure (`simulator`, `monitor`, `api`, `dashboard`).
- Virtual environment and baseline dependencies.
- CRC32 checksum generation with standard library `zlib`.
- Initial terminal dashboard and packet streaming.

### Phase 2: Multi-Sensor Telemetry & Field Error Tracking
- Realistic temperature, humidity, and barometric pressure data generation.
- Deterministic JSON payload serialization (`serialize_payload`).
- Configurable sensor node ID, sequence counters, and transmission intervals.
- Channel noise simulation with sensor field-level error attribution:
  - `temperature_errors`
  - `humidity_errors`
  - `pressure_errors`
- 6 unit & integration tests covering CRC32 verification and metrics calculations.

### Phase 3: Live FastAPI Backend & Streamlit Web Dashboard
- **FastAPI REST API Server (`api/server.py`)**:
  - `GET /api/health` — Health check endpoint.
  - `GET /api/metrics` — Current packet reliability statistics and simulation status.
  - `GET /api/history` — Sliding-window history of recent packets with status and CRC details.
  - `POST /api/simulate` — Start background streaming, pause, or step packets.
  - `POST /api/reset` — Reset metric counters and packet history.
  - Full CORS middleware enabled for local and remote dashboard access.
- **Interactive Streamlit Dashboard (`dashboard/streamlit_app.py`)**:
  - Live temperature, humidity, and barometric pressure gauge cards.
  - Instant `[ VALID ]` / `[CORRUPT]` status banner with CRC breakdown.
  - Real-time reliability and corruption percentage counters.
  - Sensor field-level error distribution charts (bar charts via pandas).
  - Recent packet transmission history log table.
  - Live interactive controls: **▶ Start**, **⏸ Stop**, **⚡ Step 1**, **🔄 Reset**.
  - Interactive noise probability slider (`0%` to `100%`) and transmission interval slider.
  - Auto-refresh toggle with configurable refresh rate.
- **Expanded Test Suite (`tests/test_api_endpoints.py`)**:
  - 12 comprehensive unit and integration tests passing with 100% coverage.

---

## 🏗️ System Architecture

```text
+--------------------------------------------------------+
|        IoT Sensor Node Simulator (ESP32 / BME280)      |
|                 [simulator/device.py]                  |
|                                                        |
| 1. Read: Temperature, Humidity, Barometric Pressure    |
| 2. Canonical JSON Serialization (serialize_payload)    |
| 3. Compute 32-bit Checksum: calculate_crc32(payload)   |
+---------------------------+----------------------------+
                            |
                            | [Simulated Wireless Channel]
                            | Configurable Noise (0.0 - 1.0)
                            v
+--------------------------------------------------------+
|         Reliability Monitor Gateway & Verifier         |
|                  [monitor/verifier.py]                 |
|                                                        |
| 1. Ingest Packet (payload, seq_num, CRC)               |
| 2. Recalculate CRC32: computed_crc = crc32(payload)    |
| 3. Integrity Check: computed_crc == received_crc       |
|    - MATCH   -> VALID (increment valid count)          |
|    - MISMATCH -> CORRUPT (increment corrupt count &    |
|                  attribute to temp / hum / pres)       |
| 4. Compute Rolling Reliability % and Corruption %      |
+---------------------------+----------------------------+
                            |
             +--------------+--------------+
             |                             |
             v                             v
+--------------------------------+  +--------------------------------+
|      FastAPI Backend API       |  |   Streamlit Web Dashboard      |
|       [api/server.py]          |  |  [dashboard/streamlit_app.py]  |
|                                |  |                                |
| • GET  /api/health             |  | • Real-time Telemetry Cards    |
| • GET  /api/metrics            |  | • Live CRC32 Verification      |
| • GET  /api/history            |  | • Field-Level Error Charts     |
| • POST /api/simulate           |  | • Start / Stop / Reset Buttons |
| • POST /api/reset              |  | • Noise Probability Slider     |
| • CORS Enabled                 |  | • Automatic Refresh            |
+--------------------------------+  +--------------------------------+
```

---

## 📁 Project Structure

```text
IoT project1/
├── venv/                           # Python 3 virtual environment
├── .gitignore                      # Git ignore rules for caches, venv, logs
├── requirements.txt                # Full project dependencies (FastAPI, Streamlit, etc.)
├── README.md                       # Comprehensive guide & architecture documentation
├── main.py                         # Phase 2 CLI entry point (streams 25 packets)
├── simulator/                      # IoT sensor node and channel noise simulation
│   ├── __init__.py
│   └── device.py                   # Sensor reading generation, CRC32, & serialization
├── monitor/                        # Verification and metrics engine
│   ├── __init__.py
│   └── verifier.py                 # CRC32 verification and field-level error attribution
├── api/                            # FastAPI backend service
│   ├── __init__.py
│   ├── routes.py                   # Legacy metrics formatting helpers
│   └── server.py                   # FastAPI REST API with state & background worker
├── dashboard/                      # Visualization layer
│   ├── __init__.py
│   ├── app.py                      # Terminal dashboard visualizer
│   └── streamlit_app.py            # Real-time interactive Streamlit web dashboard
└── tests/                          # Comprehensive test suite (12 tests)
    ├── __init__.py
    ├── test_reliability_monitor.py # Core CRC32, serialization, & error tracking tests
    └── test_api_endpoints.py       # REST API endpoint integration tests
```

---

## ⚙️ How to Run the Project (Exact macOS Commands)

Open your terminal and navigate to the project directory:
```bash
cd "/Users/anandkumarbharti/Documents/antigravity files/IoT project/IoT project1"
```

### 1. Run the Test Suite
Verify that all 12 tests pass cleanly:
```bash
./venv/bin/python3 -m unittest discover tests -v
```

### 2. Run the Terminal Demo (Phase 2 Entry Point)
Executes a 25-packet live simulation in the terminal with colored status rows and metrics:
```bash
./venv/bin/python3 main.py
```

### 3. Start the FastAPI Backend Server
Launches the REST API on `http://127.0.0.1:8000`:
```bash
./venv/bin/uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
```
- Interactive API Docs (Swagger UI): `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/health`
- Metrics: `http://127.0.0.1:8000/api/metrics`
- History: `http://127.0.0.1:8000/api/history`

### 4. Start the Streamlit Web Dashboard
In a second terminal window (with the FastAPI server running):
```bash
cd "/Users/anandkumarbharti/Documents/antigravity files/IoT project/IoT project1"
./venv/bin/streamlit run dashboard/streamlit_app.py --server.port 8501
```
Open your web browser and navigate to:
```text
http://localhost:8501
```

---

## 📡 REST API Reference

| Method | Endpoint | Description | Sample Response / Parameters |
|---|---|---|---|
| `GET` | `/api/health` | Service health status | `{"status": "healthy", "service": "...", "version": "3.0.0"}` |
| `GET` | `/api/metrics` | Real-time reliability stats | Returns `total_received`, `total_valid`, `reliability_percentage`, and field error counts |
| `GET` | `/api/history?limit=50` | Recent packet records | Array of last `limit` packets with CRC and status |
| `POST` | `/api/simulate` | Control simulation | Body: `{"action": "start"\|"stop"\|"step", "corruption_probability": 0.3, "count": 1}` |
| `POST` | `/api/reset` | Clear metrics & history | `{"status": "success", "message": "Simulation metrics and packet history have been reset."}` |

---

## 🧪 Test Coverage Summary

- **`test_api_endpoints.py`**:
  - `test_health_endpoint`: Tests `/api/health` status code and JSON payload.
  - `test_metrics_endpoint`: Tests baseline metrics reporting.
  - `test_simulate_step_and_history_endpoint`: Tests on-demand packet generation and history logging.
  - `test_crc32_verification_via_api`: Tests 100% noise injection and mismatch detection through the API.
  - `test_reset_endpoint`: Tests clearing state via `/api/reset`.
  - `test_start_and_stop_streaming`: Tests continuous background worker start/stop lifecycle.
- **`test_reliability_monitor.py`**:
  - `test_valid_packet`: Tests clean packet transmission and counter increments.
  - `test_corrupted_packet`: Tests simulated channel noise detection.
  - `test_crc32_mismatch_detection`: Tests payload and checksum tampering.
  - `test_reliability_calculation`: Tests mathematical accuracy of reliability and corruption percentages.
  - `test_packet_serialization_consistency`: Tests canonical key ordering.
  - `test_field_level_error_attribution`: Tests individual attribution for `temperature_errors`, `humidity_errors`, and `pressure_errors`.
