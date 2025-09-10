import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, Flowable
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os

# -------------------------------------------------------
# PDF Creation with side-by-side charts
# -------------------------------------------------------
class SideBySideCharts(Flowable):
    """Flowable to place two images side by side in ReportLab"""
    def __init__(self, img1, img2, width=200, height=200, space=20):
        super().__init__()
        self.img1 = img1
        self.img2 = img2
        self.width = width
        self.height = height
        self.space = space

    def wrap(self, availWidth, availHeight):
        return availWidth, self.height

    def draw(self):
        self.canv.drawImage(self.img1, 0, 0, width=self.width, height=self.height)
        self.canv.drawImage(self.img2, self.width + self.space, 0, width=self.width, height=self.height)

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

    for client in df["Client"].unique():
        client_data = df[df["Client"] == client]

        elements.append(Paragraph(f"Client Report: {client}", styles['Title']))
        elements.append(Spacer(1, 12))

        # Summary table
        total_farmers = client_data["FarmerID"].nunique()
        fixed_devices = client_data[client_data["DeviceType"] == "Fixed"]["DeviceID"].nunique()
        portable_devices = client_data[client_data["DeviceType"] == "Portable"]["DeviceID"].nunique()

        table_data = [
            ["Metric", "Value"],
            ["Total Farmers", total_farmers],
            ["Fixed Devices", fixed_devices],
            ["Portable Devices", portable_devices],
        ]
        table = Table(table_data)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.grey),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        # Device Donut Chart
        device_counts = client_data["DeviceType"].value_counts()
        tmpfile_device = None
        if not device_counts.empty:
            fig, ax = plt.subplots()
            ax.pie(device_counts, labels=device_counts.index, autopct='%1.1f%%',
                   startangle=90, wedgeprops={'width':0.4})
            ax.set_title(f"{client} - Device Distribution")
            tmpfile_device = BytesIO()
            plt.savefig(tmpfile_device, format='png', bbox_inches='tight')
            plt.close(fig)
            tmpfile_device.seek(0)

        # Water Status Pie Chart
        status_counts = client_data["WaterStatus"].value_counts() if "WaterStatus" in client_data.columns else None
        tmpfile_status = None
        if status_counts is not None and not status_counts.empty:
            fig, ax = plt.subplots()
            ax.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%', startangle=90)
            ax.set_title(f"{client} - Water Status Distribution")
            tmpfile_status = BytesIO()
            plt.savefig(tmpfile_status, format='png', bbox_inches='tight')
            plt.close(fig)
            tmpfile_status.seek(0)

        # Place charts side by side if both exist
        if tmpfile_device and tmpfile_status:
            elements.append(SideBySideCharts(tmpfile_device, tmpfile_status, width=300, height=250, space=20))
        elif tmpfile_device:
            elements.append(Image(tmpfile_device, width=400, height=250))
        elif tmpfile_status:
            elements.append(Image(tmpfile_status, width=400, height=250))

        elements.append(Spacer(1, 24))
        elements.append(PageBreak())

    doc.build(elements)
    buffer.seek(0)
    return buffer

# -------------------------------------------------------
# Streamlit Dashboard
# -------------------------------------------------------
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
        return df
    else:
        st.error(f"CSV file '{file_path}' not found!")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("No data available. Please check your CSV file or filters.")
else:
    # Sidebar filters (default show all)
    st.sidebar.header("Filters")
    client_filter = st.sidebar.multiselect("Select Client(s)", options=df["Client"].unique(), default=[])
    state_filter = st.sidebar.multiselect("Select State(s)", options=df["State"].unique(), default=[])

    # If no filters selected, show all
    if not client_filter:
        client_filter = df["Client"].unique()
    if not state_filter:
        state_filter = df["State"].unique()

    # Apply filters
    df_filtered = df[(df["Client"].isin(client_filter)) & (df["State"].isin(state_filter))]

    if df_filtered.empty:
        st.warning("No data available for selected filters.")
    else:
        # KPIs
        st.subheader("📊 Key Metrics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Farmers", df_filtered["FarmerID"].nunique())
        col2.metric("Fixed Devices", df_filtered[df_filtered["DeviceType"] == "Fixed"]["DeviceID"].nunique())
        col3.metric("Portable Devices", df_filtered[df_filtered["DeviceType"] == "Portable"]["DeviceID"].nunique())

        # Water Status Pie
        st.subheader("📈 Water Status Distribution")
        if "WaterStatus" in df_filtered.columns:
            fig1 = px.pie(df_filtered, names="WaterStatus", title="Overall Water Status")
            st.plotly_chart(fig1, use_container_width=True)

        # Device Type Donut per client
        st.subheader("📊 Device Type Distribution per Client")
        if "DeviceType" in df_filtered.columns:
            device_counts = df_filtered.groupby("Client")["DeviceType"].value_counts().reset_index(name="Count")
            for client in df_filtered["Client"].unique():
                client_data = device_counts[device_counts["Client"] == client]
                fig = px.pie(client_data, names="DeviceType", values="Count",
                             title=f"{client} - Device Distribution", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)

        # Water Level Trend
        st.subheader("📉 Water Level Trend (Sample Device)")
        if "DeviceID" in df_filtered.columns and not df_filtered.empty:
            sample_device = df_filtered["DeviceID"].iloc[0]
            device_data = df_filtered[df_filtered["DeviceID"] == sample_device]
            if not device_data.empty and "Timestamp" in device_data.columns:
                fig2 = px.line(device_data, x="Timestamp", y="WaterLevel", title=f"Device {sample_device} - Water Level Trend")
                st.plotly_chart(fig2, use_container_width=True)

        # Map
        st.subheader("🗺️ Field Map")
        if {"Latitude", "Longitude"}.issubset(df_filtered.columns):
            df_filtered["Latitude"] = pd.to_numeric(df_filtered["Latitude"], errors='coerce')
            df_filtered["Longitude"] = pd.to_numeric(df_filtered["Longitude"], errors='coerce')
            df_map = df_filtered.dropna(subset=["Latitude", "Longitude"])
            if not df_map.empty:
                fig_map = px.scatter_mapbox(
                    df_map, lat="Latitude", lon="Longitude",
                    color="WaterStatus", hover_name="FarmerName",
                    zoom=5, height=500
                )
                fig_map.update_layout(mapbox_style="open-street-map")
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.warning("No valid coordinates available for mapping.")

        # Download PDF
        st.subheader("📥 Export Reports")
        pdf_buffer = create_multi_client_pdf(df_filtered)
        st.download_button(
            label="Download Client-wise PDF Report",
            data=pdf_buffer,
            file_name="iot_client_report.pdf",
            mime="application/pdf",
        )
