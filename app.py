import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

# ---------------------------
# Dummy credentials
# ---------------------------
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "clientA": {"password": "client123", "role": "client", "client_name": "ClientA"},
    "clientB": {"password": "client123", "role": "client", "client_name": "ClientB"},
}

# ---------------------------
# Session state login check
# ---------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None
if "client_name" not in st.session_state:
    st.session_state.client_name = None

# ---------------------------
# Login form
# ---------------------------
if not st.session_state.logged_in:
    st.set_page_config(page_title="IoT Water Dashboard", layout="wide")
    st.title("🔐 IoT Water Dashboard Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = USERS.get(username)
        if user and user["password"] == password:
            st.session_state.logged_in = True
            st.session_state.role = user["role"]
            if user["role"] == "client":
                st.session_state.client_name = user["client_name"]
            st.success("✅ Login successful")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")
    st.stop()

# ---------------------------
# Dashboard after login
# ---------------------------
st.set_page_config(page_title="IoT Water Dashboard", layout="wide")

# ---------------------------
# Logo based on login
# ---------------------------
logo_map = {
    "admin": "logo.png",
    "ClientA": "logo_clientA.png",
    "ClientB": "logo_clientB.png",
}

client_name = st.session_state.client_name if st.session_state.client_name else "admin"
logo_path = logo_map.get(client_name, "logo_admin.png")

# Sidebar logo (sticky)
st.sidebar.image(logo_path, use_container_width=False, width=120)
st.sidebar.success(f"Logged in as {st.session_state.role.upper()}")

# Centered logo at top
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image(logo_path, use_container_width=False, width=180)

# Logout
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.client_name = None
    st.rerun()

# Load data
df = pd.read_csv("iot_water_data_1.csv")
df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

# ---------------------------
# Role-based filtering
# ---------------------------
if st.session_state.role == "client":
    df = df[df["Client"] == st.session_state.client_name]

# ---------------------------
# Sidebar Filters (admin only)
# ---------------------------
if st.session_state.role == "admin":
    st.sidebar.header("🔍 Filters")
    client_filter = st.sidebar.multiselect("Select Client(s)", options=df["Client"].unique())
    district_filter = st.sidebar.multiselect("Select District(s)", options=df["District"].unique())

    # Fixed date range (2025-04-20 → today)
    today = date.today()
    start_date = date(2025, 4, 20)
    date_range = st.sidebar.date_input(
        "Select Date Range",
        [start_date, today],
        min_value=start_date,
        max_value=today
    )

    df_filtered = df.copy()
    if client_filter:
        df_filtered = df_filtered[df_filtered["Client"].isin(client_filter)]
    if district_filter:
        df_filtered = df_filtered[df_filtered["District"].isin(district_filter)]
    if len(date_range) == 2:
        start, end = date_range
        df_filtered = df_filtered[
            (df_filtered["Timestamp"] >= pd.to_datetime(start)) &
            (df_filtered["Timestamp"] <= pd.to_datetime(end))
        ]
else:
    today = date.today()
    start_date = date(2025, 4, 20)
    df_filtered = df[
        (df["Timestamp"] >= pd.to_datetime(start_date)) &
        (df["Timestamp"] <= pd.to_datetime(today))
    ]

# ---------------------------
# Dashboard Layout
# ---------------------------
st.title("💧 IoT Water Dashboard")

# Donut charts: Device Type Distribution
col1, col2 = st.columns(2)

with col1:
    fixed_counts = df_filtered[df_filtered['DeviceType'] == 'Fixed'].groupby('Client')['DeviceID'].nunique()
    if not fixed_counts.empty:
        fig = px.pie(fixed_counts, values=fixed_counts.values, names=fixed_counts.index,
                     title="Fixed Devices per Client", hole=0.5)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    portable_counts = df_filtered[df_filtered['DeviceType'] == 'Portable'].groupby('Client')['DeviceID'].nunique()
    if not portable_counts.empty:
        fig = px.pie(portable_counts, values=portable_counts.values, names=portable_counts.index,
                     title="Portable Devices per Client", hole=0.5)
        st.plotly_chart(fig, use_container_width=True)

# Bar chart: Devices by District
st.subheader("🏙️ Devices per District")
district_counts = df_filtered.groupby("District")["DeviceID"].nunique().reset_index()
if not district_counts.empty:
    fig = px.bar(district_counts, x="District", y="DeviceID", title="Device Count per District", text="DeviceID")
    st.plotly_chart(fig, use_container_width=True)

# Water Level Trend: Client-wise Daily Average
st.subheader("📈 Client-wise Daily Average Water Level Trend")
daily_avg = df_filtered.groupby([df_filtered["Timestamp"].dt.date, "Client"])["WaterLevel"].mean().reset_index()
daily_avg.rename(columns={"Timestamp": "Date"}, inplace=True)
if not daily_avg.empty:
    fig = px.line(daily_avg, x="Date", y="WaterLevel", color="Client",
                  title="Daily Average Water Level Trend")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# Portable Device Charts
# ---------------------------
portable_df = df_filtered[df_filtered["DeviceType"] == "Portable"]

if not portable_df.empty:
    # Client-wise Portable Data Collection
    st.subheader("📊 Portable Devices - Client-wise Data Collection")
    client_collection = portable_df.groupby("Client")["DeviceID"].count().reset_index()
    fig = px.bar(client_collection, x="Client", y="DeviceID", text="DeviceID",
                 title="Portable Devices - Client-wise Data Collection")
    st.plotly_chart(fig, use_container_width=True)

    # Field Officer-wise Portable Data Collection
    if "FieldOfficer" in portable_df.columns:
        st.subheader("👨‍💼 Portable Devices - Field Officer-wise Data Collection")
        officer_collection = portable_df.groupby("FieldOfficer")["DeviceID"].count().reset_index()
        fig = px.bar(officer_collection, x="FieldOfficer", y="DeviceID", text="DeviceID",
                     title="Portable Devices - Field Officer-wise Data Collection")
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# Map: Device Locations
# ---------------------------
st.subheader("🗺️ Device Map (Punjab, India)")
if {"Latitude", "Longitude"}.issubset(df_filtered.columns):
    fig = px.scatter_mapbox(
        df_filtered,
        lat="Latitude",
        lon="Longitude",
        color="Client",
        hover_name="DeviceID",
        zoom=6,
        height=500
    )
    # Center map on Punjab
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_center={"lat": 30.7333, "lon": 76.7794},
        mapbox_zoom=6
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No latitude/longitude data available for mapping.")
