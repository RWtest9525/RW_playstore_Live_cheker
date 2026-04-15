import io
import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import pytz
import streamlit as st
from google_play_scraper import Sort, reviews
from PIL import Image

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
    .small-counter {
        border: 1px solid #2ecc71;
        background-color: #f0fff4;
        padding: 8px 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        display: inline-block;
    }
    .small-counter b { color: #16a34a; font-size: 18px; }
    .brand-wrap {
        display: flex; align-items: center; justify-content: space-between;
        border: 1px solid #e5e7eb; border-radius: 16px; padding: 12px 16px;
        margin-bottom: 14px; background: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- HEADER ---
logo_url = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"
st.markdown(
    f"""
    <div class="brand-wrap">
      <div style="display: flex; align-items: center; gap: 14px;">
        <img src="{logo_url}" width="54">
        <div>
          <h2 style="margin:0;">RW Playstore Live Checker</h2>
          <p style="margin:0; color:#64748b;">Premium Review Intelligence</p>
        </div>
      </div>
      <div style="text-align:right; font-size:0.85rem; color:#64748b;">Company: Reviews World Digital</div>
    </div>
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
    for path in [APP_DB_PATH, DAILY_DB_PATH]:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump([], f)

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

def review_matches_hint(text, hints):
    if not hints: return True
    return any(text.strip().endswith(hint) for hint in hints)

# --------- CORE FETCH LOGIC (FIXED) ---------
def fetch_logic(aid, target_dt, depth_pages, star_values=None, hint_values=None):
    all_raw = []
    token = None
    
    # "Anti-Ben Hoek" Strategy: Continue even if pinned reviews appear
    # We only stop when we see reviews that are actually 2 days old
    stop_date = target_dt - timedelta(days=2)
    
    for _ in range(depth_pages):
        try:
            res, token = reviews(
                aid, lang="en", country="in",
                sort=Sort.NEWEST, count=100, continuation_token=token
            )
            if not res: break
            all_raw.extend(res)
            
            # Check the date of the last item in this batch
            last_item_dt = res[-1]["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
            if last_item_dt < stop_date: break
            if not token: break
        except: break

    stars_set = set(star_values or [])
    matches = []
    for r in all_raw:
        rev_dt = r["at"].replace(tzinfo=pytz.utc).astimezone(IST_TZ).date()
        
        # 1. Date Filter (The most important check)
        if rev_dt != target_dt: continue
        
        # 2. Star Filter
        if stars_set and int(r.get("score", 0)) not in stars_set: continue
        
        # 3. Hint Filter
        text = (r.get("content") or "").strip()
        if not review_matches_hint(text, hint_values): continue

        matches.append({
            "User": r.get("userName", "Unknown"),
            "User Logo": r.get("userImage", ""),
            "Rating": f"{r.get('score', 0)}/5",
            "Review": text,
            "Date": rev_dt.strftime("%Y-%m-%d"),
            "App ID": aid
        })
    return matches

# --------- Pages ---------
def render_manual_page():
    st.subheader("Professional Review Checker")
    
    if "manual_results" not in st.session_state: st.session_state.manual_results = []
    
    mode = st.sidebar.radio("Mode", ["Single App", "Bulk Links"])
    target_date = st.sidebar.date_input("Target Date", datetime.now(IST_TZ).date())
    scan_depth = st.sidebar.select_slider("Depth", options=[1, 5, 10, 20, 50], value=10)
    
    hint_val = st.sidebar.text_input("Hint Symbol (Optional)", value="#")
    hints = [hint_val] if hint_val else []

    if mode == "Single App":
        url = st.sidebar.text_input("Play Store Link", "https://play.google.com/store/apps/details?id=com.ideopay.user")
        urls = [url]
    else:
        bulk_text = st.sidebar.text_area("Paste Links (One per line)")
        urls = [u.strip() for u in bulk_text.split("\n") if u.strip()]

    if st.button("🚀 Run Live Check"):
        st.session_state.manual_results = []
        progress = st.progress(0)
        
        for idx, u in enumerate(urls):
            aid = extract_id(u)
            with st.spinner(f"Scanning: {aid}"):
                found = fetch_logic(aid, target_date, scan_depth, hint_values=hints)
                st.session_state.manual_results.extend(found)
            progress.progress((idx + 1) / len(urls))
        
        st.success(f"Scanning Complete! Found {len(st.session_state.manual_results)} live reviews.")

    if st.session_state.manual_results:
        df = pd.DataFrame(st.session_state.manual_results)
        st.markdown(f'<div class="small-counter">Total Live: <b>{len(df)}</b></div>', unsafe_allow_html=True)
        
        # Display data
        st.dataframe(df, use_container_width=True)
        
        # Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Live_Report")
        
        st.download_button("📥 Download Excel Report", output.getvalue(), f"Report_{target_date}.xlsx", "application/vnd.ms-excel")

# --------- Navigation ---------
ensure_db_files()
if "page" not in st.session_state: st.session_state.page = "home"

if st.session_state.page == "home":
    st.subheader("Welcome, Yash")
    col1, col2 = st.columns(2)
    if col1.button("✨ Make New List"): 
        st.session_state.page = "manual"; st.rerun()
    if col2.button("⚙️ Admin Panel"): 
        st.session_state.page = "admin"; st.rerun()
else:
    if st.button("⬅️ Back to Home"): 
        st.session_state.page = "home"; st.rerun()
    if st.session_state.page == "manual": render_manual_page()
