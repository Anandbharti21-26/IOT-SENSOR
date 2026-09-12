"""
streamlit_app.py - Real-Time Web Dashboard for IoT Sensor Packet Reliability Monitor (Phase 3).

Visualizes:
1. Live temperature, humidity, and barometric pressure readings.
2. Real-time packet validity / corruption status with CRC32 matching.
3. Network reliability metrics (total, valid, corrupt, percentages).
4. Error frequency breakdown by individual sensor field (charts).
5. Sliding-window packet transmission history table.
6. Interactive controls: Start/Stop stream, Step, Reset, and Noise probability slider.
"""

import time
from typing import Dict, Any, List, Optional
import requests
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="IoT Sensor Packet Reliability Monitor",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for crisp status badges and clean typography
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid #dee2e6;
    }
    .badge-valid {
        background-color: #28a745;
        color: white;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-corrupt {
        background-color: #dc3545;
        color: white;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Sidebar Configuration & Controls
# -----------------------------------------------------------------------------
st.sidebar.title("📡 IoT Monitor Controls")

api_base_url = st.sidebar.text_input(
    "API Server URL",
    value="http://127.0.0.1:8000",
    help="FastAPI backend URL"
)

st.sidebar.markdown("---")
st.sidebar.subheader("🎲 Channel Noise Settings")

corruption_slider = st.sidebar.slider(
    "Corruption Probability",
    min_value=0.0,
    max_value=1.0,
    value=0.30,
    step=0.05,
    format="%.2f",
    help="Probability of injecting simulated noise into each sensor packet"
)

stream_interval = st.sidebar.slider(
    "Transmission Interval (seconds)",
    min_value=0.1,
    max_value=2.0,
    value=0.5,
    step=0.1,
    help="Cadence of simulated background transmissions"
)

st.sidebar.markdown("---")
st.sidebar.subheader("🕹️ Simulation Actions")

col_btn1, col_btn2 = st.sidebar.columns(2)
col_btn3, col_btn4 = st.sidebar.columns(2)


# API Helper Functions
def fetch_api(endpoint: str) -> Optional[Dict[str, Any]]:
    """Helper to query the backend GET endpoints safely."""
    try:
        url = f"{api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        res = requests.get(url, timeout=2.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        return None
    return None


def post_api(endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Helper to send POST requests to the backend."""
    try:
        url = f"{api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        res = requests.post(url, json=payload, timeout=3.0)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.sidebar.error(f"Action failed: {e}")
    return None


# Sidebar Button Actions
with col_btn1:
    if st.button("▶ Start", width="stretch", type="primary"):
        post_api("/api/simulate", {
            "action": "start",
            "corruption_probability": corruption_slider,
            "interval_seconds": stream_interval
        })
        st.toast("Continuous simulation started!", icon="🚀")

with col_btn2:
    if st.button("⏸ Stop", width="stretch"):
        post_api("/api/simulate", {"action": "stop"})
        st.toast("Simulation paused.", icon="⏸")

with col_btn3:
    if st.button("⚡ Step 1", width="stretch"):
        post_api("/api/simulate", {
            "action": "step",
            "corruption_probability": corruption_slider,
            "count": 1
        })

with col_btn4:
    if st.button("🔄 Reset", width="stretch"):
        post_api("/api/reset", {})
        st.toast("Metrics and history reset.", icon="🔄")

st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("Auto-refresh Dashboard", value=True)
refresh_interval = st.sidebar.slider("Refresh Rate (s)", 0.5, 3.0, 1.0, 0.5)


# -----------------------------------------------------------------------------
# Main Dashboard Display
# -----------------------------------------------------------------------------
st.title("📡 IoT Sensor Packet Reliability Monitor")
st.caption("Phase 3: Real-Time CRC32 Packet Integrity Verification & Channel Reliability Analytics")

# Check API Health
health_data = fetch_api("/api/health")
if not health_data:
    st.error(
        f"⚠️ Cannot connect to FastAPI server at `{api_base_url}`. "
        "Please start the backend server using: `./venv/bin/uvicorn api.server:app --reload --port 8000`"
    )
    if auto_refresh:
        time.sleep(2.0)
        st.rerun()
    st.stop()

# Query Metrics and History
metrics_response = fetch_api("/api/metrics") or {}
history_response = fetch_api("/api/history?limit=50") or {}

metrics_data = metrics_response.get("data", {})
sim_state = metrics_data.get("simulation", {})
stats = metrics_data.get("metrics", {})
history_records = history_response.get("history", [])

# Simulation Status Banner
is_running = sim_state.get("is_running", False)
state_label = "🟢 LIVE STREAMING ACTIVE" if is_running else "🟡 SIMULATION IDLE (Paused)"
st.info(
    f"**System State:** {state_label} | "
    f"**Active Node:** `{sim_state.get('device_id', 'Unknown')}` | "
    f"**Current Noise:** `{sim_state.get('corruption_probability', 0.3) * 100:.1f}%`"
)

# -----------------------------------------------------------------------------
# Top Metrics Row
# -----------------------------------------------------------------------------
m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
total_pkts = stats.get("total_received", 0)
valid_pkts = stats.get("total_valid", 0)
corrupt_pkts = stats.get("total_corrupted", 0)
rel_pct = stats.get("reliability_percentage", 100.0)
corrupt_pct = stats.get("corruption_percentage", 0.0)

m_col1.metric("Total Packets", f"{total_pkts}")
m_col2.metric("Valid Packets", f"{valid_pkts}", delta=f"{valid_pkts} intact" if total_pkts else None)
m_col3.metric("Corrupted Packets", f"{corrupt_pkts}", delta=f"-{corrupt_pkts} errors" if corrupt_pkts else None, delta_color="inverse")
m_col4.metric("Reliability Rate", f"{rel_pct:.1f}%")
m_col5.metric("Corruption Rate", f"{corrupt_pct:.1f}%")

st.markdown("---")

# -----------------------------------------------------------------------------
# Live Sensor Readings & Latest Packet Status
# -----------------------------------------------------------------------------
row2_col1, row2_col2 = st.columns([1, 1])

with row2_col1:
    st.subheader("🌡️ Latest Sensor Telemetry")
    latest_pkt = history_records[0] if history_records else None
    
    if latest_pkt and latest_pkt.get("readings"):
        readings = latest_pkt["readings"]
        temp = readings.get("temperature_c", 0.0)
        hum = readings.get("humidity_percent", 0.0)
        pres = readings.get("pressure_hpa", 0.0)
        
        t_col, h_col, p_col = st.columns(3)
        t_col.metric("Temperature", f"{temp:.1f} °C")
        h_col.metric("Relative Humidity", f"{hum:.1f} %")
        p_col.metric("Barometric Pressure", f"{pres:.1f} hPa")
    else:
        st.write("No telemetry packets received yet. Click **▶ Start** or **⚡ Step 1** in the sidebar.")

with row2_col2:
    st.subheader("🔍 Latest Packet Integrity Status")
    if latest_pkt:
        is_val = latest_pkt.get("is_valid", False)
        status_text = "VALID" if is_val else "CORRUPTED"
        status_color = "#28a745" if is_val else "#dc3545"
        
        st.markdown(
            f"<div style='padding: 10px; background-color: {status_color}; color: white; border-radius: 6px; font-weight: bold; text-align: center; font-size: 1.1rem;'>"
            f"PACKET #{latest_pkt.get('seq_num'):03d} — {status_text}"
            f"</div>",
            unsafe_allow_html=True
        )
        
        c1, c2, c3 = st.columns(3)
        c1.text(f"Original CRC:\n{latest_pkt.get('original_crc')}")
        c2.text(f"Received CRC:\n{latest_pkt.get('received_crc')}")
        c3.text(f"Calculated CRC:\n{latest_pkt.get('computed_crc')}")
        
        if not is_val:
            st.warning(f"⚠️ Corruption detected in field: **{latest_pkt.get('corrupted_field', 'unknown')}**")
    else:
        st.write("Awaiting incoming packet verification...")

st.markdown("---")

# -----------------------------------------------------------------------------
# Analytics: Field-Level Error Charts
# -----------------------------------------------------------------------------
st.subheader("📊 Sensor Field-Level Error Attribution")

temp_errs = stats.get("temperature_errors", 0)
hum_errs = stats.get("humidity_errors", 0)
pres_errs = stats.get("pressure_errors", 0)

chart_data = pd.DataFrame({
    "Sensor Field": ["Temperature", "Humidity", "Pressure"],
    "Error Count": [temp_errs, hum_errs, pres_errs]
}).set_index("Sensor Field")

ch_col1, ch_col2 = st.columns([2, 1])

with ch_col1:
    st.bar_chart(chart_data, color="#ff4b4b")

with ch_col2:
    st.write("**Error Distribution Summary:**")
    total_field_errs = temp_errs + hum_errs + pres_errs
    if total_field_errs > 0:
        st.write(f"- 🌡️ **Temperature:** {temp_errs} ({temp_errs/total_field_errs*100:.1f}%)")
        st.write(f"- 💧 **Humidity:** {hum_errs} ({hum_errs/total_field_errs*100:.1f}%)")
        st.write(f"- ⏲️ **Pressure:** {pres_errs} ({pres_errs/total_field_errs*100:.1f}%)")
    else:
        st.write("No transmission errors recorded yet.")

st.markdown("---")

# -----------------------------------------------------------------------------
# Packet Transmission History Table
# -----------------------------------------------------------------------------
st.subheader("📜 Recent Packet History Log")

if history_records:
    table_rows = []
    for pkt in history_records:
        r = pkt.get("readings", {})
        table_rows.append({
            "Seq #": f"#{pkt.get('seq_num'):03d}",
            "Status": "✅ VALID" if pkt.get("is_valid") else "❌ CORRUPT",
            "Temp (°C)": f"{r.get('temperature_c', 0.0):.1f}",
            "Humidity (%)": f"{r.get('humidity_percent', 0.0):.1f}",
            "Pressure (hPa)": f"{r.get('pressure_hpa', 0.0):.1f}",
            "Rx CRC": pkt.get("received_crc"),
            "Calc CRC": pkt.get("computed_crc"),
            "Noise Field": pkt.get("corrupted_field") or "None"
        })
    df_history = pd.DataFrame(table_rows)
    st.dataframe(df_history, width="stretch", height=300)
else:
    st.write("No packet history recorded yet.")

# -----------------------------------------------------------------------------
# Auto-refresh loop
# -----------------------------------------------------------------------------
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
