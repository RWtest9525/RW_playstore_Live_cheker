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

# 2. Perfect UI Styling (Wahi purana layout, par clean)
st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem !important; }
    .stButton > button {
        width: 100% !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
        height: 3rem !important;
    }
    .brand-wrap {
        display: flex; align-items: center; justify-content: space-between;
        border: 1px solid #e5e7eb; border-radius: 16px; padding: 15px 20px;
        margin-bottom: 20px; background: white;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .nav-card {
        border: 1px solid #e2e8f0; border-radius: 12px;
        background: #f8fafc; padding: 20px; margin-bottom: 15px;
        text-align: center;
    }
    .report-card {
        border-left: 5px solid #6366f1; background: #ffffff;
        padding: 15px; border-radius: 8px; margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
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

# --------- Storage Logic ---------
def ensure_db():
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

# --------- CORE SCRAPER (Anti-Ben Hoek) ---------
def fetch_logic(aid, target_dt, depth, stars=None, hints=None):
    all_raw = []
    token = None
    stop_date = target_dt - timedelta(days=2)
    for _ in range(depth):
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
        matches.append({"User": r.get("userName"), "Rating": r.get("score"), "Review": text, "App ID": aid})
    return matches

def run_automation():
    apps = load_json(APP_DB_PATH)
    reports = load_json(DAILY_DB_PATH)
    now = datetime.now(IST_TZ)
    report_index = {(r["app_id"], r["report_date"]) for r in reports}
    
    for app in apps:
        created_dt = datetime.fromisoformat(app.get("created_at", now.isoformat()))
        target_date = (created_dt + timedelta(days=app.get("days_after", 0))).date()
        run_time_obj = datetime.strptime(app.get("run_time", "08:00 PM"), "%I:%M %p").time()

        if target_date <= now.date() and now.time() >= run_time_obj:
            if (app["app_id"], target_date.strftime("%Y-%m-%d")) not in report_index:
                found = fetch_logic(app["app_id"], target_date, 10, app.get("stars"), app.get("hints"))
                reports.append({
                    "app_id": app["app_id"], "app_name": app.get("app_name"),
                    "report_date": target_date.strftime("%Y-%m-%d"),
                    "users": sorted({x["User"] for x in found}),
                    "generated_at": now.strftime("%I:%M %p")
                })
                save_json(DAILY_DB_PATH, reports)

# --------- Header Section ---------
st.markdown(f"""
    <div class="brand-wrap">
        <div style="display:flex; align-items:center; gap:15px;">
            <img src="{LOGO_URL}" width="60">
            <div>
                <h2 style="margin:0;">RW PRO LIVE CHECKER</h2>
                <p style="margin:0; color:#64748b;">Reviews World Intelligence</p>
            </div>
        </div>
        <div style="text-align:right; color:#94a3b8; font-size:0.8rem;">IST: {datetime.now(IST_TZ).strftime('%I:%M %p')}</div>
    </div>
""", unsafe_allow_html=True)

# --------- Navigation ---------
ensure_db()
if "page" not in st.session_state: st.session_state.page = "home"

# Home Layout (Original 3 Column)
if st.session_state.page == "home":
    st.markdown('<div class="nav-card">Choose Workflow</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if c1.button("📊 Make List"): st.session_state.page = "manual"; st.rerun()
    if c2.button("⚙️ Add App"): st.session_state.page = "admin"; st.rerun()
    if c3.button("📁 View Generated List"): st.session_state.page = "daily"; st.rerun()

else:
    if st.button("⬅️ Back to Home"): st.session_state.page = "home"; st.rerun()

    # MANUAL SCAN PAGE
    if st.session_state.page == "manual":
        st.subheader("Manual Scraper")
        t_date = st.date_input("Review Date", datetime.now(IST_TZ).date())
        urls = st.text_area("Paste Links (One per line)")
        hint = st.text_input("Hint Symbol", "#")
        if st.button("🚀 Start Scan"):
            all_res = []
            for u in [x.strip() for x in urls.split("\n") if x.strip()]:
                all_res.extend(fetch_logic(extract_id(u), t_date, 10, hints=[hint] if hint else []))
            if all_res:
                df = pd.DataFrame(all_res)
                st.dataframe(df, use_container_width=True)
                output = io.BytesIO()
                df.to_excel(output, index=False)
                st.download_button("📥 Download Excel", output.getvalue(), "Manual_Report.xlsx")

    # ADMIN PAGE (ADD / COPY / DELETE)
    elif st.session_state.page == "admin":
        st.subheader("Campaign Setup")
        apps = load_json(APP_DB_PATH)
        with st.form("add_form", clear_on_submit=True):
            col_1, col_2 = st.columns(2)
            n = col_1.text_input("App Name")
            l = col_2.text_input("Link")
            h = col_1.text_input("Hints (comma separated)")
            d = col_2.number_input("Days After (0=Today)", min_value=0, value=7)
            tm = st.selectbox("Run Time", ["08:00 AM", "12:00 PM", "04:00 PM", "08:00 PM", "10:00 PM", "11:59 PM"])
            if st.form_submit_button("Save Setup"):
                apps.append({"app_name": n, "app_id": extract_id(l), "hints": [x.strip() for x in h.split(",")], "days_after": d, "run_time": tm, "created_at": datetime.now(IST_TZ).isoformat()})
                save_json(APP_DB_PATH, apps); st.rerun()
        
        st.divider()
        for i, app in enumerate(apps):
            with st.container():
                c_a, c_b, c_c = st.columns([4, 1, 1])
                c_a.write(f"**{app.get('app_name')}** | Day {app.get('days_after')} at {app.get('run_time')}")
                if c_b.button("Copy", key=f"cp{i}"):
                    apps.append(app.copy()); save_json(APP_DB_PATH, apps); st.rerun()
                if c_c.button("Del", key=f"dl{i}"):
                    apps.pop(i); save_json(APP_DB_PATH, apps); st.rerun()

    # VIEW GENERATED LIST PAGE
    elif st.session_state.page == "daily":
        st.subheader("Auto-Generated Reports")
        if st.button("🔄 Sync Lists"): run_automation(); st.rerun()
        reports = load_json(DAILY_DB_PATH)
        if not reports: st.info("No reports yet.")
        for i, r in enumerate(reversed(reports)):
            with st.container():
                st.markdown(f"""<div class="report-card"><b>{r.get('app_name')}</b> | {r.get('report_date')} | {len(r.get('users'))} Live</div>""", unsafe_allow_html=True)
                with st.expander("View Users"): st.write(", ".join(r.get("users")))
                if st.button("Delete Report", key=f"dr{i}"):
                    reports.remove(r); save_json(DAILY_DB_PATH, reports); st.rerun()
