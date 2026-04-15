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

# 2. Premium Professional CSS
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    code { font-family: 'JetBrains Mono', monospace; }

    .main { background: #fdfdfd; }
    
    /* Header Design */
    .header-box {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 2.5rem;
        border-radius: 24px;
        color: white;
        margin-bottom: 2rem;
        border: 1px solid rgba(255,255,255,0.1);
    }

    /* List Item Cards */
    .report-card {
        background: white;
        border: 1px solid #f1f5f9;
        border-radius: 16px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: all 0.2s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .report-card:hover {
        border-color: #6366f1;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05);
    }

    /* Status Badges */
    .badge {
        padding: 4px 12px;
        border-radius: 8px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .badge-live { background: #dcfce7; color: #166534; }
    .badge-time { background: #fef9c3; color: #854d0e; }

    /* Buttons */
    .stButton>button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

IST_TZ = pytz.timezone("Asia/Kolkata")
DATA_DIR = "data"
APP_DB_PATH = os.path.join(DATA_DIR, "apps_config.json")
DAILY_DB_PATH = os.path.join(DATA_DIR, "daily_reports.json")

# --------- Logic Core ---------
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

        matches.append({
            "User": r.get("userName", "Unknown"),
            "Rating": f"{r.get('score', 0)}/5",
            "Review": text,
            "App ID": aid,
            "Date": rev_dt.strftime("%Y-%m-%d")
        })
    return matches

def run_automation():
    apps = load_json(APP_DB_PATH)
    reports = load_json(DAILY_DB_PATH)
    now = datetime.now(IST_TZ)
    report_index = {(r["app_id"], r["report_date"]) for r in reports}
    
    updated = False
    for app in apps:
        created_dt = datetime.fromisoformat(app["created_at"])
        target_date = (created_dt + timedelta(days=app.get("days_after", 0))).date()
        
        # Check Time Logic
        run_time_obj = datetime.strptime(app.get("run_time", "08:00 PM"), "%I:%M %p").time()
        current_time_obj = now.time()
        
        # If today is the target date AND current time is past run_time
        if target_date <= now.date() and current_time_obj >= run_time_obj:
            report_key = (app["app_id"], target_date.strftime("%Y-%m-%d"))
            if report_key not in report_index:
                found = fetch_logic(app["app_id"], target_date, 10, app.get("stars"), app.get("hints"))
                reports.append({
                    "app_id": app["app_id"], "app_name": app["app_name"],
                    "report_date": target_date.strftime("%Y-%m-%d"),
                    "users": sorted({x["User"] for x in found}),
                    "detailed_rows": found, "generated_at": now.strftime("%I:%M %p, %d %b")
                })
                updated = True
    if updated: save_json(DAILY_DB_PATH, reports)

# --------- Pages ---------
def render_manual():
    st.subheader("Manual Review Scan")
    target_date = st.date_input("Select Review Date", datetime.now(IST_TZ).date())
    urls = st.text_area("Paste Play Store Links (One per line)")
    hint = st.text_input("Hint Symbol", "#")
    
    if st.button("🚀 Run Professional Check"):
        links = [u.strip() for u in urls.split("\n") if u.strip()]
        all_results = []
        for l in links:
            aid = extract_id(l)
            with st.spinner(f"Checking {aid}..."):
                all_results.extend(fetch_logic(aid, target_date, 10, hints=[hint] if hint else []))
        
        if all_results:
            df = pd.DataFrame(all_results)
            st.success(f"Total Live Found: {len(df)}")
            st.dataframe(df, use_container_width=True)
            output = io.BytesIO()
            df.to_excel(output, index=False)
            st.download_button("📥 Download Report", output.getvalue(), "Manual_Report.xlsx")

def render_admin():
    st.subheader("Setup New Campaign")
    apps = load_json(APP_DB_PATH)
    
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("App Name")
        link = col2.text_input("Play Store Link")
        hints = col1.text_input("Hints (comma separated)")
        days = col2.number_input("Days After (0 = Today)", min_value=0, value=7)
        time_val = st.selectbox("Run Time (IST)", ["08:00 AM", "12:00 PM", "04:00 PM", "08:00 PM", "10:00 PM", "11:59 PM"])
        
        if st.form_submit_button("💾 Save App Config"):
            apps.append({
                "app_name": name, "app_id": extract_id(link), "app_url": link,
                "hints": [x.strip() for x in hints.split(",") if x.strip()],
                "days_after": int(days), "run_time": time_val,
                "created_at": datetime.now(IST_TZ).isoformat()
            })
            save_json(APP_DB_PATH, apps); st.rerun()

    st.markdown("---")
    for i, app in enumerate(apps):
        with st.container():
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.markdown(f"**{app['app_name']}** | `{app['app_id']}`<br><span class='badge badge-time'>Every {app['days_after']} Days at {app['run_time']}</span>", unsafe_allow_html=True)
            if c2.button("📋 Copy", key=f"cp_{i}"):
                new_app = app.copy(); new_app["app_name"] += " (Copy)"
                apps.append(new_app); save_json(APP_DB_PATH, apps); st.rerun()
            if c3.button("🗑️ Del", key=f"dl_{i}"):
                apps.pop(i); save_json(APP_DB_PATH, apps); st.rerun()

def render_daily():
    st.subheader("Generated Daily Reports")
    run_automation()
    reports = load_json(DAILY_DB_PATH)
    
    if not reports:
        st.info("No reports generated. Try adding an app with '0 days' and setting time to '08:00 AM'.")
    else:
        for i, r in enumerate(reversed(reports)):
            with st.container():
                st.markdown(f"""
                <div class="report-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:800; font-size:1.1rem;">{r['app_name']}</span>
                        <span class="badge badge-live">{len(r['users'])} Live Reviews</span>
                    </div>
                    <p style="margin:8px 0; color:#64748b; font-size:0.85rem;">
                        Target Date: <b>{r['report_date']}</b> | Generated: {r['generated_at']}
                    </p>
                </div>
                """, unsafe_allow_html=True)
                col1, col2 = st.columns([4, 1])
                with col1:
                    with st.expander("Show User List"):
                        st.write(", ".join(r['users']))
                with col2:
                    if st.button("🗑️ Delete", key=f"dre_{i}"):
                        reports.remove(r); save_json(DAILY_DB_PATH, reports); st.rerun()

# --------- Main Nav ---------
ensure_db_files()
logo = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"

st.markdown(f"""
<div class="header-box">
    <div style="display:flex; align-items:center; gap:20px;">
        <img src="{logo}" width="80">
        <div>
            <h1 style="margin:0; letter-spacing:-1px;">RW PRO LIVE CHECKER</h1>
            <p style="margin:0; opacity:0.7;">Intelligent Bulk Scraper & Review Monitor</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if "page" not in st.session_state: st.session_state.page = "home"

with st.sidebar:
    st.markdown("### 💠 Menu")
    if st.button("🏠 Home Dashboard", use_container_width=True): st.session_state.page = "home"; st.rerun()
    if st.button("📊 Make List (Manual)", use_container_width=True): st.session_state.page = "manual"; st.rerun()
    if st.button("⚙️ Add App Setup", use_container_width=True): st.session_state.page = "admin"; st.rerun()
    if st.button("📁 View Generated Lists", use_container_width=True): st.session_state.page = "daily"; st.rerun()
    st.divider()
    st.markdown(f"**Status:** `System Live`<br>**Region:** `India/IST`", unsafe_allow_html=True)

if st.session_state.page == "home":
    st.markdown("### 👋 Welcome, Yash")
    st.write("Use the sidebar to navigate. The system automatically scans your apps based on the schedule you set.")
elif st.session_state.page == "manual": render_manual()
elif st.session_state.page == "admin": render_admin()
elif st.session_state.page == "daily": render_daily()
