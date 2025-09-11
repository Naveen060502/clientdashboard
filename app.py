import streamlit as st
import pandas as pd
import plotly.express as px

# ---------------------------
# Page Config
# ---------------------------
st.set_page_config(page_title="💧 IoT Water Dashboard", layout="wide")

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
# Sidebar: User Info & Logout
# ---------------------------
st.sidebar.success(f"👤 Logged in as {st.session_state.role.upper()}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.client_name = None
    st.rerun()

# ---------------------------
# Load Data
# ---------------------------
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
    village_filter = st.sidebar.multiselect("Select Village(s)", options=df["Village"].unique())
    date_range = st.sidebar.date_input("Select Date Range", [df["Timestamp"].min(), df["Timestamp"].max()])

    df_filtered = df.copy()
    if client_filter:
        df_filtered = df_filtered[df_filtered["Client"].isin(client_filter)]
    if district_filter:
        df_filtered = df_filtered[df_filtered["District"].isin(district_filter)]
    if village_filter:
        df_filtered = df_filtered[df_filtered["Village"].isin(village_filter)]
    if len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df_filtered[(df_filtered["Timestamp"] >= pd.to_datetime(start_date)) &
                                  (df_filtered["Timestamp"] <= pd.to_datetime(end_date))]
else:
    df_filtered = df.copy()

# ---------------------------
# Dashboard Layout
# ---------------------------
st.title("💧 IoT Water Dashboard")

# Device Distribution
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

# Devices by District
st.subheader("🏙️ Devices per District")
district_counts = df_filtered.groupby("District")["DeviceID"].nunique().reset_index()
if not district_counts.empty:
    fig = px.bar(district_counts, x="District", y="DeviceID", title="Device Count per District", text="DeviceID")
    st.plotly_chart(fig, use_container_width=True)

# Devices by Village
st.subheader("🏘️ Devices per Village")
village_counts = df_filtered.groupby("Village")["DeviceID"].nunique().reset_index()
if not village_counts.empty:
    fig = px.bar(village_counts, x="Village", y="DeviceID", title="Device Count per Village", text="DeviceID")
    st.plotly_chart(fig, use_container_width=True)

# Daily Average Water Level Trend
st.subheader("📈 Client-wise Daily Average Water Level Trend")
df_filtered["Date"] = df_filtered["Timestamp"].dt.date  # Extract only the date
daily_avg = df_filtered.groupby(["Date", "Client"])["WaterLevel"].mean().reset_index()
if not daily_avg.empty:
    fig = px.line(daily_avg, x="Date", y="WaterLevel", color="Client",
                  title="Daily Average Water Level Trend")
    st.plotly_chart(fig, use_container_width=True)

# Sample Device Trend
st.subheader("📊 Sample Device Water Level Trend (per Client)")
sample_trend = pd.DataFrame()
for client in df_filtered["Client"].unique():
    client_devices = df_filtered[df_filtered["Client"] == client]["DeviceID"].unique()
    if len(client_devices) > 0:
        sample_device = client_devices[0]
        device_data = df_filtered[df_filtered["DeviceID"] == sample_device]
        sample_trend = pd.concat([sample_trend, device_data])

if not sample_trend.empty:
    fig = px.line(sample_trend, x="Timestamp", y="WaterLevel",
                  color="Client", line_group="DeviceID",
                  title="Client-wise Sample Device Water Level Trend")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# NEW CHART: Portable Sensor – Client-wise Data Collection
# ---------------------------
st.subheader("📦 Portable Sensor Data Collection (Client-wise)")
portable_data = df_filtered[df_filtered["DeviceType"] == "Portable"].groupby("Client")["WaterLevel"].count().reset_index()
portable_data.rename(columns={"WaterLevel": "Readings"}, inplace=True)
if not portable_data.empty:
    fig = px.bar(portable_data, x="Client", y="Readings", text="Readings",
                 title="Portable Sensor Readings per Client", color="Client")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# NEW CHART: Field Officer-wise Data Collection
# ---------------------------
if "FieldOfficer" in df_filtered.columns:
    st.subheader("🧑‍🌾 Field Officer-wise Data Collection")
    officer_data = df_filtered.groupby("FieldOfficer")["WaterLevel"].count().reset_index()
    officer_data.rename(columns={"WaterLevel": "Readings"}, inplace=True)
    if not officer_data.empty:
        fig = px.bar(officer_data, x="FieldOfficer", y="Readings", text="Readings",
                     title="Data Collection by Field Officers", color="FieldOfficer")
        st.plotly_chart(fig, use_container_width=True)

# Map: Device Locations
st.subheader("🗺️ Device Map")
if {"Latitude", "Longitude"}.issubset(df_filtered.columns):
    fig = px.scatter_mapbox(df_filtered, lat="Latitude", lon="Longitude",
                            color="Client", hover_name="DeviceID",
                            zoom=5, height=500)
    fig.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No latitude/longitude data available for mapping.")
