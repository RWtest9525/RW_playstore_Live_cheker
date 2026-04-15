import io
import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st
from google_play_scraper import Sort, reviews

# 1. Page Config & Professional UI Theme
st.set_page_config(page_title="RW Pro Live Checker", page_icon="🚀", layout="wide")

st.markdown(
    """
    <style>
    /* Main Background and Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main { background-color: #f8fafc; }
    
    /* Custom Header Card */
    .brand-container {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        padding: 2rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
        display: flex;
        align-items: center;
        gap: 20px;
    }
    
    /* Card Styling */
    .st-emotion-cache-1r6slb0, .report-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
    }
    
    /* Button Styling */
    div.stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
        height: 3rem;
    }
    
    div.stButton > button:first-child {
        background-color: #6366f1 !important;
        color: white !important;
        border: none !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.3);
    }
    
    /* Metric / Counter */
    .live-badge {
        background: #ecfdf5;
        color: #065f46;
        padding: 5px 15px;
        border-radius: 999px;
        font-weight: 700;
        border: 1px solid #a7f3d0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

IST_TZ = pytz.timezone("Asia/Kolkata")
DATA_DIR = "data"
APP_DB_PATH = os.path.join(DATA_DIR, "apps_config.json")
DAILY_DB_PATH = os.path.join(DATA_DIR, "daily_reports.json")

# --------- Helpers ---------
def ensure_db_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(APP_DB_PATH): save_json(APP_DB_PATH, [])
    if not os.path.exists(DAILY_DB_PATH): save_json(DAILY_DB_PATH, [])

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_id(url):
    match = re.search(r"id=([a-zA-Z0-9._]+)", url)
    return match.group(1) if match else url.strip()

# --------- CORE FETCH LOGIC (STABLE) ---------
def fetch_logic(aid, target_dt, depth_pages, star_values=None, hint_values=None):
    all_raw = []
    token = None
    stop_date = target_dt - timedelta(days=2) # Deep search safety
    
    for _ in range(depth_pages):
        try:
            res, token = reviews(aid, lang="en", country="in", sort=Sort.NEWEST, count=100, continuation_token=token)
            if not res: break
            all_raw.extend(res)
            last_item_dt = res[-1]["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
            if last_item_dt < stop_date: break
            if not token: break
        except: break

    stars_set = set(star_values or [])
    matches = []
    for r in all_raw:
        rev_dt = r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
        if rev_dt != target_dt: continue
        if stars_set and int(r.get("score", 0)) not in stars_set: continue
        text = (r.get("content") or "").strip()
        if hint_values and not any(text.endswith(h) for h in hint_values): continue

        matches.append({
            "User": r.get("userName", "Unknown"),
            "Rating": f"{r.get('score', 0)}/5",
            "Review": text,
            "App ID": aid,
            "Logo": r.get("userImage", ""),
            "Date": rev_dt.strftime("%Y-%m-%d")
        })
    return matches

def run_due_daily_jobs():
    apps = load_json(APP_DB_PATH)
    reports = load_json(DAILY_DB_PATH)
    now_ist = datetime.now(IST_TZ)
    report_index = {(r["app_id"], r["report_date"]) for r in reports}
    generated = 0

    for app in apps:
        created_dt = datetime.fromisoformat(app["created_at"])
        due_date = (created_dt + timedelta(days=app.get("days_after", 0))).date()
        report_key = (app["app_id"], due_date.strftime("%Y-%m-%d"))
        
        if due_date <= now_ist.date() and report_key not in report_index:
            found = fetch_logic(app["app_id"], due_date, 5, app.get("stars", []), app.get("hints", []))
            reports.append({
                "app_id": app["app_id"], "app_name": app["app_name"],
                "report_date": due_date.strftime("%Y-%m-%d"),
                "users": sorted({x["User"] for x in found}),
                "detailed_rows": found, "generated_at": now_ist.isoformat()
            })
            generated += 1
    if generated: save_json(DAILY_DB_PATH, reports)
    return generated

# --------- UPGRADED UI PAGES ---------
def render_manual_page():
    st.markdown("### 🔍 Live Analysis")
    if "manual_results" not in st.session_state: st.session_state.manual_results = []
    
    with st.container():
        col_a, col_b = st.columns([1, 1])
        with col_a:
            mode = st.radio("Search Mode", ["Single Link", "Bulk Mode"], horizontal=True)
            target_date = st.date_input("Filter Date", datetime.now(IST_TZ).date())
        with col_b:
            scan_depth = st.select_slider("Search Depth", options=[1, 5, 10, 20, 50], value=10)
            hint_val = st.text_input("End-Hint Symbol", value="#")

    if mode == "Single Link":
        urls = [st.text_input("Enter App Link", placeholder="https://play.google.com/...")]
    else:
        urls = [u.strip() for u in st.text_area("Paste Multiple Links (One per line)").split("\n") if u.strip()]

    if st.button("🚀 Start Professional Scan"):
        st.session_state.manual_results = []
        for u in urls:
            aid = extract_id(u)
            if aid: st.session_state.manual_results.extend(fetch_logic(aid, target_date, scan_depth, hint_values=[hint_val] if hint_val else []))
        st.rerun()

    if st.session_state.manual_results:
        df = pd.DataFrame(st.session_state.manual_results)
        st.markdown(f'<span class="live-badge">Verified Live: {len(df)}</span>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Pro Export
        output = io.BytesIO()
        df.to_excel(output, index=False)
        st.download_button("📥 Export Report to Excel", output.getvalue(), f"RW_Report_{target_date}.xlsx")

def render_admin_page():
    st.markdown("### 🛠️ Campaign Manager")
    apps = load_json(APP_DB_PATH)
    
    with st.expander("➕ Add New Campaign", expanded=False):
        with st.form("new_app"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Client/App Name")
            link = c2.text_input("Play Store Link")
            h = c1.text_input("Hints (comma separated)")
            d = c2.number_input("Days After (0 for same day)", min_value=0, value=7)
            if st.form_submit_button("💾 Save to Database"):
                aid = extract_id(link)
                apps.append({
                    "app_name": name, "app_id": aid, "app_url": link,
                    "hints": [x.strip() for x in h.split(",") if x.strip()],
                    "days_after": int(d), "created_at": datetime.now(IST_TZ).isoformat()
                })
                save_json(APP_DB_PATH, apps); st.rerun()

    st.markdown("#### Active Monitoring")
    for i, app in enumerate(apps):
        with st.container():
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            col1.markdown(f"**{app['app_name']}** <br> <code style='font-size:0.7rem'>{app['app_id']}</code>", unsafe_allow_html=True)
            col2.write(f"📅 Day {app['days_after']}")
            if col3.button("📋 Copy", key=f"c_{i}"):
                apps.append(app.copy()); save_json(APP_DB_PATH, apps); st.rerun()
            if col4.button("🗑️ Del", key=f"d_{i}"):
                apps.pop(i); save_json(APP_DB_PATH, apps); st.rerun()

def render_daily_list_page():
    st.markdown("### 📊 Auto-Generated Intelligence")
    if st.button("♻️ Force Sync Now"): run_due_daily_jobs(); st.rerun()
    
    reports = load_json(DAILY_DB_PATH)
    if not reports:
        st.info("No reports have been triggered yet. Add an app with '0 days' to test.")
    else:
        for i, r in enumerate(reversed(reports)):
            with st.container():
                st.markdown(f"""
                <div class="report-card">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-weight:700; color:#1e293b;">{r['app_name']}</span>
                        <span class="live-badge">{len(r['users'])} Live</span>
                    </div>
                    <p style="font-size:0.8rem; color:#64748b; margin:5px 0;">Target Date: {r['report_date']}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button("❌ Remove Report", key=f"dr_{i}"):
                    reports.remove(r); save_json(DAILY_DB_PATH, reports); st.rerun()

# --------- Main Navigation ---------
ensure_db_files()
logo = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"

# Premium Header
st.markdown(f"""
    <div class="brand-container">
        <img src="{logo}" width="70">
        <div>
            <h1 style='margin:0; font-size:1.8rem;'>RW PRO LIVE CHECKER</h1>
            <p style='margin:0; opacity:0.8;'>Reviews World Digital Operations Dashboard</p>
        </div>
    </div>
""", unsafe_allow_html=True)

if "page" not in st.session_state: st.session_state.page = "home"

# Professional Sidebar Nav
with st.sidebar:
    st.markdown("### 🗺️ Navigation")
    if st.button("🏠 Home Dashboard", use_container_width=True): st.session_state.page = "home"; st.rerun()
    if st.button("✨ Make New List", use_container_width=True): st.session_state.page = "manual"; st.rerun()
    if st.button("⚙️ Campaign Setup", use_container_width=True): st.session_state.page = "admin"; st.rerun()
    if st.button("📈 Daily Reports", use_container_width=True): st.session_state.page = "daily"; st.rerun()
    st.divider()
    st.info("System Online: IST")

if st.session_state.page == "home":
    st.markdown("## Welcome back, Yash.")
    st.write("Current Status: Monitoring active reviews across Google Play Store.")
    
    # Quick Action Tiles
    c1, c2, c3 = st.columns(3)
    with c1: 
        if st.button("New Manual Scan"): st.session_state.page = "manual"; st.rerun()
    with c2: 
        if st.button("Configure Apps"): st.session_state.page = "admin"; st.rerun()
    with c3: 
        if st.button("Review History"): st.session_state.page = "daily"; st.rerun()

elif st.session_state.page == "manual": render_manual_page()
elif st.session_state.page == "admin": render_admin_page()
elif st.session_state.page == "daily": render_daily_list_page()
