import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime
import pytz
import os
import io

# 1. Page Config
st.set_page_config(page_title="RW Pro Live Checker", page_icon="🚀", layout="wide")

# --- FORCE CLEAR OLD HISTORY DATA ---
if 'history_list' in st.session_state:
    del st.session_state['history_list']
if 'history' in st.session_state:
    del st.session_state['history']

# 2. UI Styling
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; }
    .stButton > button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    .small-counter { 
        border: 1px solid #2ecc71; 
        background-color: #f0fff4; 
        padding: 8px 15px; 
        border-radius: 8px; 
        margin-bottom: 15px; 
        display: inline-block;
    }
    .small-counter b { color: #16a34a; font-size: 18px; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER ---
logo_url = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"
st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="{logo_url}" width="50">
        <h2 style="margin: 0;">RW Pro Live Checker</h2>
    </div>
""", unsafe_allow_html=True)

# 3. Session State Initialization
if 'all_matches' not in st.session_state: st.session_state.all_matches = []
if 'bulk_mode' not in st.session_state: st.session_state.bulk_mode = False
if 'summary_dict' not in st.session_state: st.session_state.summary_dict = {}

def extract_id(url):
    if not url or "play.google.com" not in url: return None
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

# --- SIDEBAR CONFIG ---
st.sidebar.header("⚙️ Configuration")

if st.sidebar.button("🔄 Switch Mode"):
    st.session_state.bulk_mode = not st.session_state.bulk_mode
    st.session_state.all_matches = []
    st.session_state.summary_dict = {}

if st.session_state.bulk_mode:
    bulk_links = st.sidebar.text_area("Bulk Links (One per line):", height=150)
else:
    app_url = st.sidebar.text_input("Play Store URL:", value="https://play.google.com/store/apps/details?id=com.ideopay.user")

# FILTERS (ALL PRO FEATURES INTACT)
scan_depth = st.sidebar.select_slider("Scan Depth (Pages)", options=[1, 10, 50, 100, 200, 500], value=100)
score_filter = st.sidebar.selectbox("Filter Stars", [None, 5, 4, 3, 2, 1], index=0)
target_date = st.sidebar.date_input("Select Date", datetime.now(pytz.timezone('Asia/Kolkata')))

# HINT MODES (RESTORED)
hint_type = st.sidebar.radio("Hint Mode", ["Show All", "No Hint (Normal .)", "Custom Symbol"], index=2)
custom_symbol = ""
if hint_type == "Custom Symbol":
    custom_symbol = st.sidebar.text_input("Enter Symbol (e.g. # or ,,)", value="#")

# --- FETCH LOGIC ---
def fetch_logic(aid, target_dt, depth, star_val):
    all_raw = []
    token = None
    ist_tz = pytz.timezone('Asia/Kolkata')
    for _ in range(depth):
        try:
            res, token = reviews(aid, lang='en', country='in', sort=Sort.NEWEST, count=100, continuation_token=token, filter_score_with=star_val)
            if not res: break
            all_raw.extend(res)
            last_dt = res[-1]['at'].replace(tzinfo=pytz.utc).astimezone(ist_tz).date()
            if last_dt < target_dt: break
            if not token: break
        except: break
    
    matches = []
    for r in all_raw:
        rev_time = r['at'].replace(tzinfo=pytz.utc).astimezone(ist_tz)
        if rev_time.date() == target_dt:
            text = r['content'].strip()
            keep = False
            if hint_type == "Show All": keep = True
            elif hint_type == "No Hint (Normal .)":
                keep = (text.endswith('.') and not text.endswith('..')) or (len(text) > 0 and text[-1].isalnum())
            else:
                keep = text.endswith(custom_symbol) if custom_symbol else True

            if keep:
                matches.append({
                    "User": r['userName'], "Review": text, "App ID": aid,
                    "Rating": f"{r['score']}/5", "Date": rev_time.strftime('%Y-%m-%d'), "Time": rev_time.strftime('%H:%M:%S')
                })
    return matches

# --- EXECUTION ---
if st.button("🚀 Run Professional Check"):
    urls = [u.strip() for u in (bulk_links.split('\n') if st.session_state.bulk_mode else [app_url]) if u.strip()]
    st.session_state.all_matches = []
    st.session_state.summary_dict = {}
    
    progress_bar = st.progress(0)
    for i, url in enumerate(urls):
        aid = extract_id(url)
        if aid:
            with st.spinner(f"Scanning {aid}..."):
                found = fetch_logic(aid, target_date, scan_depth, score_filter)
                st.session_state.all_matches.extend(found)
                st.session_state.summary_dict[aid] = len(found)
        progress_bar.progress((i + 1) / len(urls))
    st.balloons()
    st.toast('✅ Scan Complete!', icon='🎉')

# --- RESULTS ---
if st.session_state.summary_dict:
    st.markdown(f'<div class="small-counter">Total Live: <b>{len(st.session_state.all_matches)}</b></div>', unsafe_allow_html=True)
    
    if st.session_state.all_matches:
        df = pd.DataFrame(st.session_state.all_matches)
        st.dataframe(df, use_container_width=True)
    
    st.markdown("### 📊 Summary")
    st.table(pd.DataFrame(list(st.session_state.summary_dict.items()), columns=['App ID', 'Count']))

    st.markdown("---")
    st.subheader("📥 Export & Reporting")
    col1, col2, col3 = st.columns(3)
    
    # Excel Export with AppID_Date Filename and Gaps
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        start_row = 0
        for aid in st.session_state.summary_dict.keys():
            app_data = [m for m in st.session_state.all_matches if m['App ID'] == aid]
            if app_data:
                pd.DataFrame(app_data).to_excel(writer, index=False, sheet_name='Data', startrow=start_row)
                start_row += len(app_data) + 2
    
    # FILENAME METHOD LOCKED: AppID_Date.xlsx
    file_date = target_date.strftime('%Y-%m-%d')
    if st.session_state.bulk_mode:
        fname = f"Bulk_Report_{file_date}.xlsx"
    else:
        aid_label = extract_id(app_url) if extract_id(app_url) else "Report"
        fname = f"{aid_label}_{file_date}.xlsx"

    col1.download_button("Excel Report", output.getvalue(), fname, use_container_width=True)
    col2.button("PDF Summary (Coming Soon)", use_container_width=True)
    col3.button("Sync to Google Sheets", use_container_width=True)
