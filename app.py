import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import tempfile

# -------------------
# Load Data
# -------------------
@st.cache_data
def load_data():
    df = pd.read_csv("iot_water_data_1.csv")  # your IoT data file
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    return df

data = load_data()

# -------------------
# Sidebar Filters
# -------------------
st.sidebar.header("Filters")
client = st.sidebar.selectbox("Select Client", options=["All"] + sorted(data["Client"].unique()))
state = st.sidebar.selectbox("Select State", options=["All"] + sorted(data["State"].unique()))
device_type = st.sidebar.multiselect("Device Type", options=data["DeviceType"].unique(), default=data["DeviceType"].unique())

# Apply filters
df = data.copy()
if client != "All":
    df = df[df["Client"] == client]
if state != "All":
    df = df[df["State"] == state]
if device_type:
    df = df[df["DeviceType"].isin(device_type)]

st.title("🌾 IoT Paddy Field Monitoring Dashboard – Multi-Client Report")

# -------------------
# PDF Export Function
# -------------------
def create_multi_client_pdf(dataframe):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle("Title", fontSize=22, textColor=colors.HexColor("#1a4d2e"), alignment=1, spaceAfter=20)
    subtitle_style = ParagraphStyle("Subtitle", fontSize=14, textColor=colors.HexColor("#444444"), alignment=1, spaceAfter=20)
    header_style = ParagraphStyle("Header", fontSize=14, textColor=colors.HexColor("#2e86ab"), spaceAfter=10, spaceBefore=10)

    story = []

    # --- Cover Page ---
    try:
        story.append(Image("logo.png", width=120, height=50))  # Replace with your logo
    except:
        pass
    story.append(Spacer(1, 60))
    story.append(Paragraph("🌾 IoT Paddy Field Monitoring Report", title_style))
    story.append(Paragraph("📑 Client-wise Insights", subtitle_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Report Generated On: {datetime.now().strftime('%d %B %Y, %I:%M %p')}", styles["Normal"]))
    story.append(Spacer(1, 300))
    story.append(Paragraph("Prepared by: Analytics Team", styles["Italic"]))
    story.append(PageBreak())

    # --- Loop through Clients ---
    clients = dataframe["Client"].unique()
    for i, client_name in enumerate(clients):
        client_df = dataframe[dataframe["Client"] == client_name]

        story.append(Paragraph(f"🌾 IoT Report – {client_name}", title_style))
        story.append(Spacer(1, 12))

        # Executive Summary
        story.append(Paragraph("📌 Executive Summary", header_style))
        summary_data = [
            ["Total Farmers", client_df["FarmerID"].nunique()],
            ["Fixed Devices", sum(client_df["DeviceType"]=="Fixed")],
            ["Portable Devices", sum(client_df["DeviceType"]=="Portable")]
        ]
        summary_table = Table(summary_data, colWidths=[200, 200])
        summary_table.setStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#cce5ff")),
                                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                                ("GRID", (0,0), (-1,-1), 0.5, colors.grey)])
        story.append(summary_table)
        story.append(Spacer(1, 24))

        # Device Insights
        if not client_df.empty:
            story.append(Paragraph("📊 Device Insights", header_style))

            # Pie chart
            status_counts = client_df["WaterStatus"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig_pie = px.pie(status_counts, values="Count", names="Status", title="Field Water Status")

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_pie:
                fig_pie.write_image(tmp_pie.name, format="png")
                story.append(Image(tmp_pie.name, width=400, height=250))
            story.append(Spacer(1, 12))

            # Line chart (pick one device)
            if "DeviceID" in client_df and not client_df["DeviceID"].empty:
                sample_device = client_df["DeviceID"].iloc[0]
                device_data = client_df[client_df["DeviceID"] == sample_device]
                fig_line = px.line(device_data, x="Timestamp", y="WaterLevel", color="DeviceType",
                                   title=f"Water Level Trend – Device {sample_device}")
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_line:
                    fig_line.write_image(tmp_line.name, format="png")
                    story.append(Image(tmp_line.name, width=400, height=250))
                story.append(Spacer(1, 24))

        # Farmer Insights
        story.append(Paragraph("👨‍🌾 Farmer Insights", header_style))
        if not client_df.empty:
            status_summary = client_df["WaterStatus"].value_counts().reset_index()
            status_summary.columns = ["Status", "Count"]
            table_data = [["Status", "Count"]] + status_summary.values.tolist()
            table = Table(table_data, colWidths=[200, 200])
            table.setStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#d4edda")),
                            ("ALIGN", (0,0), (-1,-1), "CENTER"),
                            ("GRID", (0,0), (-1,-1), 0.5, colors.grey)])
            story.append(table)
        else:
            story.append(Paragraph("No farmer data available for this client.", styles["Normal"]))
        story.append(Spacer(1, 24))

        # Map
        if {"Latitude", "Longitude"}.issubset(client_df.columns) and not client_df.empty:
            story.append(Paragraph("🗺️ Field Locations", header_style))
            fig_map = px.scatter_mapbox(
                client_df,
                lat="Latitude",
                lon="Longitude",
                color="WaterStatus",
                hover_name="FarmerName",
                zoom=5,
                mapbox_style="open-street-map"
            )
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_map:
                fig_map.write_image(tmp_map.name, format="png")
                story.append(Image(tmp_map.name, width=400, height=250))
            story.append(Spacer(1, 24))

        if i < len(clients) - 1:
            story.append(PageBreak())

    # --- Final Summary Page ---
    story.append(PageBreak())
    story.append(Paragraph("📊 Final Summary – All Clients Combined", title_style))
    story.append(Spacer(1, 20))

    # Summary metrics
    total_summary = [
        ["Total Clients", dataframe["Client"].nunique()],
        ["Total Farmers", dataframe["FarmerID"].nunique()],
        ["Fixed Devices", sum(dataframe["DeviceType"]=="Fixed")],
        ["Portable Devices", sum(dataframe["DeviceType"]=="Portable")]
    ]
    total_table = Table(total_summary, colWidths=[200, 200])
    total_table.setStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f8d7da")),
                          ("ALIGN", (0,0), (-1,-1), "CENTER"),
                          ("GRID", (0,0), (-1,-1), 0.5, colors.grey)])
    story.append(total_table)
    story.append(Spacer(1, 24))

    # Overall water status pie
    status_counts_all = dataframe["WaterStatus"].value_counts().reset_index()
    status_counts_all.columns = ["Status", "Count"]
    fig_all = px.pie(status_counts_all, values="Count", names="Status", title="Overall Water Status Across Clients")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_all:
        fig_all.write_image(tmp_all.name, format="png")
        story.append(Image(tmp_all.name, width=400, height=250))
    story.append(Spacer(1, 24))

    # Trend chart across time (all devices combined)
    if "Timestamp" in dataframe.columns:
        df_trend = dataframe.copy()
        df_trend["Date"] = df_trend["Timestamp"].dt.date
        trend_counts = df_trend.groupby(["Date", "WaterStatus"]).size().reset_index(name="Count")

        fig_trend = px.line(trend_counts, x="Date", y="Count", color="WaterStatus",
                            title="Water Status Trends Over Time (All Clients)")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_trend:
            fig_trend.write_image(tmp_trend.name, format="png")
            story.append(Image(tmp_trend.name, width=400, height=250))
        story.append(Spacer(1, 24))

    # Top 5 clients by Dry risk
    risk_df = dataframe.groupby("Client")["WaterStatus"].value_counts(normalize=True).unstack().fillna(0)
    if "Dry" in risk_df.columns:
        risk_df["Dry_Percentage"] = (risk_df["Dry"] * 100).round(2)
        top5_risk = risk_df.sort_values("Dry_Percentage", ascending=False).head(5).reset_index()

        fig_risk = px.bar(top5_risk, x="Client", y="Dry_Percentage", text="Dry_Percentage",
                          title="Top 5 Clients by Dry Field Risk (%)", color="Dry_Percentage", color_continuous_scale="Reds")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_risk:
            fig_risk.write_image(tmp_risk.name, format="png")
            story.append(Image(tmp_risk.name, width=400, height=250))
        story.append(Spacer(1, 24))

    doc.build(story)
    buffer.seek(0)
    return buffer

# -------------------
# Download Button
# -------------------
if st.button("📥 Download All Clients Report as PDF"):
    pdf_buffer = create_multi_client_pdf(df)
    st.download_button(
        label="Download Multi-Client PDF",
        data=pdf_buffer,
        file_name="All_Clients_IoT_Report.pdf",
        mime="application/pdf"
    )
