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
if 'history_list' not in st.session_state: st.session_state.history_list = []
if 'trigger_run' not in st.session_state: st.session_state.trigger_run = False

# Default values for inputs
if 'app_url_input' not in st.session_state: st.session_state.app_url_input = "https://play.google.com/store/apps/details?id=com.ideopay.user"
if 'stored_stars' not in st.session_state: st.session_state.stored_stars = None
if 'stored_hint' not in st.session_state: st.session_state.stored_hint = "Custom Symbol"
if 'stored_symbol' not in st.session_state: st.session_state.stored_symbol = "#"

def extract_id(url):
    if not url or "play.google.com" not in url: return None
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

# --- SIDEBAR CONFIG ---
st.sidebar.header("⚙️ Configuration")

if st.sidebar.button("🔄 Switch Mode"):
    st.session_state.bulk_mode = not st.session_state.bulk_mode
    st.session_state.all_matches = []

if st.session_state.bulk_mode:
    bulk_links = st.sidebar.text_area("Bulk Links (One per line):", height=150)
else:
    st.session_state.app_url_input = st.sidebar.text_input("Play Store URL:", value=st.session_state.app_url_input)

# FILTERS
scan_depth = st.sidebar.select_slider("Scan Depth (Pages)", options=[1, 10, 50, 100, 200, 500], value=100)

star_options = [None, 5, 4, 3, 2, 1]
st.session_state.stored_stars = st.sidebar.selectbox(
    "Filter Stars", 
    star_options, 
    index=star_options.index(st.session_state.stored_stars) if st.session_state.stored_stars in star_options else 0
)

target_date = st.sidebar.date_input("Select Date", datetime.now(pytz.timezone('Asia/Kolkata')))

hint_options = ["Show All", "No Hint (Normal .)", "Custom Symbol"]
st.session_state.stored_hint = st.sidebar.radio(
    "Hint Mode", 
    hint_options, 
    index=hint_options.index(st.session_state.stored_hint)
)

custom_symbol = ""
if st.session_state.stored_hint == "Custom Symbol":
    st.session_state.stored_symbol = st.sidebar.text_input("Enter Symbol", value=st.session_state.stored_symbol)
    custom_symbol = st.session_state.stored_symbol

# --- CLICKABLE HISTORY WITH ERROR SAFETY ---
st.sidebar.markdown("---")
st.sidebar.subheader("📜 History (Click to Load & Run)")

if st.sidebar.button("🗑️ Clear History"):
    st.session_state.history_list = []
    st.rerun()

for h in st.session_state.history_list[-5:]:
    if st.sidebar.button(h.get('label', 'Unknown Scan'), key=f"btn_{h.get('label', 'id')}"):
        # Load settings with safety .get() to prevent KeyErrors
        st.session_state.app_url_input = h.get('url', "https://play.google.com/store/apps/details?id=com.ideopay.user")
        st.session_state.stored_stars = h.get('stars', None)
        st.session_state.stored_hint = h.get('hint_mode', "Custom Symbol")
        st.session_state.stored_symbol = h.get('symbol', "#")
        st.session_state.trigger_run = True 
        st.rerun()

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
            if st.session_state.stored_hint == "Show All": keep = True
            elif st.session_state.stored_hint == "No Hint (Normal .)":
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
run_pressed = st.button("🚀 Run Professional Check")

if run_pressed or st.session_state.trigger_run:
    st.session_state.trigger_run = False 
    
    urls = [u.strip() for u in (bulk_links.split('\n') if st.session_state.bulk_mode else [st.session_state.app_url_input]) if u.strip()]
    st.session_state.all_matches = []
    st.session_state.summary_dict = {}
    
    progress_bar = st.progress(0)
    for i, url in enumerate(urls):
        aid = extract_id(url)
        if aid:
            with st.spinner(f"Scanning {aid}..."):
                found = fetch_logic(aid, target_date, scan_depth, st.session_state.stored_stars)
                st.session_state.all_matches.extend(found)
                st.session_state.summary_dict[aid] = len(found)
                
                time_now = datetime.now().strftime('%H:%M')
                history_entry = {
                    "aid": aid,
                    "url": url,
                    "stars": st.session_state.stored_stars,
                    "hint_mode": st.session_state.stored_hint,
                    "symbol": st.session_state.stored_symbol,
                    "label": f"{time_now} - {aid} ({len(found)})"
                }
                if not any(x['label'] == history_entry['label'] for x in st.session_state.history_list):
                    st.session_state.history_list.append(history_entry)
                    
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
    
    # EXCEL FILENAME LOGIC PRESERVED
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        start_row = 0
        for aid in st.session_state.summary_dict.keys():
            app_data = [m for m in st.session_state.all_matches if m['App ID'] == aid]
            if app_data:
                pd.DataFrame(app_data).to_excel(writer, index=False, sheet_name='Data', startrow=start_row)
                start_row += len(app_data) + 2
    
    file_date = target_date.strftime('%Y-%m-%d')
    if st.session_state.bulk_mode:
        fname = f"Bulk_Report_{file_date}.xlsx"
    else:
        aid_label = extract_id(st.session_state.app_url_input) if extract_id(st.session_state.app_url_input) else "Report"
        fname = f"{aid_label}_{file_date}.xlsx"

    col1.download_button("Excel Report", output.getvalue(), fname, use_container_width=True)
    col2.button("PDF Summary (Coming Soon)", use_container_width=True)
    col3.button("Sync to Google Sheets", use_container_width=True)
