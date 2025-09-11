import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os

# ---------------- PDF Helper ----------------
def fig_to_bytesio(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

# ---------------- PDF Export ----------------
def create_multi_client_pdf(df):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    if df.empty:
        elements.append(Paragraph("No data available for the selected filters.", styles['Title']))
        doc.build(elements)
        buffer.seek(0)
        return buffer

    # Summary table
    total_farmers = df["FarmerID"].nunique()
    fixed_devices_total = df[df["DeviceType"]=="Fixed"]["DeviceID"].nunique()
    portable_devices_total = df[df["DeviceType"]=="Portable"]["DeviceID"].nunique()

    elements.append(Paragraph("IoT Paddy Field Dashboard Report", styles['Title']))
    elements.append(Spacer(1,12))
    table_data = [
        ["Metric","Value"],
        ["Total Farmers", total_farmers],
        ["Total Fixed Devices", fixed_devices_total],
        ["Total Portable Devices", portable_devices_total]
    ]
    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
    ]))
    elements.append(table)
    elements.append(Spacer(1,24))

    # Device Type Donuts side by side
    fixed_counts = df[df["DeviceType"]=="Fixed"].groupby("Client")["DeviceID"].nunique()
    portable_counts = df[df["DeviceType"]=="Portable"].groupby("Client")["DeviceID"].nunique()
   
    if not fixed_counts.empty or not portable_counts.empty:
        imgs = []
        if not fixed_counts.empty:
            fig, ax = plt.subplots()
            ax.pie(fixed_counts, labels=fixed_counts.index, autopct='%1.1f%%', startangle=90, wedgeprops={'width':0.4})
            ax.set_title("Fixed Devices per Client")
            imgs.append(RLImage(fig_to_bytesio(fig), width=300, height=250))
        else:
            imgs.append(Spacer(300,250))

        if not portable_counts.empty:
            fig, ax = plt.subplots()
            ax.pie(portable_counts, labels=portable_counts.index, autopct='%1.1f%%', startangle=90, wedgeprops={'width':0.4})
            ax.set_title("Portable Devices per Client")
            imgs.append(RLImage(fig_to_bytesio(fig), width=300, height=250))
        else:
            imgs.append(Spacer(300,250))

        # Side by side table
        table_side_by_side = Table([imgs], colWidths=[300,300])
        table_side_by_side.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER")]))
        elements.append(table_side_by_side)
        elements.append(Spacer(1,24))

    # Water Status Pie
    if "WaterStatus" in df.columns:
        status_counts = df["WaterStatus"].value_counts()
        if not status_counts.empty:
            fig, ax = plt.subplots()
            ax.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', startangle=90)
            ax.set_title("Water Status Distribution")
            elements.append(RLImage(fig_to_bytesio(fig), width=400, height=250))

    elements.append(PageBreak())
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ---------------- Streamlit ----------------
st.set_page_config(page_title="IoT Paddy Field Dashboard", layout="wide")

# Logo
if os.path.exists("logo.png"):
    st.image("logo.png", width=150)

st.title("🌾 IoT Paddy Field Monitoring Dashboard")

# Load CSV
@st.cache_data
def load_data():
    file_path = "iot_water_data_1.csv"
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if "Timestamp" in df.columns:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors='coerce')
        if "Latitude" in df.columns:
            df["Latitude"] = pd.to_numeric(df["Latitude"], errors='coerce')
        if "Longitude" in df.columns:
            df["Longitude"] = pd.to_numeric(df["Longitude"], errors='coerce')
        return df
    else:
        st.error(f"CSV file '{file_path}' not found!")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("No data available. Please check your CSV file.")
else:
    # Filters
    st.sidebar.header("Filters")
    client_filter = st.sidebar.multiselect("Select Client(s)", options=df["Client"].unique(), default=[])
    state_filter = st.sidebar.multiselect("Select State(s)", options=df["State"].unique(), default=[])
    district_filter = st.sidebar.multiselect("Select District(s)", options=df["District"].unique(), default=[])
    village_filter = st.sidebar.multiselect("Select Village(s)", options=df["Village"].unique(), default=[])
    
    if not client_filter:
        client_filter = df["Client"].unique()
    if not state_filter:
        state_filter = df["State"].unique()
    if not district_filter:
        district_filter = df["District"].unique()
    if not village_filter:
        village_filter = df["Village").unique()

    df_filtered = df[(df["Client"].isin(client_filter)) & (df["State"].isin(state_filter)) & (df["District"].isin(district_filter)) & (df["Village"].isin(village_filter))]

    if df_filtered.empty:
        st.warning("No data available for selected filters.")
    else:
        # KPIs
        st.subheader("📊 Key Metrics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Farmers", df_filtered["FarmerID"].nunique())
        col2.metric("Fixed Devices", df_filtered[df_filtered["DeviceType"]=="Fixed"]["DeviceID"].nunique())
        col3.metric("Portable Devices", df_filtered[df_filtered["DeviceType"]=="Portable"]["DeviceID"].nunique())

        # Water Status Pie
        st.subheader("📈 Water Status Distribution")
        if "WaterStatus" in df_filtered.columns:
            fig1 = px.pie(df_filtered, names="WaterStatus", title="Overall Water Status")
            st.plotly_chart(fig1, use_container_width=True)

        # Device Type Donuts
        st.subheader("📊 Device Type Distribution per Client")
        fixed_counts = df_filtered[df_filtered["DeviceType"]=="Fixed"].groupby("Client")["DeviceID"].nunique()
        portable_counts = df_filtered[df_filtered["DeviceType"]=="Portable"].groupby("Client")["DeviceID"].nunique()
        if not fixed_counts.empty:
            fig = px.pie(values=fixed_counts.values, names=fixed_counts.index, hole=0.4, title="Fixed Devices per Client")
            st.plotly_chart(fig, use_container_width=True)
        if not portable_counts.empty:
            fig = px.pie(values=portable_counts.values, names=portable_counts.index, hole=0.4, title="Portable Devices per Client")
            st.plotly_chart(fig, use_container_width=True)

        # Water Level Trend (sample device)
        st.subheader("📉 Water Level Trend (Sample Device)")
        if "DeviceID" in df_filtered.columns:
            sample_device = df_filtered["DeviceID"].iloc[0]
            device_data = df_filtered[df_filtered["DeviceID"]==sample_device]
            if not device_data.empty and "Timestamp" in device_data.columns:
                fig2 = px.line(device_data, x="Timestamp", y="WaterLevel", title=f"Device {sample_device} - Water Level Trend")
                st.plotly_chart(fig2, use_container_width=True)

        # Map
        st.subheader("🗺️ Field Map")
        if {"Latitude","Longitude"}.issubset(df_filtered.columns):
            df_map = df_filtered.dropna(subset=["Latitude","Longitude"])
            if not df_map.empty:
                center_lat = df_map["Latitude"].mean()
                center_lon = df_map["Longitude"].mean()
                fig_map = px.scatter_mapbox(
                    df_map, lat="Latitude", lon="Longitude",
                    color="WaterStatus", hover_name="FarmerName",
                    zoom=10, height=500
                )
                fig_map.update_layout(mapbox_style="open-street-map")
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.warning("No valid coordinates for mapping.")

        # Download PDF
        st.subheader("📥 Export Reports")
        pdf_buffer = create_multi_client_pdf(df_filtered)
        st.download_button(
            label="Download Client-wise PDF Report",
            data=pdf_buffer,
            file_name="iot_client_report.pdf",
            mime="application/pdf",
        )
