import streamlit as st
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet

# ---------------------------
# Utility: Save matplotlib fig to BytesIO for ReportLab
# ---------------------------
def fig_to_bytesio(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf

# ---------------------------
# Utility: Save plotly fig to BytesIO for ReportLab
# ---------------------------
def plotly_fig_to_bytesio(fig):
    buf = BytesIO()
    fig.write_image(buf, format="png")  # requires kaleido
    buf.seek(0)
    return buf

# ---------------------------
# PDF Export Function
# ---------------------------
def create_multi_client_pdf(df):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(800, 1000))
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("📊 Multi-Client IoT Water Report", styles["Title"]))
    elements.append(Spacer(1, 20))

    # Donut charts (Fixed & Portable) side by side
    fixed_counts = df[df['DeviceType'] == 'Fixed'].groupby('Client')['DeviceID'].nunique()
    portable_counts = df[df['DeviceType'] == 'Portable'].groupby('Client')['DeviceID'].nunique()

    if not fixed_counts.empty and not portable_counts.empty:
        fig, axes = plt.subplots(1, 2, figsize=(8, 4))
        axes[0].pie(fixed_counts, labels=fixed_counts.index, autopct='%1.1f%%',
                    startangle=90, wedgeprops={'width': 0.4})
        axes[0].set_title("Fixed Devices per Client")
        axes[1].pie(portable_counts, labels=portable_counts.index, autopct='%1.1f%%',
                    startangle=90, wedgeprops={'width': 0.4})
        axes[1].set_title("Portable Devices per Client")
        elements.append(RLImage(fig_to_bytesio(fig), width=500, height=250))
        elements.append(Spacer(1, 20))

    # Client-wise Water Level Trend (one sample device per client)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    sample_trend = pd.DataFrame()

    for client in df["Client"].unique():
        client_devices = df[df["Client"] == client]["DeviceID"].unique()
        if len(client_devices) > 0:
            sample_device = client_devices[0]  # pick first device
            device_data = df[df["DeviceID"] == sample_device]
            sample_trend = pd.concat([sample_trend, device_data])

    if not sample_trend.empty:
        fig = px.line(sample_trend, x="Timestamp", y="WaterLevel",
                      color="Client", line_group="DeviceID",
                      title="Client-wise Sample Device Water Level Trend")
        fig.update_layout(template="plotly_white")
        elements.append(RLImage(plotly_fig_to_bytesio(fig), width=500, height=250))
        elements.append(Spacer(1, 20))

    doc.build(elements)
    buf.seek(0)
    return buf

# ---------------------------
# Streamlit App
# ---------------------------
st.set_page_config(page_title="IoT Water Dashboard", layout="wide")

# Load data
df = pd.read_csv("iot_water_data_1.csv")
df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

# Sidebar Filters
st.sidebar.header("🔍 Filters")
client_filter = st.sidebar.multiselect("Select Client(s)", options=df["Client"].unique())
district_filter = st.sidebar.multiselect("Select District(s)", options=df["District"].unique())
village_filter = st.sidebar.multiselect("Select Village(s)", options=df["Village"].unique())
date_range = st.sidebar.date_input("Select Date Range", [df["Timestamp"].min(), df["Timestamp"].max()])

# Apply filters
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

# Client-wise Sample Device Water Level Trend
st.subheader("📈 Client-wise Sample Device Water Level Trend")
sample_trend = pd.DataFrame()

for client in df_filtered["Client"].unique():
    client_devices = df_filtered[df_filtered["Client"] == client]["DeviceID"].unique()
    if len(client_devices) > 0:
        sample_device = client_devices[0]  # pick first device
        device_data = df_filtered[df_filtered["DeviceID"] == sample_device]
        sample_trend = pd.concat([sample_trend, device_data])

if not sample_trend.empty:
    fig = px.line(sample_trend, x="Timestamp", y="WaterLevel",
                  color="Client", line_group="DeviceID",
                  title="Client-wise Sample Device Water Level Trend")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No data available for selected filters.")

# ---------------------------
# Export Section
# ---------------------------
st.subheader("📥 Export Reports")
pdf_buffer = create_multi_client_pdf(df_filtered)
st.download_button(
    label="Download Client-wise PDF Report",
    data=pdf_buffer,
    file_name="client_report.pdf",
    mime="application/pdf"
)
