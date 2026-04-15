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
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .main { background: #fdfdfd; }
    .header-box {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 2rem; border-radius: 24px; color: white; margin-bottom: 2rem;
    }
    .report-card {
        background: white; border: 1px solid #f1f5f9; border-radius: 16px;
        padding: 1.25rem; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .badge { padding: 4px 12px; border-radius: 8px; font-size: 0.75rem; font-weight: 700; }
    .badge-time { background: #fef9c3; color: #854d0e; }
    .badge-live { background: #dcfce7; color: #166534; }
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
        # SAFETY FIX: Use .get() to prevent KeyError if field is missing
        created_at_raw = app.get("created_at", datetime.now(IST_TZ).isoformat())
        created_dt = datetime.fromisoformat(created_at_raw)
        days_after = app.get("days_after", 0)
        target_date = (created_dt + timedelta(days=days_after)).date()
        
        run_time_str = app.get("run_time", "08:00 PM")
        try:
            run_time_obj = datetime.strptime(run_time_str, "%I:%M %p").time()
        except:
            run_time_obj = datetime.strptime("08:00 PM", "%I:%M %p").time()

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
            df.to_excel(output, index=False); st.download_button("📥 Download Report", output.getvalue(), "Report.xlsx")

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
                "days_after": int(days), "run_time": time_val, "created_at": datetime.now(IST_TZ).isoformat()
            })
            save_json(APP_DB_PATH, apps); st.rerun()

    st.markdown("---")
    # SAFETY FIX: Handling missing keys in loop
    for i, app in enumerate(apps):
        name = app.get("app_name", "Unknown")
        aid = app.get("app_id", "Unknown")
        days = app.get("days_after", 0)
        rtime = app.get("run_time", "08:00 PM")
        with st.container():
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.markdown(f"**{name}** | `{aid}`<br><span class='badge badge-time'>Every {days} Days at {rtime}</span>", unsafe_allow_html=True)
            if c2.button("📋 Copy", key=f"cp_{i}"):
                new_app = app.copy(); new_app["app_name"] = name + " (Copy)"
                apps.append(new_app); save_json(APP_DB_PATH, apps); st.rerun()
            if c3.button("🗑️ Del", key=f"dl_{i}"):
                apps.pop(i); save_json(APP_DB_PATH, apps); st.rerun()

def render_daily():
    st.subheader("Generated Daily Reports")
    if st.button("🔄 Refresh & Check for New Lists"): run_automation(); st.rerun()
    reports = load_json(DAILY_DB_PATH)
    if not reports:
        st.info("No reports yet. Add an app with '0 days' and past 'Run Time' to generate one.")
    else:
        for i, r in enumerate(reversed(reports)):
            with st.container():
                st.markdown(f"""<div class="report-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:800;">{r.get('app_name', 'Unknown')}</span>
                        <span class="badge badge-live">{len(r.get('users', []))} Live</span>
                    </div>
                    <p style="margin:5px 0; color:#64748b; font-size:0.85rem;">Date: {r.get('report_date')} | Generated: {r.get('generated_at')}</p>
                </div>""", unsafe_allow_html=True)
                if st.button("🗑️ Delete Report", key=f"dre_{i}"):
                    reports.remove(r); save_json(DAILY_DB_PATH, reports); st.rerun()

# --------- Main Nav ---------
ensure_db_files()
st.markdown(f'<div class="header-box"><h1>RW PRO LIVE CHECKER</h1></div>', unsafe_allow_html=True)
if "page" not in st.session_state: st.session_state.page = "home"
with st.sidebar:
    if st.button("🏠 Home", use_container_width=True): st.session_state.page = "home"; st.rerun()
    if st.button("📊 Manual Scan", use_container_width=True): st.session_state.page = "manual"; st.rerun()
    if st.button("⚙️ Setup App", use_container_width=True): st.session_state.page = "admin"; st.rerun()
    if st.button("📁 Daily Lists", use_container_width=True): st.session_state.page = "daily"; st.rerun()

if st.session_state.page == "home": st.markdown("### Welcome, Yash")
elif st.session_state.page == "manual": render_manual()
elif st.session_state.page == "admin": render_admin()
elif st.session_state.page == "daily": render_daily()
