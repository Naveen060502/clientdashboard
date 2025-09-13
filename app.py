
import os
from datetime import date, datetime, timedelta, timezone
import uuid
import json

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# =====================================
# --------- Config & Constants --------
# =====================================
st.set_page_config(
    page_title="IoT Water Dashboard",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

FAST_LIMIT_ROWS = 300_000
DEFAULT_STATUS_HOURS = 24
SEASON_LABEL = "Kharif - 2025"

# =====================================
# --------- Dummy Credentials ---------
# =====================================
USERS = {
    "admin": {"password": "admin123", "role": "admin", "client_name": "admin"},
    "AVPN": {"password": "avpn123", "role": "client", "client_name": "AVPN"},
    "CIPT": {"password": "cipt123", "role": "client", "client_name": "CIPT"},
    "Titan": {"password": "titan123", "role": "client", "client_name": "Titan"},
}

FEEDBACK_FILE = "feedbacks.csv"
FEEDBACK_DIR = "feedback_history"

# =====================================
# --------- Session State -------------
# =====================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "role" not in st.session_state:
    st.session_state.role = None
if "client_name" not in st.session_state:
    st.session_state.client_name = None

def do_login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state.authenticated = True
            st.session_state.role = USERS[username]["role"]
            st.session_state.client_name = USERS[username]["client_name"]
            st.success("✅ Login successful")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")

def do_logout():
    st.session_state.authenticated = False
    st.session_state.role = None
    st.session_state.client_name = None
    st.rerun()

if not st.session_state.authenticated:
    do_login()
    st.stop()

client_name = st.session_state.client_name

# =====================================
# -------------- Sidebar --------------
# =====================================
st.sidebar.success(f"Logged in as **{st.session_state.role.upper()}** ({client_name})")
if st.sidebar.button("Logout"):
    do_logout()

# Logos
logo_map = {"admin": "logo.png", "AVPN": "AVPN_logo.png", "CIPT": "CIPT_LOGO.png", "Titan": "titan.png"}
admin_logo = "logo.png"
client_logo = logo_map.get(client_name, "logo.png")
if os.path.exists(client_logo):
    st.sidebar.image(client_logo, width=140)

# =====================================
# -------------- Data -----------------
# =====================================
@st.cache_data(show_spinner=False)
def load_data(csv_path: str = "iot_water_data_1.csv") -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_path, engine="python", sep=None)
    except Exception:
        df = pd.read_csv(csv_path)

    if "Timestamp" in df.columns:
        try:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True, errors="raise")
        except Exception:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True, dayfirst=True, errors="coerce")
    else:
        df["Timestamp"] = pd.NaT

    default_cols = {"Client": np.nan, "District": np.nan, "DeviceID": np.nan,
                    "DeviceType": np.nan, "FarmerName": np.nan, "WaterLevel": np.nan}
    for c, val in default_cols.items():
        if c not in df.columns:
            df[c] = val

    for c in ["Client","District","DeviceID","DeviceType","FarmerName"]:
        try:
            df[c] = df[c].astype("category")
        except Exception:
            pass

    for c in ["Latitude","Longitude"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

df = load_data()

def ist(dt_series: pd.Series) -> pd.Series:
    try:
        if dt_series.dt.tz is None:
            return dt_series.dt.tz_localize("Asia/Kolkata")
        return dt_series.dt.tz_convert("Asia/Kolkata")
    except Exception:
        s = pd.to_datetime(dt_series, errors="coerce")
        return s.dt.tz_localize("Asia/Kolkata")

row_count = len(df)
fast_mode = row_count > FAST_LIMIT_ROWS
if fast_mode:
    st.sidebar.warning(f"Fast mode ON: dataset has {row_count:,} rows; charts use aggregated views.")

# =====================================
# -------------- Filters --------------
# =====================================
st.sidebar.header("🔍 Filters")

min_ts = pd.to_datetime(df["Timestamp"]).min()
max_ts = pd.to_datetime(df["Timestamp"]).max()
if pd.isna(min_ts) or pd.isna(max_ts):
    min_ts = pd.Timestamp(date.today() - timedelta(days=30), tz="UTC")
    max_ts = pd.Timestamp(date.today(), tz="UTC")

default_start = (max_ts - pd.Timedelta(days=30)).date()
default_end = max_ts.date()

date_range = st.sidebar.date_input(
    "Select Date Range",
    [default_start, default_end],
    min_value=min_ts.date(),
    max_value=max_ts.date()
)

working = df.copy()
if st.session_state.role == "client":
    working = working[working["Client"] == client_name]

if st.session_state.role == "admin":
    client_opts = sorted([c for c in working["Client"].dropna().unique().tolist()])
    district_opts = sorted([c for c in working["District"].dropna().unique().tolist()])
    dtype_opts = sorted([c for c in working["DeviceType"].dropna().unique().tolist()])

    client_sel = st.sidebar.multiselect("Client(s)", client_opts)
    district_sel = st.sidebar.multiselect("District(s)", district_opts)
    dtype_sel = st.sidebar.multiselect("Device Type(s)", dtype_opts)

    if client_sel:
        working = working[working["Client"].isin(client_sel)]
    if district_sel:
        working = working[working["District"].isin(district_sel)]
    if dtype_sel:
        working = working[working["DeviceType"].isin(dtype_sel)]
else:
    district_opts = sorted([c for c in working["District"].dropna().unique().tolist()])
    dtype_opts = sorted([c for c in working["DeviceType"].dropna().unique().tolist()])
    farmer_opts = sorted([c for c in working["FarmerName"].dropna().unique().tolist()])
    device_opts = sorted([c for c in working["DeviceID"].dropna().unique().tolist()])
    district_sel = st.sidebar.multiselect("District(s)", district_opts)
    dtype_sel = st.sidebar.multiselect("Device Type(s)", dtype_opts)
    farmer_sel = st.sidebar.multiselect("Farmer(s)", farmer_opts)
    device_sel = st.sidebar.multiselect("Device(s)", device_opts)
    if district_sel:
        working = working[working["District"].isin(district_sel)]
    if dtype_sel:
        working = working[working["DeviceType"].isin(dtype_sel)]
    if farmer_sel:
        working = working[working["FarmerName"].isin(farmer_sel)]
    if device_sel:
        working = working[working["DeviceID"].isin(device_sel)]

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = date_range
    start_utc = pd.Timestamp(start).tz_localize("Asia/Kolkata").tz_convert("UTC")
    end_utc = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    end_utc = end_utc.tz_localize("Asia/Kolkata").tz_convert("UTC")
    working = working[(pd.to_datetime(working["Timestamp"]) >= start_utc) & (pd.to_datetime(working["Timestamp"]) <= end_utc)]

# =====================================
# ---------- Helper functions ---------
# =====================================
def show_top_header():
    c1, c2, c3 = st.columns([1,4,1])
    with c1:
        if os.path.exists(admin_logo):
            st.image(admin_logo, width=70)
    with c2:
        st.markdown("## cultYvate Kharif 2025 Summary Report")
    with c3:
        if os.path.exists(client_logo) and client_logo != admin_logo:
            st.image(client_logo, width=70)

def kpi_metrics(frame: pd.DataFrame):
    farmers = 0
    if "FarmerID" in frame.columns:
        farmers = frame["FarmerID"].nunique()
    elif "FarmerName" in frame.columns:
        farmers = frame["FarmerName"].nunique()
    devices = frame["DeviceID"].nunique() if "DeviceID" in frame.columns else 0
    readings = len(frame)

    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.metric("Total Farmers", int(farmers))
    c2.metric("Total Devices", int(devices))
    c3.metric("Total Readings", int(readings))
    c4.metric("Season", SEASON_LABEL)

def pick_field_officer_column(frame: pd.DataFrame) -> str | None:
    candidates = ["FieldOfficer","Field Officer","Field_Officer","FOName","Officer","FiledOfficer","FiledOfficer.Name"]
    for c in candidates:
        if c in frame.columns:
            return c
    return None

def pick_village_column(frame: pd.DataFrame) -> str | None:
    candidates = ["Village","VillageName","village","Village_Name"]
    for c in candidates:
        if c in frame.columns:
            return c
    return None

def derive_status_counts(frame: pd.DataFrame, hours:int=DEFAULT_STATUS_HOURS) -> pd.DataFrame:
    if "Status" in frame.columns and frame["Status"].notna().any():
        s = (frame.dropna(subset=["DeviceID","Status"])
                    .drop_duplicates(subset=["DeviceID"], keep="last")
                    .groupby("Status")["DeviceID"].nunique().reset_index(name="DeviceCount"))
        return s
    if frame.empty or frame["Timestamp"].isna().all():
        return pd.DataFrame({"Status":["No Data"], "DeviceCount":[0]})
    last_seen_by_dev = (frame.dropna(subset=["DeviceID","Timestamp"])
                             .groupby("DeviceID")["Timestamp"].max()
                             .reset_index())
    now_utc = pd.Timestamp.now(tz="UTC")
    threshold = now_utc - pd.Timedelta(hours=hours)
    last_seen_by_dev["Status"] = np.where(last_seen_by_dev["Timestamp"] >= threshold, "Online", "Offline")
    out = last_seen_by_dev.groupby("Status")["DeviceID"].nunique().reset_index(name="DeviceCount")
    return out

def reset_feedback_form():
    for k in ["fb_comment","fb_reason","fb_changes","fb_status","fb_sat"]:
        if k in st.session_state:
            st.session_state.pop(k)
    st.rerun()

# =====================================
# ---------------- UI -----------------
# =====================================
tabs = st.tabs([
    "📊 Dashboard",
    "📈 Trends",
    "📟 Device-wise Irrigation Trend",
    "🧪 Data Quality",
    "🗺️ Device Location",
    "💬 Feedback"
])

# ---------------- Dashboard ------------
with tabs[0]:
    show_top_header()
    st.markdown("### 🌊 IoT Water Dashboard")
    kpi_metrics(working)

    st.markdown("---")
    g1, g2 = st.columns([1,1])

    with g1:
        if st.session_state.role == "admin":
            st.subheader("Client-wise Device Count (Pie)")
            if {"Client","DeviceID"}.issubset(working.columns) and working["DeviceID"].notna().any():
                cdc = working.groupby("Client")["DeviceID"].nunique().reset_index(name="DeviceCount")
                cdc = cdc.sort_values("DeviceCount", ascending=False)
                if not cdc.empty:
                    fig = px.pie(cdc, names="Client", values="DeviceCount")
                    fig.update_traces(textposition="inside", textinfo="percent+label")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No devices in selection.")
            else:
                st.info("Need 'Client' and 'DeviceID' columns.")
        else:
            st.subheader("District-wise Device Count (Pie)")
            if {"District","DeviceID"}.issubset(working.columns) and working["DeviceID"].notna().any():
                ddc = working.groupby("District")["DeviceID"].nunique().reset_index(name="DeviceCount")
                ddc = ddc.sort_values("DeviceCount", ascending=False)
                if not ddc.empty:
                    fig = px.pie(ddc, names="District", values="DeviceCount")
                    fig.update_traces(textposition="inside", textinfo="percent+label")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No devices in selection.")
            else:
                st.info("Need 'District' and 'DeviceID' columns.")

    with g2:
        st.subheader("Status-wise Device Count (Donut)")
        sc = derive_status_counts(working, hours=DEFAULT_STATUS_HOURS)
        if not sc.empty:
            fig = px.pie(sc, names="Status", values="DeviceCount", hole=0.45)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No status data.")

    st.markdown("---")

    gg1, gg2 = st.columns([1,1])
    with gg1:
        if "DeviceType" in working.columns:
            portable = working[working["DeviceType"] == "Portable"]
            if st.session_state.role == "admin":
                st.subheader("Client-wise Number of Data (Portable only)")
                if not portable.empty:
                    cnd = portable.groupby("Client").size().reset_index(name="Rows")
                    cnd = cnd.sort_values("Rows", ascending=False)
                    fig = px.bar(cnd, x="Client", y="Rows", text="Rows")
                    fig.update_layout(yaxis_title="Row Count (readings)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No Portable device rows in current selection.")
            else:
                st.subheader("District-wise Number of Data (Portable only)")
                if not portable.empty and "District" in portable.columns:
                    dnd = portable.groupby("District").size().reset_index(name="Rows")
                    dnd = dnd.sort_values("Rows", ascending=False)
                    fig = px.bar(dnd, x="District", y="Rows", text="Rows")
                    fig.update_layout(yaxis_title="Row Count (readings)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No Portable device rows (or District column missing).")
        else:
            st.info("Column 'DeviceType' missing.")

    with gg2:
        st.subheader("Field Officer-wise Number of Data (Portable only)")
        fo_col = pick_field_officer_column(working)
        if fo_col is None:
            st.info("Couldn't find a Field Officer column. Expected one of: FieldOfficer, FiledOfficer, FOName, etc.")
        else:
            portable = working[working["DeviceType"] == "Portable"]
            if not portable.empty and fo_col in portable.columns:
                fnd = portable.groupby(fo_col).size().reset_index(name="Rows")
                fnd = fnd.sort_values("Rows", ascending=False).head(30)
                fig = px.bar(fnd, x=fo_col, y="Rows", text="Rows")
                fig.update_layout(xaxis_title="Field Officer", yaxis_title="Row Count (readings)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No Portable device rows for Field Officer chart.")

    if st.session_state.role == "client":
        st.markdown("---")
        st.markdown("### 👥 Farmers & Devices by Geography")

        if "District" in working.columns:
            st.subheader("District-wise Farmer Count")
            farmer_col = "FarmerID" if "FarmerID" in working.columns else ("FarmerName" if "FarmerName" in working.columns else None)
            if farmer_col:
                dff = (working.dropna(subset=["District"])
                             .groupby("District")[farmer_col].nunique()
                             .reset_index(name="Farmers"))
                if not dff.empty:
                    fig = px.bar(dff.sort_values("Farmers", ascending=False), x="District", y="Farmers", text="Farmers")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No district data.")
            else:
                st.info("Farmer column not found.")
        else:
            st.info("District column not found.")

        vcol = pick_village_column(working)
        if vcol:
            st.subheader("Village-wise Farmer Count")
            farmer_col = "FarmerID" if "FarmerID" in working.columns else ("FarmerName" if "FarmerName" in working.columns else None)
            if farmer_col:
                vff = (working.dropna(subset=[vcol])
                             .groupby(vcol)[farmer_col].nunique()
                             .reset_index(name="Farmers"))
                if not vff.empty:
                    fig = px.bar(vff.sort_values("Farmers", ascending=False).head(40), x=vcol, y="Farmers", text="Farmers")
                    fig.update_layout(xaxis_title="Village")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No village data for farmer counts.")
            else:
                st.info("Farmer column not found.")
        else:
            st.info("Village column not found.")

        if vcol and "DeviceID" in working.columns:
            st.subheader("Village-wise Device Count")
            vdc = (working.dropna(subset=[vcol])
                         .groupby(vcol)["DeviceID"].nunique()
                         .reset_index(name="Devices"))
            if not vdc.empty:
                fig = px.bar(vdc.sort_values("Devices", ascending=False).head(40), x=vcol, y="Devices", text="Devices")
                fig.update_layout(xaxis_title="Village")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No village device data.")

        if "WaterStatus" in working.columns:
            st.subheader("WaterStatus-wise Distribution (Pie)")
            ws = working.groupby("WaterStatus").size().reset_index(name="Count")
            if not ws.empty:
                fig = px.pie(ws, names="WaterStatus", values="Count")
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No WaterStatus values.")
        else:
            st.info("WaterStatus column not found.")

    st.markdown("---")
    c1, c2 = st.columns([1,1])
    with c1:
        st.subheader("WaterLevel Distribution")
        if "WaterLevel" in working.columns and working["WaterLevel"].notna().any():
            fig = px.histogram(working, x="WaterLevel", nbins=40, marginal="box")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No WaterLevel values to show.")
    with c2:
        st.subheader("Top Portable Sensors by Readings")
        if "DeviceType" in working.columns and "DeviceID" in working.columns:
            portable = working[working["DeviceType"] == "Portable"]
            if not portable.empty:
                topN = (portable.groupby("DeviceID").size().reset_index(name="Readings")
                               .sort_values("Readings", ascending=False).head(15))
                if not topN.empty:
                    fig = px.bar(topN, x="DeviceID", y="Readings", text="Readings")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No readings for Portable devices.")
            else:
                st.info("No Portable device rows.")
        else:
            st.info("Required columns missing.")

# ---------------- Trends ---------------
with tabs[1]:
    show_top_header()
    st.markdown("### 📈 Time-Series & Daily Heatmap")
    agg_pick = st.selectbox("Aggregation for time-series", ["mean","sum","max","min"], index=0)
    tmp = working[["Timestamp","WaterLevel"]].copy()
    tmp = tmp.dropna(subset=["Timestamp"])
    if tmp.empty:
        st.info("No time-series to plot.")
    else:
        tmp["Timestamp"] = pd.to_datetime(tmp["Timestamp"])
        tmp["Date"] = ist(tmp["Timestamp"]).dt.date
        g = tmp.groupby("Date", as_index=False)["WaterLevel"].agg(agg_pick)
        title_suffix = " (fast mode)" if len(df) > FAST_LIMIT_ROWS else ""
        fig = px.line(g, x="Date", y="WaterLevel", markers=True, title=f"Daily {agg_pick} WaterLevel{title_suffix}")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Daily Heatmap (Avg WaterLevel)")
    tmp2 = working[["Timestamp","WaterLevel"]].dropna(subset=["Timestamp"]).copy()
    if tmp2.empty:
        st.info("Not enough data for a heatmap.")
    else:
        tmp2["Timestamp"] = pd.to_datetime(tmp2["Timestamp"])
        ist_ts = ist(tmp2["Timestamp"])
        tmp2["Date"] = ist_ts.dt.date
        tmp2["DayOfWeek"] = ist_ts.dt.day_name()
        week_start = ist_ts.dt.to_period("W-MON").apply(lambda p: p.start_time.date())
        tmp2["WeekStart"] = week_start
        heat = tmp2.groupby(["WeekStart","DayOfWeek"])["WaterLevel"].mean().reset_index()
        dow = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        heat["DayOfWeek"] = pd.Categorical(heat["DayOfWeek"], categories=dow, ordered=True)
        heat = heat.sort_values(["WeekStart","DayOfWeek"])
        pivot = heat.pivot(index="DayOfWeek", columns="WeekStart", values="WaterLevel")
        fig = go.Figure(data=go.Heatmap(z=pivot.values, x=[str(x) for x in pivot.columns], y=pivot.index, coloraxis="coloraxis"))
        fig.update_layout(coloraxis=dict(colorscale="Viridis"))
        st.plotly_chart(fig, use_container_width=True)

# ------------- Device-wise Irrigation Trend -------------
with tabs[2]:
    show_top_header()
    st.markdown("### 📟 Device-wise Irrigation Trend")

    farmer_opts_all = sorted([str(x) for x in working["FarmerName"].dropna().unique().tolist()]) if "FarmerName" in working.columns else []
    farmer_pick = st.selectbox("Filter by Farmer", options=["All"] + farmer_opts_all) if farmer_opts_all else "All"
    w = working.copy()
    if farmer_pick != "All" and "FarmerName" in w.columns:
        w = w[w["FarmerName"].astype(str) == farmer_pick]

    dev_opts = sorted([str(x) for x in w["DeviceID"].dropna().unique().tolist()]) if "DeviceID" in w.columns else []
    selected_dev = st.selectbox("Select Device", options=["Auto (top by readings)"] + dev_opts) if dev_opts else "Auto (top by readings)"

    if "DeviceID" in w.columns and w["DeviceID"].notna().any():
        if selected_dev == "Auto (top by readings)":
            counts = w.groupby("DeviceID").size().reset_index(name="Readings").sort_values("Readings", ascending=False)
            if counts.empty:
                st.info("No device data available."); st.stop()
            dev_id = counts.iloc[0]["DeviceID"]
        else:
            dev_id = selected_dev

        sub = w[w["DeviceID"].astype(str) == str(dev_id)].copy()
        if sub.empty:
            st.info("No rows for the selected device.")
        else:
            sub["Timestamp"] = pd.to_datetime(sub["Timestamp"])
            sub = sub.dropna(subset=["Timestamp"])

            if "DeviceType" in sub.columns:
                vals = sub["DeviceType"].dropna()
                dtype = str(vals.iloc[0]) if len(vals) > 0 else "Unknown"
            else:
                dtype = "Unknown"

            label_farmer = sub['FarmerName'].dropna().iloc[0] if 'FarmerName' in sub.columns and not sub['FarmerName'].dropna().empty else "—"
            st.markdown(f"**Device {dev_id}** — Type: {dtype} — Farmer: {label_farmer}")

            if dtype == "Fixed":
                fig = px.line(sub.sort_values("Timestamp"), x="Timestamp", y="WaterLevel", markers=True, title=f"Irrigation Trend — Fixed ({dev_id})")
            else:
                fig = px.scatter(sub.sort_values("Timestamp"), x="Timestamp", y="WaterLevel", title=f"Irrigation Trend — Portable/Other ({dev_id})", trendline="lowess")
            st.plotly_chart(fig, use_container_width=True)

            sub["Date"] = ist(sub["Timestamp"]).dt.date
            daily = sub.groupby("Date", as_index=False)["WaterLevel"].mean()
            st.dataframe(daily.rename(columns={"WaterLevel":"Avg WaterLevel"}), use_container_width=True, height=260)
    else:
        st.info("DeviceID column not found.")

# ------------- Data Quality ------------
with tabs[3]:
    show_top_header()
    st.markdown("### 🧪 Data Quality")
    c1, c2 = st.columns([1,1])

    with c1:
        st.subheader("Duplicate Timestamp per Device")
        if {"DeviceID","Timestamp"}.issubset(working.columns):
            dup = working.duplicated(subset=["DeviceID","Timestamp"]).sum()
            st.metric("Duplicate rows", int(dup))
            if dup > 0:
                ddf = working[working.duplicated(subset=["DeviceID","Timestamp"], keep=False)].sort_values(["DeviceID","Timestamp"])
                st.dataframe(ddf, use_container_width=True, height=260)
        else:
            st.info("Need DeviceID and Timestamp")

    with c2:
        st.subheader("Out-of-Range Flags")
        if "WaterLevel" in working.columns:
            q01 = float(np.nanquantile(working["WaterLevel"].dropna(), 0.01)) if working["WaterLevel"].notna().sum() else 0.0
            q99 = float(np.nanquantile(working["WaterLevel"].dropna(), 0.99)) if working["WaterLevel"].notna().sum() else 100.0
            low = st.number_input("Min allowed WaterLevel", value=q01)
            high = st.number_input("Max allowed WaterLevel", value=q99)
            flagged = working[(working["WaterLevel"].notna()) & ((working["WaterLevel"] < low) | (working["WaterLevel"] > high))]
            st.metric("Flagged readings", len(flagged))
            if not flagged.empty:
                cols = [c for c in ["Timestamp","DeviceID","WaterLevel","Client","District","FarmerName"] if c in working.columns]
                st.dataframe(flagged[cols], use_container_width=True, height=260)
        else:
            st.info("No WaterLevel column.")

# ------------- Device Location Map -------------
with tabs[4]:
    show_top_header()
    st.markdown("### 🗺️ Device Location (Unique DeviceID)")
    if {"DeviceID","Latitude","Longitude"}.issubset(working.columns):
        loc = working.dropna(subset=["Latitude","Longitude","DeviceID"]).copy()
        if "Timestamp" in loc.columns:
            loc["Timestamp"] = pd.to_datetime(loc["Timestamp"], errors="coerce")
            loc = loc.sort_values("Timestamp")
            loc = loc.groupby("DeviceID").tail(1)
        else:
            loc = loc.drop_duplicates(subset=["DeviceID"], keep="last")

        if not loc.empty:
            dtype_opts = sorted(loc["DeviceType"].dropna().unique().tolist()) if "DeviceType" in loc.columns else []
            dtype_pick = st.multiselect("Filter by Device Type", options=dtype_opts, default=[])
            if dtype_pick:
                loc = loc[loc["DeviceType"].isin(dtype_pick)]

            fig = px.scatter_mapbox(
                loc, lat="Latitude", lon="Longitude",
                hover_name="DeviceID",
                hover_data=[c for c in ["Client","District","FarmerName","DeviceType"] if c in loc.columns],
                zoom=4, height=500
            )
            fig.update_layout(mapbox_style="open-street-map")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No device locations available (lat/lon missing).")
    else:
        st.info("Latitude/Longitude columns not found.")

# --------------- Feedback --------------
with tabs[5]:
    show_top_header()
    st.markdown("#### All feedback is stored in: `feedbacks.csv` and per-entry JSON files under `feedback_history/`.")
    os.makedirs(FEEDBACK_DIR, exist_ok=True)

    if st.session_state.role == "client":
        st.markdown("### 💬 Submit Feedback / Report Approval")
        status = st.selectbox("Report status", ["Approved", "Not Approved", "Changes Required"], key="fb_status")
        comment = st.text_area("Comments (optional)", key="fb_comment")

        satisfaction = None
        if status == "Approved":
            satisfaction = st.slider("Satisfaction rating", 1, 5, 5, help="1 = Very Low, 5 = Very High", key="fb_sat")

        reason = st.text_area("Reason for rejection (required)", key="fb_reason") if status == "Not Approved" else ""
        changes = st.text_area("List the changes required (required)", key="fb_changes") if status == "Changes Required" else ""

        if st.button("Submit", type="primary", key="fb_submit"):
            if status == "Not Approved" and not str(reason).strip():
                st.warning("Please provide a reason for rejection."); st.stop()
            if status == "Changes Required" and not str(changes).strip():
                st.warning("Please list the required changes."); st.stop()

            fb_id = uuid.uuid4().hex
            row = {
                "ID": fb_id,
                "Timestamp": datetime.now(timezone.utc).isoformat(),
                "Client": client_name,
                "Status": status,
                "Satisfaction": satisfaction if satisfaction is not None else "",
                "Reason": str(reason).strip() if isinstance(reason, str) else "",
                "Changes": str(changes).strip() if isinstance(changes, str) else "",
                "Comment": str(comment).strip() if isinstance(comment, str) else "",
                "AdminComment": "",
            }
            new_df = pd.DataFrame([row])
            if os.path.exists(FEEDBACK_FILE):
                try:
                    old = pd.read_csv(FEEDBACK_FILE)
                    out = pd.concat([old, new_df], ignore_index=True)
                except Exception:
                    out = new_df
            else:
                out = new_df
            out.to_csv(FEEDBACK_FILE, index=False)

            json_path = os.path.join(FEEDBACK_DIR, f"{fb_id}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(row, f, ensure_ascii=False, indent=2)

            st.success("✅ Submitted. Thank you! (Saved to CSV + history file)")

            reset_feedback_form()

    else:
        st.markdown("### 💬 Client Feedbacks")
        if os.path.exists(FEEDBACK_FILE):
            fb = pd.read_csv(FEEDBACK_FILE)
            if "AdminComment" not in fb.columns:
                fb["AdminComment"] = ""
            if "ID" not in fb.columns:
                fb["ID"] = [f"legacy_{i}" for i in range(len(fb))]
                fb.to_csv(FEEDBACK_FILE, index=False)

            if fb.empty:
                st.info("No feedback submitted yet.")
            else:
                st.subheader("📋 Latest Feedback")
                st.dataframe(fb.sort_values("Timestamp", ascending=False), use_container_width=True, height=320)

                st.markdown("### ✍️ Add/Update Admin Comment")
                fb_disp = fb.copy()
                fb_disp["_row_index"] = fb_disp.index
                options = fb_disp.apply(lambda r: f"[{r['_row_index']}] {r.get('Timestamp','')} • {r.get('Client','')} • {r.get('Status','')} • ID={r.get('ID','')}", axis=1).tolist()
                if options:
                    pick = st.selectbox("Choose a feedback entry", options=options)
                    try:
                        sel_row_index = int(pick.split(']')[0][1:])
                    except Exception:
                        sel_row_index = None
                    current_val = str(fb.loc[sel_row_index, "AdminComment"]) if sel_row_index is not None else ""
                    admin_note = st.text_area("Admin comment", value=current_val, key="admin_note")
                    if st.button("Save Admin Comment"):
                        if sel_row_index is not None:
                            fb.loc[sel_row_index, "AdminComment"] = str(admin_note).strip()
                            fb.to_csv(FEEDBACK_FILE, index=False)

                            os.makedirs(FEEDBACK_DIR, exist_ok=True)
                            fb_id = str(fb.loc[sel_row_index, "ID"])
                            json_path = os.path.join(FEEDBACK_DIR, f"{fb_id}.json")
                            row_dict = fb.loc[sel_row_index].to_dict()
                            try:
                                with open(json_path, "w", encoding="utf-8") as f:
                                    json.dump(row_dict, f, ensure_ascii=False, indent=2)
                            except Exception:
                                pass

                            st.success("💾 Saved admin comment (CSV + history updated).")
                        else:
                            st.warning("Please select a valid entry.")

                st.markdown("---")
                cols = st.columns(3)
                with cols[0]:
                    st.subheader("Status Breakdown")
                    by_status = fb.groupby("Status")["Client"].count().reset_index().rename(columns={"Client":"Count"})
                    fig = px.bar(by_status, x="Status", y="Count", text="Count")
                    st.plotly_chart(fig, use_container_width=True)

                with cols[1]:
                    st.subheader("Avg Satisfaction by Client")
                    if "Satisfaction" in fb.columns:
                        s = fb.copy()
                        s["Satisfaction"] = pd.to_numeric(s["Satisfaction"], errors="coerce")
                        s = s.dropna(subset=["Satisfaction"])
                        if not s.empty:
                            agg = s.groupby("Client")["Satisfaction"].mean().reset_index()
                            fig = px.bar(agg, x="Client", y="Satisfaction", text="Satisfaction", range_y=[0,5])
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No satisfaction ratings yet.")
                    else:
                        st.info("No satisfaction data.")

                with cols[2]:
                    st.subheader("Approvals Over Time")
                    fb["Date"] = pd.to_datetime(fb["Timestamp"], errors="coerce").dt.date
                    appr = fb[fb["Status"] == "Approved"].groupby("Date").size().reset_index(name="Approved")
                    fig = px.line(appr, x="Date", y="Approved", markers=True)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No feedback submitted yet.")
