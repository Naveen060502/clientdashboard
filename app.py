
import os
from datetime import date, datetime, timedelta, timezone

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

FAST_LIMIT_ROWS = 300_000   # switch to fast-mode aggregations above this
DEFAULT_STATUS_HOURS = 24   # last seen within this window => Online

# =====================================
# -------------- Styling --------------
# =====================================
st.markdown(
    """
    <style>
      .small-note {font-size: 0.9rem; color: #6b7280;}
      .metric-row {display: flex; gap: 1rem; flex-wrap: wrap;}
      .metric-card {
          flex: 1 1 220px;
          padding: 1rem;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          background: #ffffff;
          box-shadow: 0 1px 2px rgba(0,0,0,0.05);
      }
      .st-emotion-cache-1jicfl2 {padding-top: 1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

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

# Optional logo
logo_map = {"admin": "logo.png", "AVPN": "AVPN_logo.png", "CIPT": "CIPT_LOGO.png", "Titan": "titan.png"}
logo_path = logo_map.get(client_name, "logo.png")
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=140)

# =====================================
# -------------- Data -----------------
# =====================================
@st.cache_data(show_spinner=False)
def load_data(csv_path: str = "iot_water_data_1.csv") -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_path, engine="python", sep=None)
    except Exception:
        df = pd.read_csv(csv_path)

    # Parse timestamps to UTC if possible
    if "Timestamp" in df.columns:
        try:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True, errors="raise")
        except Exception:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True, dayfirst=True, errors="coerce")
    else:
        df["Timestamp"] = pd.NaT

    # Standardize important columns
    default_cols = {
        "Client": np.nan, "District": np.nan, "DeviceID": np.nan,
        "DeviceType": np.nan, "FarmerName": np.nan, "WaterLevel": np.nan
    }
    for c, val in default_cols.items():
        if c not in df.columns:
            df[c] = val

    # Cast strings to category for memory/perf
    for c in ["Client","District","DeviceID","DeviceType","FarmerName"]:
        try:
            df[c] = df[c].astype("category")
        except Exception:
            pass

    # Geolocation numeric
    for c in ["Latitude","Longitude"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

df = load_data()

def ist(dt_series: pd.Series) -> pd.Series:
    # dt_series is expected tz-aware; if not, localize to IST
    try:
        if dt_series.dt.tz is None:
            return dt_series.dt.tz_localize("Asia/Kolkata")
        return dt_series.dt.tz_convert("Asia/Kolkata")
    except Exception:
        # as a last resort, coerce then localize
        s = pd.to_datetime(dt_series, errors="coerce")
        return s.dt.tz_localize("Asia/Kolkata")

# Fast mode suggestion
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
    working = working[working["Client"] == client_name]
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

# Date filter
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start, end = date_range
    start_utc = pd.Timestamp(start).tz_localize("Asia/Kolkata").tz_convert("UTC")
    end_utc = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    end_utc = end_utc.tz_localize("Asia/Kolkata").tz_convert("UTC")
    working = working[(pd.to_datetime(working["Timestamp"]) >= start_utc) & (pd.to_datetime(working["Timestamp"]) <= end_utc)]

# =====================================
# ---------- Helper functions ---------
# =====================================
def kpi_block(frame: pd.DataFrame):
    farmers = frame["FarmerName"].nunique() if "FarmerName" in frame.columns else 0
    devices = frame["DeviceID"].nunique() if "DeviceID" in frame.columns else 0
    readings = len(frame)
    last_seen = pd.to_datetime(frame["Timestamp"]).max()
    last_seen_str = "—" if pd.isna(last_seen) else ist(pd.Series([last_seen])).iloc[0].strftime("%d %b %Y, %H:%M IST")

    wl_notnull = frame["WaterLevel"].notna().mean() * 100 if "WaterLevel" in frame.columns and len(frame) else 0.0
    fixed_count = frame.query("DeviceType == 'Fixed'").DeviceID.nunique() if "DeviceType" in frame.columns else 0
    portable_count = frame.query("DeviceType == 'Portable'").DeviceID.nunique() if "DeviceType" in frame.columns else 0

    st.markdown('<div class="metric-row">', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-card"><h4>👨‍🌾 Farmers</h4><h2>{farmers:,}</h2></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-card"><h4>💧 Devices</h4><h2>{devices:,}</h2><div class="small-note">Fixed: {fixed_count} • Portable: {portable_count}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-card"><h4>📊 Readings</h4><h2>{readings:,}</h2></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-card"><h4>✅ Data Completeness</h4><h2>{wl_notnull:.1f}%</h2><div class="small-note">non-null WaterLevel</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-card"><h4>⏱️ Last Ingest</h4><h2 style="font-size:1.2rem">{last_seen_str}</h2></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def pick_field_officer_column(frame: pd.DataFrame) -> str | None:
    candidates = ["FieldOfficer","Field Officer","Field_Officer","FOName","Officer","FiledOfficer","FiledOfficer.Name"]
    for c in candidates:
        if c in frame.columns:
            return c
    return None

def derive_status_counts(frame: pd.DataFrame, hours:int=DEFAULT_STATUS_HOURS) -> pd.DataFrame:
    # Prefer explicit Status column if present and non-null
    if "Status" in frame.columns and frame["Status"].notna().any():
        s = (frame.dropna(subset=["DeviceID","Status"])
                    .drop_duplicates(subset=["DeviceID"], keep="last")
                    .groupby("Status")["DeviceID"].nunique().reset_index(name="DeviceCount"))
        return s

    # Fallback: derive Online/Offline by last-seen recency
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

# =====================================
# ---------------- UI -----------------
# =====================================
tabs = st.tabs(["📊 Dashboard", "📈 Trends", "📟 Device-wise Irrigation Trend", "🧪 Data Quality", "💬 Feedback"])

# ---------------- Dashboard ------------
with tabs[0]:
    st.markdown("## 🌊 IoT Water Dashboard")
    kpi_block(working)

    st.markdown("---")
    # === Requested charts ===
    g1, g2 = st.columns([1,1])
    with g1:
        st.subheader("Client-wise Device Count (Pie)")
        if {"Client","DeviceID"}.issubset(working.columns) and working["DeviceID"].notna().any():
            cdc = working.groupby("Client")["DeviceID"].nunique().reset_index(name="DeviceCount")
            cdc = cdc.sort_values("DeviceCount", ascending=False)
            if not cdc.empty:
                fig = px.pie(cdc, names="Client", values="DeviceCount", hole=0.0)
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No devices in selection.")
        else:
            st.info("Need 'Client' and 'DeviceID' columns.")

    with g2:
        st.subheader("Status-wise Device Count (Donut)")
        hrs = st.slider("Status threshold (hours)", 1, 72, DEFAULT_STATUS_HOURS, help="Last seen within N hours ⇒ Online")
        sc = derive_status_counts(working, hours=hrs)
        if not sc.empty:
            fig = px.pie(sc, names="Status", values="DeviceCount", hole=0.45)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No status data.")

    st.markdown("---")
    gg1, gg2 = st.columns([1,1])
    with gg1:
        st.subheader("Client-wise Number of Data (Portable only)")
        if "DeviceType" in working.columns:
            portable = working[working["DeviceType"] == "Portable"]
            if not portable.empty:
                cnd = portable.groupby("Client").size().reset_index(name="Rows")
                cnd = cnd.sort_values("Rows", ascending=False)
                fig = px.bar(cnd, x="Client", y="Rows", text="Rows")
                fig.update_layout(yaxis_title="Row Count (readings)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No Portable device rows in current selection.")
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

    st.markdown("---")
    # Compact extras
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
    st.markdown("## 📈 Time-Series & Heatmaps")
    agg_pick = st.selectbox("Aggregation", ["mean","sum","max","min"], index=0)
    # Daily aggregation for speed
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
    st.subheader("Hourly Heatmap (Avg WaterLevel)")
    tmp2 = working[["Timestamp","WaterLevel"]].dropna(subset=["Timestamp"]).copy()
    if tmp2.empty:
        st.info("Not enough data for a heatmap.")
    else:
        tmp2["Timestamp"] = pd.to_datetime(tmp2["Timestamp"])
        ist_ts = ist(tmp2["Timestamp"])
        tmp2["Hour"] = ist_ts.dt.hour
        tmp2["DayOfWeek"] = ist_ts.dt.day_name()
        heat = tmp2.groupby(["DayOfWeek","Hour"])["WaterLevel"].mean().reset_index()
        # ensure day ordering
        dow = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        heat["DayOfWeek"] = pd.Categorical(heat["DayOfWeek"], categories=dow, ordered=True)
        heat = heat.sort_values(["DayOfWeek","Hour"])
        pivot = heat.pivot(index="DayOfWeek", columns="Hour", values="WaterLevel")
        fig = go.Figure(data=go.Heatmap(z=pivot.values, x=pivot.columns, y=pivot.index, coloraxis="coloraxis"))
        fig.update_layout(coloraxis=dict(colorscale="Viridis"))
        st.plotly_chart(fig, use_container_width=True)

# ------------- Device-wise Irrigation Trend -------------
with tabs[2]:
    st.markdown("## 📟 Device-wise Irrigation Trend")
    # Choose single device (to keep fast). If none selected, show top by readings.
    dev_opts = sorted([str(x) for x in working["DeviceID"].dropna().unique().tolist()]) if "DeviceID" in working.columns else []
    selected_dev = st.selectbox("Select Device", options=["Auto (top by readings)"] + dev_opts) if dev_opts else "Auto (top by readings)"

    w = working.copy()
    if "DeviceID" in w.columns and w["DeviceID"].notna().any():
        if selected_dev == "Auto (top by readings)":
            counts = w.groupby("DeviceID").size().reset_index(name="Readings").sort_values("Readings", ascending=False)
            if counts.empty:
                st.info("No device data available.")
                st.stop()
            dev_id = counts.iloc[0]["DeviceID"]
        else:
            dev_id = selected_dev

        sub = w[w["DeviceID"].astype(str) == str(dev_id)].copy()
        if sub.empty:
            st.info("No rows for the selected device.")
        else:
            sub["Timestamp"] = pd.to_datetime(sub["Timestamp"])
            sub = sub.dropna(subset=["Timestamp"])

            # Compute dtype safely for categorical
            if "DeviceType" in sub.columns:
                vals = sub["DeviceType"].dropna()
                dtype = str(vals.iloc[0]) if len(vals) > 0 else "Unknown"
            else:
                dtype = "Unknown"

            st.markdown(f"**Device {dev_id}** — Type: {dtype}")

            if dtype == "Fixed":
                fig = px.line(sub.sort_values("Timestamp"), x="Timestamp", y="WaterLevel", markers=True, title=f"Irrigation Trend — Fixed ({dev_id})")
            else:
                fig = px.scatter(sub.sort_values("Timestamp"), x="Timestamp", y="WaterLevel", title=f"Irrigation Trend — Portable/Other ({dev_id})", trendline="lowess")
            st.plotly_chart(fig, use_container_width=True)

            # Optional: day-wise aggregation for quick summary
            sub["Date"] = ist(sub["Timestamp"]).dt.date
            daily = sub.groupby("Date", as_index=False)["WaterLevel"].mean()
            st.dataframe(daily.rename(columns={"WaterLevel":"Avg WaterLevel"}), use_container_width=True, height=260)
    else:
        st.info("DeviceID column not found.")

# ------------- Data Quality ------------
with tabs[3]:
    st.markdown("## 🧪 Data Quality")
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
            # sensible defaults from quantiles (guarded)
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

# --------------- Feedback --------------
with tabs[4]:
    if st.session_state.role == "client":
        st.markdown("## 💬 Submit Feedback / Report Approval")
        status = st.selectbox("Report status", ["Approved", "Not Approved", "Changes Required"])
        comment = st.text_area("Comments (optional)")

        satisfaction = None
        reason = ""
        changes = ""

        if status == "Approved":
            satisfaction = st.slider("Satisfaction rating", 1, 5, 5, help="1 = Very Low, 5 = Very High")
        elif status == "Not Approved":
            reason = st.text_area("Reason for rejection (required)")
        elif status == "Changes Required":
            changes = st.text_area("List the changes required (required)")

        if st.button("Submit", type="primary"):
            # Validate required fields
            if status == "Approved":
                pass  # satisfaction always set by slider
            elif status == "Not Approved" and not reason.strip():
                st.warning("Please provide a reason for rejection.")
                st.stop()
            elif status == "Changes Required" and not changes.strip():
                st.warning("Please list the required changes.")
                st.stop()

            row = {
                "Timestamp": datetime.now(timezone.utc).isoformat(),
                "Client": client_name,
                "Status": status,
                "Satisfaction": satisfaction if satisfaction is not None else "",
                "Reason": reason.strip(),
                "Changes": changes.strip(),
                "Comment": comment.strip(),
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
            st.success("✅ Submitted. Thank you!")

    else:
        st.markdown("## 💬 Client Feedbacks")
        if os.path.exists(FEEDBACK_FILE):
            fb = pd.read_csv(FEEDBACK_FILE)
            if fb.empty:
                st.info("No feedback submitted yet.")
            else:
                st.subheader("📋 Latest Feedback")
                st.dataframe(fb.sort_values("Timestamp", ascending=False), use_container_width=True, height=320)

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
