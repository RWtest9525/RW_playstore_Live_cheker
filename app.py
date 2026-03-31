import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime
import pytz
import os

# 1. Page Config
st.set_page_config(page_title="RW play store live cheker", page_icon="🎯", layout="wide")

# 2. Header Style Fix
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem !important; }
    [data-testid="column"] { display: flex; align-items: center; }
    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; }
    .stButton > button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER ---
logo_path = "logo.png"
if os.path.exists(logo_path):
    col_l, col_r = st.columns([1, 10])
    with col_l: st.image(logo_path, width=70)
    with col_r: st.title("RW play store live cheker")
else:
    st.title("📊 RW play store live cheker")

# 3. Initialize session state
if 'all_matches' not in st.session_state: st.session_state.all_matches = []
if 'bulk_mode' not in st.session_state: st.session_state.bulk_mode = False

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ Configuration")

# BULK CHECK TOGGLE BUTTON
if st.sidebar.button("🔄 Switch to " + ("Single Mode" if st.session_state.bulk_mode else "Bulk Check")):
    st.session_state.bulk_mode = not st.session_state.bulk_mode
    st.session_state.all_matches = []

if st.session_state.bulk_mode:
    st.sidebar.warning("📁 BULK MODE ACTIVE")
    bulk_links = st.sidebar.text_area("Enter Bulk Links (One per line):", height=200, placeholder="https://play.google.com/...\nhttps://play.google.com/...")
else:
    app_url = st.sidebar.text_input("Play Store URL:", value="https://play.google.com/store/apps/details?id=com.sanatan.dharma")

count = st.sidebar.slider("Batch Size (Per App)", 10, 1000, 500)
score_filter = st.sidebar.selectbox("Filter by Stars", [None, 5, 4, 3, 2, 1], format_func=lambda x: "Show All" if x is None else f"{x} Stars")

st.sidebar.subheader("📅 Date Filter")
use_date = st.sidebar.checkbox("Filter by Specific Date", value=True)
ist = pytz.timezone('Asia/Kolkata')
target_date = st.sidebar.date_input("Select Date", datetime.now(ist))

st.sidebar.subheader("🔍 Hint Logic")
hint_type = st.sidebar.radio("Hint Type", ["Show All", "No Hint (Normal .)", "Custom Symbol"], index=2)
custom_symbol = st.sidebar.text_input("Enter Symbol", value="!") if hint_type == "Custom Symbol" else ""

def process_reviews(res, app_id):
    matches = []
    ist_tz = pytz.timezone('Asia/Kolkata')
    for r in res:
        review_time_ist = r['at'].replace(tzinfo=pytz.utc).astimezone(ist_tz)
        if use_date and review_time_ist.date() != target_date: continue
        
        content = r['content'].strip()
        keep = False
        if hint_type == "Show All": keep = True
        elif hint_type == "No Hint (Normal .)":
            if len(content) > 0:
                keep = (content.endswith('.') and not content.endswith('..')) or content[-1].isalnum()
        else:
            keep = content.endswith(custom_symbol) if custom_symbol else True

        if keep:
            matches.append({
                "App ID": app_id,
                "Date": review_time_ist.strftime('%Y-%m-%d %H:%M:%S'),
                "User": r['userName'],
                "Review": content
            })
    return matches

# --- EXECUTION ---
st.markdown("---")
if st.button("🚀 Run " + ("Bulk Process" if st.session_state.bulk_mode else "Single Check")):
    st.session_state.all_matches = []
    
    if st.session_state.bulk_mode:
        urls = [u.strip() for u in bulk_links.split('\n') if u.strip()]
        if not urls: st.error("Please enter links!")
        else:
            progress_bar = st.progress(0)
            for i, url in enumerate(urls):
                app_id = extract_id(url)
                if app_id:
                    with st.spinner(f"Processing: {app_id}"):
                        res, _ = reviews(app_id, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
                        st.session_state.all_matches.extend(process_reviews(res, app_id))
                progress_bar.progress((i + 1) / len(urls))
            st.success("Bulk Processing Complete!")
    else:
        app_id = extract_id(app_url)
        if app_id:
            with st.spinner(f"Fetching: {app_id}"):
                res, _ = reviews(app_id, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
                st.session_state.all_matches = process_reviews(res, app_id)
        else: st.error("Invalid URL")

# --- RESULTS ---
if st.session_state.all_matches:
    df = pd.DataFrame(st.session_state.all_matches)
    st.dataframe(df, use_container_width=True)
    
    # Filename Logic
    file_date = target_date.strftime('%Y-%m-%d')
    filename = f"Bulk_Report_{file_date}.csv" if st.session_state.bulk_mode else f"{extract_id(app_url)}_{file_date}.csv"
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download All Results", data=csv, file_name=filename, mime='text/csv')
