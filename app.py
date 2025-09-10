import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# -------------------------------------------------------
# PDF Creation (using Matplotlib instead of Plotly export)
# -------------------------------------------------------
def create_multi_client_pdf(df):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

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

        # Water status pie chart (Matplotlib)
        if "WaterStatus" in client_data.columns:
            status_counts = client_data["WaterStatus"].value_counts()
            fig, ax = plt.subplots()
            ax.pie(status_counts, labels=status_counts.index, autopct='%1.1f%%')
            ax.set_title(f"Water Status Distribution - {client}")
            tmpfile = BytesIO()
            plt.savefig(tmpfile, format='png')
            plt.close(fig)
            tmpfile.seek(0)
            elements.append(Image(tmpfile, width=300, height=200))
            elements.append(Spacer(1, 24))

        elements.append(PageBreak())

    doc.build(elements)
    buffer.seek(0)
    return buffer

# -------------------------------------------------------
# Streamlit Dashboard
# -------------------------------------------------------
st.set_page_config(page_title="IoT Paddy Field Dashboard", layout="wide")

# Add logo if available
try:
    st.image("logo.png", width=150)
except:
    st.write("")

st.title("🌾 IoT Paddy Field Monitoring Dashboard")

# Load data from repo CSV
@st.cache_data
def load_data():
    return pd.read_csv("iot_water_data_1.csv")

df = load_data()

# Sidebar filters
st.sidebar.header("Filters")
client_filter = st.sidebar.multiselect("Select Client(s)", options=df["Client"].unique(), default=df["Client"].unique())
state_filter = st.sidebar.multiselect("Select State(s)", options=df["State"].unique(), default=df["State"].unique())

# Apply filters
df_filtered = df[(df["Client"].isin(client_filter)) & (df["State"].isin(state_filter))]

# KPIs
st.subheader("📊 Key Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("Total Farmers", df_filtered["FarmerID"].nunique())
col2.metric("Fixed Devices", df_filtered[df_filtered["DeviceType"] == "Fixed"]["DeviceID"].nunique())
col3.metric("Portable Devices", df_filtered[df_filtered["DeviceType"] == "Portable"]["DeviceID"].nunique())

# Charts
st.subheader("📈 Water Status Distribution")
if "WaterStatus" in df_filtered.columns:
    fig1 = px.pie(df_filtered, names="WaterStatus", title="Overall Water Status")
    st.plotly_chart(fig1, use_container_width=True)

st.subheader("📉 Water Level Trend (Sample Device)")
if "DeviceID" in df_filtered.columns and not df_filtered.empty:
    sample_device = df_filtered["DeviceID"].iloc[0]
    device_data = df_filtered[df_filtered["DeviceID"] == sample_device]
    if not device_data.empty and "Timestamp" in device_data.columns:
        fig2 = px.line(device_data, x="Timestamp", y="WaterLevel", title=f"Device {sample_device} - Water Level Trend")
        st.plotly_chart(fig2, use_container_width=True)

st.subheader("🗺️ Field Map")
if {"Latitude", "Longitude"}.issubset(df_filtered.columns):
    fig3 = px.scatter_mapbox(
        df_filtered, lat="Latitude", lon="Longitude",
        color="WaterStatus", hover_name="FarmerName",
        zoom=5, height=500
    )
    fig3.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(fig3, use_container_width=True)

# Download PDF
st.subheader("📥 Export Reports")
pdf_buffer = create_multi_client_pdf(df_filtered)
st.download_button(
    label="Download Client-wise PDF Report",
    data=pdf_buffer,
    file_name="iot_client_report.pdf",
    mime="application/pdf",
)
