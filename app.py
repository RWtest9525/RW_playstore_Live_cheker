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

# 2. UI Styling
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem !important; }
    .stButton > button {
        width: 100% !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        background: linear-gradient(135deg, #f8fbff 0%, #edf4ff 100%) !important;
        color: #0f172a !important;
    }
    .brand-wrap {
        display: flex; align-items: center; justify-content: space-between;
        border: 1px solid #e5e7eb; border-radius: 16px; padding: 12px 16px;
        margin-bottom: 14px; background: white;
    }
    .report-card {
        border: 1px solid #dbeafe; border-radius: 14px; padding: 12px 14px;
        background: #f8fbff; margin-bottom: 10px;
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
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def extract_id(url):
    match = re.search(r"id=([a-zA-Z0-9._]+)", url)
    return match.group(1) if match else url.strip()

def normalize_csv_values(raw):
    return [x.strip() for x in str(raw).split(",") if x.strip()]

# --------- CORE FETCH LOGIC (ANTI-BEN HOEK) ---------
def fetch_logic(aid, target_dt, depth_pages, star_values=None, hint_values=None):
    all_raw = []
    token = None
    stop_date = target_dt - timedelta(days=2) # Deep search buffer
    
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
            "User Logo": r.get("userImage", ""),
            "Review": text,
            "App ID": aid,
            "Rating": f"{r.get('score', 0)}/5",
            "Date": rev_dt.strftime("%Y-%m-%d")
        })
    return matches

# --------- Logic for Automation ---------
def run_due_daily_jobs(scan_depth=500):
    apps = load_json(APP_DB_PATH)
    reports = load_json(DAILY_DB_PATH)
    now_ist = datetime.now(IST_TZ)
    report_index = {(r["app_id"], r["report_date"]) for r in reports}
    generated = 0

    for app in apps:
        created_dt = datetime.fromisoformat(app["created_at"])
        due_date = (created_dt + timedelta(days=app.get("days_after", 0))).date()
        
        # Check if due today
        report_key = (app["app_id"], due_date.strftime("%Y-%m-%d"))
        if due_date <= now_ist.date() and report_key not in report_index:
            found = fetch_logic(app["app_id"], due_date, scan_depth // 100, app.get("stars", []), app.get("hints", []))
            reports.append({
                "app_id": app["app_id"],
                "app_name": app["app_name"],
                "report_date": due_date.strftime("%Y-%m-%d"),
                "users": sorted({x["User"] for x in found}),
                "detailed_rows": found,
                "generated_at": now_ist.isoformat()
            })
            generated += 1
    
    if generated: save_json(DAILY_DB_PATH, reports)
    return generated

# --------- Pages ---------
def render_manual_page():
    st.subheader("Professional Review Checker")
    if "manual_results" not in st.session_state: st.session_state.manual_results = []
    
    mode = st.sidebar.radio("Mode", ["Single App", "Bulk Links"])
    target_date = st.sidebar.date_input("Target Date", datetime.now(IST_TZ).date())
    scan_depth = st.sidebar.select_slider("Depth", options=[1, 5, 10, 50, 100], value=10)
    hint_val = st.sidebar.text_input("Hint (e.g. #)", value="#")
    
    if mode == "Single App":
        urls = [st.sidebar.text_input("Play Store Link", "")]
    else:
        urls = [u.strip() for u in st.sidebar.text_area("Paste Links").split("\n") if u.strip()]

    if st.button("🚀 Run Check"):
        st.session_state.manual_results = []
        for u in urls:
            aid = extract_id(u)
            if aid: st.session_state.manual_results.extend(fetch_logic(aid, target_date, scan_depth, hint_values=[hint_val] if hint_val else []))
        st.success(f"Found {len(st.session_state.manual_results)} reviews.")

    if st.session_state.manual_results:
        df = pd.DataFrame(st.session_state.manual_results)
        st.dataframe(df, use_container_width=True)
        # Excel Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Excel Report", output.getvalue(), "Report.xlsx")

def render_admin_page():
    st.subheader("Admin Panel")
    apps = load_json(APP_DB_PATH)
    
    with st.form("add_app", clear_on_submit=True):
        name = st.text_input("App Name")
        link = st.text_input("Play Store Link")
        hints = st.text_input("Hints (comma separated)")
        stars = st.text_input("Stars (comma separated)", value="5")
        days = st.number_input("Days After (Set 0 for today)", min_value=0, value=7) # <--- 0 DAY ENABLED
        if st.form_submit_button("Save App"):
            aid = extract_id(link)
            apps.append({
                "app_name": name, "app_id": aid, "app_url": link,
                "hints": normalize_csv_values(hints),
                "stars": [int(s) for s in normalize_csv_values(stars) if s.isdigit()],
                "days_after": int(days), "created_at": datetime.now(IST_TZ).isoformat()
            })
            save_json(APP_DB_PATH, apps)
            st.success("App added!")
            st.rerun()

    st.markdown("### Existing Apps")
    for i, app in enumerate(apps):
        cols = st.columns([3, 1, 1])
        cols[0].write(f"**{app['app_name']}** ({app['app_id']}) - Days: {app['days_after']}")
        if cols[1].button("Copy", key=f"cp_{i}"):
            new_app = app.copy()
            new_app["app_name"] += " (Copy)"
            apps.append(new_app); save_json(APP_DB_PATH, apps); st.rerun()
        if cols[2].button("Delete", key=f"del_{i}"):
            apps.pop(i); save_json(APP_DB_PATH, apps); st.rerun()

def render_daily_list_page():
    st.subheader("Generated Lists")
    run_due_daily_jobs()
    reports = load_json(DAILY_DB_PATH)
    
    if not reports:
        st.info("No reports generated yet.")
    else:
        for i, r in enumerate(reversed(reports)):
            with st.expander(f"{r['app_name']} - {r['report_date']} ({len(r['users'])} live)"):
                st.write(f"Generated at: {r['generated_at']}")
                st.write(", ".join(r['users']))
                if st.button("Delete Report", key=f"del_rep_{i}"):
                    reports.remove(r); save_json(DAILY_DB_PATH, reports); st.rerun()

# --------- Main ---------
ensure_db_files()
logo_url = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"
st.markdown(f'<div class="brand-wrap"><img src="{logo_url}" width="54"><h2>RW Live Checker</h2></div>', unsafe_allow_html=True)

if "page" not in st.session_state: st.session_state.page = "home"
if st.session_state.page == "home":
    c1, c2, c3 = st.columns(3)
    if c1.button("Make List"): st.session_state.page = "manual"; st.rerun()
    if c2.button("Add App"): st.session_state.page = "admin"; st.rerun()
    if c3.button("View List"): st.session_state.page = "daily"; st.rerun()
else:
    if st.button("⬅️ Back"): st.session_state.page = "home"; st.rerun()
    if st.session_state.page == "manual": render_manual_page()
    elif st.session_state.page == "admin": render_admin_page()
    elif st.session_state.page == "daily": render_daily_list_page()
