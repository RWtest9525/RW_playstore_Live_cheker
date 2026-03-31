import streamlit as st
import pandas as pd
import re
from google_play_scraper import Sort, reviews
from datetime import datetime
import pytz
import os
import io

# 1. Page Config
st.set_page_config(page_title="RW play store live cheker", page_icon="🎯", layout="wide")

# 2. CSS Styling
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; }
    .stButton > button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    .header-container { display: flex; align-items: center; gap: 15px; margin-bottom: 15px; }
    .header-container img { height: 50px !important; width: auto !important; border-radius: 5px; }
    .header-container h2 { margin: 0 !important; font-size: 28px !important; }
    .small-counter {
        padding: 4px 12px; border-radius: 4px; border: 1px solid #2ecc71;
        display: inline-block; margin-bottom: 10px; background-color: rgba(46, 204, 113, 0.1);
    }
    .small-counter b { color: #2ecc71; font-size: 16px; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER SECTION ---
logo_url = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"
st.markdown(f'<div class="header-container"><img src="{logo_url}"><h2>RW play store live cheker</h2></div>', unsafe_allow_html=True)

# 3. Initialize session state
if 'all_matches' not in st.session_state: st.session_state.all_matches = []
if 'bulk_mode' not in st.session_state: st.session_state.bulk_mode = False
if 'summary_dict' not in st.session_state: st.session_state.summary_dict = {}

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

# --- SIDEBAR CONFIG ---
st.sidebar.header("⚙️ Configuration")
if st.sidebar.button("🔄 Switch to " + ("Single Mode" if st.session_state.bulk_mode else "Bulk Check")):
    st.session_state.bulk_mode = not st.session_state.bulk_mode
    st.session_state.all_matches = []
    st.session_state.summary_dict = {}

if st.session_state.bulk_mode:
    bulk_links = st.sidebar.text_area("Enter Bulk Links (One per line):", height=150)
else:
    app_url = st.sidebar.text_input("Play Store URL:", value="https://play.google.com/store/apps/details?id=com.sanatan.dharma")

# Increased scan depth options, default set to 100 for deep searching
scan_depth = st.sidebar.select_slider("Scan Depth (Pages)", options=[1, 10, 50, 100, 200, 500], value=100)
score_filter = st.sidebar.selectbox("Filter Stars", [None, 5, 4, 3, 2, 1])

ist = pytz.timezone('Asia/Kolkata')
target_date = st.sidebar.date_input("Select Date", datetime.now(ist))

hint_type = st.sidebar.radio("Hint", ["Show All", "No Hint (Normal .)", "Custom Symbol"], index=2)
custom_symbol = st.sidebar.text_input("Symbol", value="#")

def fetch_deep_reviews(aid, target_dt, depth):
    all_raw = []
    token = None
    ist_tz = pytz.timezone('Asia/Kolkata')
    
    for _ in range(depth):
        try:
            res, token = reviews(aid, lang='en', country='in', sort=Sort.NEWEST, count=100, 
                                 filter_score_with=score_filter, continuation_token=token)
            if not res: break
            all_raw.extend(res)
            
            # Stop scanning if we have passed the target date
            last_date_in_batch = res[-1]['at'].replace(tzinfo=pytz.utc).astimezone(ist_tz).date()
            if last_date_in_batch < target_dt: break
            if not token: break
        except:
            break
        
    matches = []
    for r in all_raw:
        rev_time = r['at'].replace(tzinfo=pytz.utc).astimezone(ist_tz)
        if rev_time.date() != target_dt: continue
        
        content = r['content'].strip()
        keep = False
        
        if hint_type == "Show All": 
            keep = True
        elif hint_type == "No Hint (Normal .)":
            keep = (content.endswith('.') and not content.endswith('..')) or (len(content) > 0 and content[-1].isalnum())
        else:
            keep = content.endswith(custom_symbol) if custom_symbol else True

        if keep:
            matches.append({
                "User": r['userName'], 
                "Review": content, 
                "App ID": aid,
                "Rating": f"{r['score']}/5", 
                "Date": rev_time.strftime('%Y-%m-%d'),
                "Posting Time": rev_time.strftime('%H:%M:%S')
            })
    return matches

# --- EXECUTION ---
if st.button("🚀 Run Check"):
    st.session_state.all_matches = []
    st.session_state.summary_dict = {}
    
    urls = [u.strip().rstrip('.') for u in (bulk_links.split('\n') if st.session_state.bulk_mode else [app_url]) if u.strip()]
    
    for url in urls:
        aid = extract_id(url)
        if aid:
            with st.spinner(f"Scanning {aid}..."):
                found = fetch_deep_reviews(aid, target_date, scan_depth)
                st.session_state.all_matches.extend(found)
                # Ensure every app is in summary, even with 0 count
                st.session_state.summary_dict[aid] = len(found)

# --- DISPLAY ---
if st.session_state.summary_dict:
    st.markdown(f'<div class="small-counter">Total Live: <b>{len(st.session_state.all_matches)}</b></div>', unsafe_allow_html=True)
    
    if st.session_state.all_matches:
        df = pd.DataFrame(st.session_state.all_matches)
        st.dataframe(df[["User", "Review", "App ID", "Rating", "Date", "Posting Time"]], use_container_width=True)
    else:
        st.warning("No reviews found for this specific date and symbol.")
    
    st.markdown("### 📊 Summary")
    summary_df = pd.DataFrame(list(st.session_state.summary_dict.items()), columns=['App ID', 'Live Count'])
    st.table(summary_df)

    # Excel Export with Gap between apps
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Sheet 1: Data with one-line gaps
        start_row = 0
        for aid in st.session_state.summary_dict.keys():
            app_data = [m for m in st.session_state.all_matches if m['App ID'] == aid]
            if app_data:
                pd.DataFrame(app_data).to_excel(writer, index=False, sheet_name='Data', startrow=start_row)
                start_row += len(app_data) + 2 # Add gap
        
        # Sheet 2: Clean Summary
        summary_sheet = writer.book.add_worksheet('Summary')
        header_fmt = writer.book.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1})
        summary_sheet.write(0, 0, "APP ID", header_fmt)
        summary_sheet.write(0, 1, "LIVE COUNT", header_fmt)
        
        for i, (k, v) in enumerate(st.session_state.summary_dict.items()):
            summary_sheet.write(i+1, 0, k)
            summary_sheet.write(i+1, 1, v)
        
        summary_sheet.write(len(st.session_state.summary_dict)+1, 0, "TOTAL", header_fmt)
        summary_sheet.write(len(st.session_state.summary_dict)+1, 1, len(st.session_state.all_matches), header_fmt)

    # Dynamic Naming
    file_date = target_date.strftime('%Y-%m-%d')
    fname = f"Bulk_Report_{file_date}.xlsx" if st.session_state.bulk_mode else f"{extract_id(app_url)}_{file_date}.xlsx"
    st.download_button("📥 Download Excel Report", output.getvalue(), fname)
