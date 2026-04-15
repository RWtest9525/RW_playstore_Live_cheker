import io
import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st
from google_play_scraper import Sort, reviews

# 1. Page Config
st.set_page_config(page_title="RW Pro Live Checker", page_icon="🚀", layout="wide")

# 2. Premium Professional CSS (Indigo & Slate Theme)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    
    .main { background: #fdfdfd; }
    
    /* Header Styling */
    .header-container {
        background: #1e1b4b; /* Indigo 950 */
        padding: 2rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        display: flex;
        align-items: center;
        gap: 20px;
    }
    
    /* Sidebar Overhaul */
    [data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Card Design */
    .report-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Global Buttons */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

IST_TZ = pytz.timezone("Asia/Kolkata")
DATA_DIR = "data"
APP_DB_PATH = os.path.join(DATA_DIR, "apps_config.json")
DAILY_DB_PATH = os.path.join(DATA_DIR, "daily_reports.json")
LOGO_URL = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"

# --------- Logic Core ---------
def ensure_db_files():
    if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
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

def fetch_logic(aid, target_dt, depth_pages, stars=None, hints=None):
    all_raw = []
    token = None
    stop_date = target_dt - timedelta(days=2) # Anti-Ben Hoek Safety
    for _ in range(depth_pages):
        try:
            res, token = reviews(aid, lang="en", country="in", sort=Sort.NEWEST, count=100, continuation_token=token)
            if not res: break
            all_raw.extend(res)
            last_dt = res[-1]["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
            if last_dt < stop_date: break
            if not token: break
        except: break
    
    matches = []
    for r in all_raw:
        rev_dt = r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
        if rev_dt != target_dt: continue
        if stars and int(r.get("score", 0)) not in stars: continue
        text = (r.get("content") or "").strip()
        if hints and not any(text.endswith(h) for h in hints): continue
        matches.append({"User": r.get("userName", "Unknown"), "Rating": f"{r.get('score', 0)}/5", "Review": text, "App ID": aid})
    return matches

def run_automation():
    apps = load_json(APP_DB_PATH)
    reports = load_json(DAILY_DB_PATH)
    now = datetime.now(IST_TZ)
    report_index = {(r["app_id"], r["report_date"]) for r in reports}
    updated = False
    for app in apps:
        created_dt = datetime.fromisoformat(app.get("created_at", now.isoformat()))
        days_after = app.get("days_after", 0)
        target_date = (created_dt + timedelta(days=days_after)).date()
        
        run_time_str = app.get("run_time", "08:00 PM")
        run_time_obj = datetime.strptime(run_time_str, "%I:%M %p").time()

        if target_date <= now.date() and now.time() >= run_time_obj:
            report_key = (app["app_id"], target_date.strftime("%Y-%m-%d"))
            if report_key not in report_index:
                found = fetch_logic(app["app_id"], target_date, 10, app.get("stars"), app.get("hints"))
                reports.append({
                    "app_id": app["app_id"], "app_name": app.get("app_name", "Unknown"),
                    "report_date": target_date.strftime("%Y-%m-%d"),
                    "users": sorted({x["User"] for x in found}),
                    "detailed_rows": found, "generated_at": now.strftime("%I:%M %p, %d %b")
                })
                updated = True
    if updated: save_json(DAILY_DB_PATH, reports)

# --------- Navigation Content ---------
def render_home():
    st.title("Welcome back, Yash")
    st.write("Current Status: All systems operational. Scraper running on IST.")

def render_manual():
    st.subheader("Manual Bulk Checker")
    t_date = st.date_input("Filter Date", datetime.now(IST_TZ).date())
    urls = st.text_area("Paste Links (One per line)")
    hint = st.text_input("Hint (Optional)", "#")
    if st.button("🚀 Start Live Scan"):
        all_res = []
        for u in [x.strip() for x in urls.split("\n") if x.strip()]:
            aid = extract_id(u)
            with st.spinner(f"Scanning {aid}..."):
                all_res.extend(fetch_logic(aid, t_date, 10, hints=[hint] if hint else []))
        if all_res:
            df = pd.DataFrame(all_res)
            st.success(f"Verified {len(df)} Live Reviews")
            st.dataframe(df, use_container_width=True, hide_index=True)
            output = io.BytesIO()
            df.to_excel(output, index=False)
            st.download_button("📥 Excel Export", output.getvalue(), f"Report_{t_date}.xlsx")

def render_admin():
    st.subheader("Campaign Setup")
    apps = load_json(APP_DB_PATH)
    with st.form("add_app"):
        c1, c2 = st.columns(2)
        n = c1.text_input("Client Name")
        l = c2.text_input("App Link")
        h = c1.text_input("Hints (e.g. #, @@)")
        d = c2.number_input("Days After (0 = Today)", min_value=0, value=7)
        rt = st.selectbox("Run Time (IST)", ["08:00 AM", "12:00 PM", "04:00 PM", "08:00 PM", "10:00 PM", "11:59 PM"])
        if st.form_submit_button("💾 Save App"):
            apps.append({
                "app_name": n, "app_id": extract_id(l), "app_url": l,
                "hints": [x.strip() for x in h.split(",") if x.strip()],
                "days_after": int(d), "run_time": rt, "created_at": datetime.now(IST_TZ).isoformat()
            })
            save_json(APP_DB_PATH, apps); st.rerun()

    st.divider()
    for i, app in enumerate(apps):
        with st.container():
            col_a, col_b, col_c = st.columns([4, 1, 1])
            col_a.markdown(f"**{app.get('app_name')}** | `{app.get('app_id')}`<br><small>Schedule: {app.get('run_time')} (Day {app.get('days_after')})</small>", unsafe_allow_html=True)
            if col_b.button("📋 Copy", key=f"cp{i}"):
                apps.append(app.copy()); save_json(APP_DB_PATH, apps); st.rerun()
            if col_c.button("🗑️ Del", key=f"dl{i}"):
                apps.pop(i); save_json(APP_DB_PATH, apps); st.rerun()

def render_daily():
    st.subheader("Daily History")
    if st.button("🔄 Sync New Reports"): run_automation(); st.rerun()
    reports = load_json(DAILY_DB_PATH)
    if not reports: st.info("No auto-reports yet.")
    for i, r in enumerate(reversed(reports)):
        with st.expander(f"{r.get('app_name')} - {r.get('report_date')} ({len(r.get('users'))} Live)"):
            st.write(", ".join(r.get("users")))
            if st.button("Delete Report", key=f"dr{i}"):
                reports.remove(r); save_json(DAILY_DB_PATH, reports); st.rerun()

# --------- Main App ---------
ensure_db_files()

# LOGO FIX: Using st.columns to center the header content properly
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.image(LOGO_URL, width=80)
with col_title:
    st.title("RW PRO LIVE CHECKER")
    st.write("Professional Bulk Scraper for Reviews World")

if "page" not in st.session_state: st.session_state.page = "home"

with st.sidebar:
    st.markdown("### 🧭 Main Navigation")
    if st.button("🏠 Home Dashboard", use_container_width=True): st.session_state.page = "home"; st.rerun()
    if st.button("📊 Manual Bulk Check", use_container_width=True): st.session_state.page = "manual"; st.rerun()
    if st.button("⚙️ Campaign Setup", use_container_width=True): st.session_state.page = "admin"; st.rerun()
    if st.button("📁 Daily History", use_container_width=True): st.session_state.page = "daily"; st.rerun()
    st.divider()
    st.info(f"Time: {datetime.now(IST_TZ).strftime('%H:%M')} IST")

if st.session_state.page == "home": render_home()
elif st.session_state.page == "manual": render_manual()
elif st.session_state.page == "admin": render_admin()
elif st.session_state.page == "daily": render_daily()
