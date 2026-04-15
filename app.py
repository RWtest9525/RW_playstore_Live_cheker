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

# 2. UI Styling (Premium Indigo Theme)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #f8fafc; }
    .brand-container {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 2rem; border-radius: 20px; color: white; margin-bottom: 2rem;
        display: flex; align-items: center; gap: 20px;
    }
    .report-card {
        background: white; padding: 1.5rem; border-radius: 15px;
        border: 1px solid #e2e8f0; margin-bottom: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .live-badge {
        background: #ecfdf5; color: #065f46; padding: 4px 12px;
        border-radius: 8px; font-weight: 700; font-size: 0.8rem;
    }
    div.stButton > button { border-radius: 10px !important; font-weight: 600 !important; }
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

# --------- CORE FETCH LOGIC ---------
def fetch_logic(aid, target_dt, depth_pages, star_values=None, hint_values=None):
    all_raw = []
    token = None
    stop_date = target_dt - timedelta(days=2) 
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
        rev_time = r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ)
        if rev_time.date() != target_dt: continue
        if star_values and int(r.get("score", 0)) not in star_values: continue
        text = (r.get("content") or "").strip()
        if hint_values and not any(text.endswith(h) for h in hint_values): continue
        matches.append({"User": r.get("userName"), "Rating": r.get("score"), "Review": text, "App ID": aid})
    return matches

def run_automation():
    apps = load_json(APP_DB_PATH)
    reports = load_json(DAILY_DB_PATH)
    now = datetime.now(IST_TZ)
    report_index = {(r["app_id"], r["report_date"]) for r in reports}
    
    updated = False
    for app in apps:
        created_dt = datetime.fromisoformat(app.get("created_at", now.isoformat()))
        target_date = (created_dt + timedelta(days=app.get("days_after", 0))).date()
        
        # AM/PM Time Logic
        run_time_str = app.get("run_time", "08:00 PM")
        run_time_obj = datetime.strptime(run_time_str, "%I:%M %p").time()

        if target_date <= now.date() and now.time() >= run_time_obj:
            report_key = (app["app_id"], target_date.strftime("%Y-%m-%d"))
            if report_key not in report_index:
                found = fetch_logic(app["app_id"], target_date, 10, app.get("stars"), app.get("hints"))
                reports.append({
                    "app_id": app["app_id"], "app_name": app.get("app_name"),
                    "report_date": target_date.strftime("%Y-%m-%d"),
                    "users": sorted({x["User"] for x in found}),
                    "generated_at": now.strftime("%I:%M %p")
                })
                updated = True
    if updated: save_json(DAILY_DB_PATH, reports)

# --------- PAGES ---------
def render_manual_page():
    st.markdown("### 🔍 Manual Scraper")
    t_date = st.date_input("Review Date", datetime.now(IST_TZ).date())
    urls = st.text_area("Paste Links")
    hint = st.text_input("Hint Symbol", "#")
    if st.button("🚀 Run Check"):
        all_res = []
        for u in [x.strip() for x in urls.split("\n") if x.strip()]:
            all_res.extend(fetch_logic(extract_id(u), t_date, 10, hint_values=[hint] if hint else []))
        if all_res:
            st.dataframe(pd.DataFrame(all_res), use_container_width=True)

def render_admin_page():
    st.markdown("### 🛠️ Campaign Setup")
    apps = load_json(APP_DB_PATH)
    with st.form("add_app"):
        col1, col2 = st.columns(2)
        n = col1.text_input("App Name")
        l = col2.text_input("Play Store Link")
        h = col1.text_input("Hints (comma separated)")
        d = col2.number_input("Days After (0=Today)", min_value=0, value=7)
        tm = st.selectbox("Run Time (IST)", ["08:00 AM", "12:00 PM", "04:00 PM", "08:00 PM", "10:00 PM", "11:59 PM"])
        if st.form_submit_button("💾 Save App"):
            apps.append({"app_name": n, "app_id": extract_id(l), "hints": [x.strip() for x in h.split(",")], "days_after": int(d), "run_time": tm, "created_at": datetime.now(IST_TZ).isoformat()})
            save_json(APP_DB_PATH, apps); st.rerun()

    st.markdown("#### Active Campaigns")
    for i, app in enumerate(apps):
        cols = st.columns([5, 1])
        cols[0].write(f"**{app['app_name']}** | {app['run_time']} (Day {app['days_after']})")
        if cols[1].button("🗑️ Del", key=f"del_{i}"):
            apps.pop(i); save_json(APP_DB_PATH, apps); st.rerun()

def render_daily_list_page():
    st.markdown("### 📊 Generated Lists")
    if st.button("♻️ Sync Reports"): run_automation(); st.rerun()
    reports = load_json(DAILY_DB_PATH)
    
    for i, r in enumerate(reversed(reports)):
        with st.container():
            st.markdown(f"""
            <div class="report-card">
                <div style="display:flex; justify-content:space-between;">
                    <span style="font-weight:700;">{r['app_name']}</span>
                    <span class="live-badge">{len(r['users'])} Live</span>
                </div>
                <p style="font-size:0.8rem; color:#64748b; margin:5px 0;">Date: {r['report_date']} | Generated at: {r['generated_at']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns([1, 1, 4])
            # COPY LIST FEATURE
            list_text = f"App: {r['app_name']}\nDate: {r['report_date']}\nLive: {len(r['users'])}\n\nUsers:\n" + "\n".join([f"{idx+1}. {u}" for idx, u in enumerate(r['users'])])
            c1.download_button("📋 Copy List", list_text, file_name=f"{r['app_name']}_list.txt", key=f"cp_l_{i}")
            
            if c2.button("❌ Delete", key=f"del_r_{i}"):
                reports.remove(r); save_json(DAILY_DB_PATH, reports); st.rerun()

# --------- Main ---------
ensure_db_files()
logo = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"
st.markdown(f'<div class="brand-container"><img src="{logo}" width="70"><div><h1 style="margin:0;">RW PRO LIVE CHECKER</h1></div></div>', unsafe_allow_html=True)

if "page" not in st.session_state: st.session_state.page = "home"
with st.sidebar:
    if st.button("🏠 Home", use_container_width=True): st.session_state.page = "home"; st.rerun()
    if st.button("✨ Make List", use_container_width=True): st.session_state.page = "manual"; st.rerun()
    if st.button("⚙️ Add App", use_container_width=True): st.session_state.page = "admin"; st.rerun()
    if st.button("📁 View Lists", use_container_width=True): st.session_state.page = "daily"; st.rerun()

if st.session_state.page == "manual": render_manual_page()
elif st.session_state.page == "admin": render_admin_page()
elif st.session_state.page == "daily": render_daily_list_page()
else: st.write("Welcome back, Yash. Use the sidebar to manage your campaigns.")
