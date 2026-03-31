import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime
import pytz
import os
import io
import time

# 1. Page Config
st.set_page_config(page_title="RW Pro Live Checker", page_icon="🚀", layout="wide")

# 2. Advanced CSS (Dark/Light Toggle & UX)
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

def toggle_theme():
    st.session_state.theme = 'light' if st.session_state.theme == 'dark' else 'dark'

if st.session_state.theme == 'dark':
    st.markdown("""<style>
        .stApp { background-color: #0E1117; color: white; }
        .small-counter { border: 1px solid #2ecc71; background-color: rgba(46, 204, 113, 0.1); padding: 5px 15px; border-radius: 5px; }
    </style>""", unsafe_allow_html=True)
else:
    st.markdown("""<style>
        .stApp { background-color: #FFFFFF; color: black; }
        .small-counter { border: 1px solid #2ecc71; background-color: #e8f8f0; padding: 5px 15px; border-radius: 5px; }
    </style>""", unsafe_allow_html=True)

# 3. Initialize session state
if 'all_matches' not in st.session_state: st.session_state.all_matches = []
if 'bulk_mode' not in st.session_state: st.session_state.bulk_mode = False
if 'summary_dict' not in st.session_state: st.session_state.summary_dict = {}
if 'history' not in st.session_state: st.session_state.history = []

def extract_id(url):
    # URL Validator logic
    if not url or "play.google.com" not in url:
        return None
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

# --- SIDEBAR ---
st.sidebar.button("🌓 Toggle Dark/Light Mode", on_click=toggle_theme)

st.sidebar.header("⚙️ Configuration")
if st.sidebar.button("🔄 Switch Mode"):
    st.session_state.bulk_mode = not st.session_state.bulk_mode
    st.session_state.all_matches = []

if st.session_state.bulk_mode:
    bulk_links = st.sidebar.text_area("Enter Bulk Links:", height=150, placeholder="Paste URLs here...")
else:
    app_url = st.sidebar.text_input("Play Store URL:", value="https://play.google.com/store/apps/details?id=com.sanatan.dharma")

scan_depth = st.sidebar.select_slider("Scan Depth (Pages)", options=[1, 10, 50, 100, 200, 500], value=100)
ist = pytz.timezone('Asia/Kolkata')
target_date = st.sidebar.date_input("Select Date", datetime.now(ist))
custom_symbol = st.sidebar.text_input("Symbol Hint", value="#")

# --- HISTORY LOG ---
st.sidebar.markdown("---")
st.sidebar.subheader("📜 Recent History")
for item in st.session_state.history[-5:]:
    st.sidebar.caption(f"🕒 {item}")

def fetch_deep_reviews(aid, target_dt, depth):
    all_raw = []
    token = None
    ist_tz = pytz.timezone('Asia/Kolkata')
    for _ in range(depth):
        try:
            res, token = reviews(aid, lang='en', country='in', sort=Sort.NEWEST, count=100, continuation_token=token)
            if not res: break
            all_raw.extend(res)
            last_date = res[-1]['at'].replace(tzinfo=pytz.utc).astimezone(ist_tz).date()
            if last_date < target_dt: break
            if not token: break
        except: break
        
    matches = []
    for r in all_raw:
        rev_time = r['at'].replace(tzinfo=pytz.utc).astimezone(ist_tz)
        if rev_time.date() == target_dt and r['content'].strip().endswith(custom_symbol):
            matches.append({
                "User": r['userName'], "Review": r['content'].strip(), "App ID": aid,
                "Rating": f"{r['score']}/5", "Date": rev_time.strftime('%Y-%m-%d'), "Time": rev_time.strftime('%H:%M:%S')
            })
    return matches

# --- EXECUTION ---
if st.button("🚀 Run Professional Check"):
    urls = [u.strip() for u in (bulk_links.split('\n') if st.session_state.bulk_mode else [app_url]) if u.strip()]
    
    # 1. URL Validation Check
    valid_urls = [u for u in urls if extract_id(u)]
    if len(valid_urls) != len(urls):
        st.error(f"❌ {len(urls) - len(valid_urls)} Invalid URLs detected and skipped.")

    st.session_state.all_matches = []
    st.session_state.summary_dict = {}
    
    progress_text = "Operation in progress. Please wait."
    my_bar = st.progress(0, text=progress_text)
    
    for i, url in enumerate(valid_urls):
        aid = extract_id(url)
        found = fetch_deep_reviews(aid, target_date, scan_depth)
        st.session_state.all_matches.extend(found)
        st.session_state.summary_dict[aid] = len(found)
        st.session_state.history.append(f"{aid} ({len(found)} matches)")
        my_bar.progress((i + 1) / len(valid_urls), text=f"Scanning {aid}...")

    # 2. Live Notification (Audio Alert + Balloon)
    st.balloons()
    st.toast('✅ Scan Complete!', icon='🎉')
    # Simple alert sound (optional Browser behavior)
    st.markdown("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-01a.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

# --- DISPLAY ---
if st.session_state.summary_dict:
    st.markdown(f'<div class="small-counter">Total Live: <b>{len(st.session_state.all_matches)}</b></div>', unsafe_allow_html=True)
    
    col_main, col_sum = st.columns([3, 1])
    
    with col_main:
        if st.session_state.all_matches:
            df = pd.DataFrame(st.session_state.all_matches)
            st.dataframe(df, use_container_width=True)
    
    with col_sum:
        st.markdown("### 📊 Summary")
        summary_df = pd.DataFrame(list(st.session_state.summary_dict.items()), columns=['App ID', 'Count'])
        st.table(summary_df)

    # 3. Export Suite
    st.markdown("---")
    st.subheader("📥 Export & Reporting")
    c1, c2, c3 = st.columns(3)
    
    # Excel Export
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pd.DataFrame(st.session_state.all_matches).to_excel(writer, index=False, sheet_name='Data')
    c1.download_button("Excel Report", output.getvalue(), f"Report_{target_date}.xlsx", use_container_width=True)
    
    # PDF Placeholder (Simulated via Markdown Report)
    c2.button("Generate PDF Summary", on_click=lambda: st.info("PDF Engine requires ReportLab library setup."), use_container_width=True)
    
    # Google Sheets Info
    c3.button("Sync to Google Sheets", on_click=lambda: st.warning("Please connect your Google Service Account JSON first."), use_container_width=True)
