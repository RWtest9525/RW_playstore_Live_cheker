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
        padding: 4px 12px;
        border-radius: 4px;
        border: 1px solid #2ecc71;
        display: inline-block;
        margin-bottom: 10px;
        background-color: rgba(46, 204, 113, 0.1);
        font-size: 14px;
    }
    .small-counter b { color: #2ecc71; font-size: 16px; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER SECTION ---
logo_url = "https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png"
st.markdown(f"""
    <div class="header-container">
        <img src="{logo_url}">
        <h2>RW play store live cheker</h2>
    </div>
""", unsafe_allow_html=True)

# 3. Initialize session state
if 'all_matches' not in st.session_state: st.session_state.all_matches = []
if 'bulk_mode' not in st.session_state: st.session_state.bulk_mode = False
if 'summary_data' not in st.session_state: st.session_state.summary_data = {}

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

# --- SIDEBAR CONFIG ---
st.sidebar.header("⚙️ Configuration")
if st.sidebar.button("🔄 Switch to " + ("Single Mode" if st.session_state.bulk_mode else "Bulk Check")):
    st.session_state.bulk_mode = not st.session_state.bulk_mode
    st.session_state.all_matches = []
    st.session_state.summary_data = {}

if st.session_state.bulk_mode:
    bulk_links = st.sidebar.text_area("Enter Bulk Links (One per line):", height=150)
else:
    app_url = st.sidebar.text_input("Play Store URL:", value="https://play.google.com/store/apps/details?id=com.sanatan.dharma")

count = st.sidebar.slider("Batch Size", 10, 1000, 500)
score_filter = st.sidebar.selectbox("Filter Stars", [None, 5, 4, 3, 2, 1])

use_date = st.sidebar.checkbox("Filter by Date", value=True)
ist = pytz.timezone('Asia/Kolkata')
target_date = st.sidebar.date_input("Select Date", datetime.now(ist))

hint_type = st.sidebar.radio("Hint", ["Show All", "No Hint (Normal .)", "Custom Symbol"], index=0)
custom_symbol = st.sidebar.text_input("Symbol", value="!")

def process_reviews(res, app_id):
    matches = []
    ist_tz = pytz.timezone('Asia/Kolkata')
    for r in res:
        rev_time = r['at'].replace(tzinfo=pytz.utc).astimezone(ist_tz)
        if use_date and rev_time.date() != target_date: continue
        
        content = r['content'].strip()
        keep = False
        if hint_type == "Show All": keep = True
        elif hint_type == "No Hint (Normal .)":
            keep = (content.endswith('.') and not content.endswith('..')) or (len(content) > 0 and content[-1].isalnum())
        else:
            keep = content.endswith(custom_symbol) if custom_symbol else True

        if keep:
            matches.append({
                "User": r['userName'],
                "Review": content,
                "App ID": app_id,
                "Rating": f"{r['score']}/5",
                "Date": rev_time.strftime('%Y-%m-%d'),
                "Posting Time": rev_time.strftime('%H:%M:%S')
            })
    return matches

# --- EXECUTION ---
st.markdown("---")
if st.button("🚀 Run Check"):
    st.session_state.all_matches = []
    st.session_state.summary_data = {}
    
    if st.session_state.bulk_mode:
        urls = [u.strip().rstrip('.') for u in bulk_links.split('\n') if u.strip()]
        for url in urls:
            aid = extract_id(url)
            if aid:
                try:
                    res, _ = reviews(aid, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
                    found_matches = process_reviews(res, aid)
                    st.session_state.all_matches.extend(found_matches)
                    # Track count even if it is 0
                    st.session_state.summary_data[aid] = len(found_matches)
                except:
                    st.session_state.summary_data[aid] = 0
    else:
        aid = extract_id(app_url)
        if aid:
            res, _ = reviews(aid, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
            found_matches = process_reviews(res, aid)
            st.session_state.all_matches = found_matches
            st.session_state.summary_data[aid] = len(found_matches)

# --- DISPLAY & EXCEL ---
if st.session_state.summary_data:
    # 1. Total Counter
    st.markdown(f'<div class="small-counter">Total Live Across All Apps: <b>{len(st.session_state.all_matches)}</b></div>', unsafe_allow_html=True)
    
    # 2. Data Table (If matches exist)
    if st.session_state.all_matches:
        df = pd.DataFrame(st.session_state.all_matches)
        desired_order = ["User", "Review", "App ID", "Rating", "Date", "Posting Time"]
        df = df[desired_order]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No matching reviews found for the selected criteria.")
    
    # 3. Summary (Showing 0 for empty apps)
    st.markdown("### 📊 App Wise Summary")
    summary_df = pd.DataFrame(list(st.session_state.summary_data.items()), columns=['App ID', 'Live Count'])
    st.table(summary_df)
    
    # 4. Excel Download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Sheet 1: Data with gaps
        if st.session_state.all_matches:
            start_row = 0
            for app_id in st.session_state.summary_data.keys():
                app_df = df[df['App ID'] == app_id]
                if not app_df.empty:
                    app_df.to_excel(writer, index=False, sheet_name='Data', startrow=start_row)
                    start_row += len(app_df) + 2
        
        # Sheet 2: Summary (Always includes 0 counts)
        workbook = writer.book
        summary_sheet = workbook.add_worksheet('Summary')
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1})
        summary_sheet.write(0, 0, "APP NAME / ID", header_fmt)
        summary_sheet.write(0, 1, "LIVE COUNT", header_fmt)
        
        for i, (app_id, count_val) in enumerate(st.session_state.summary_data.items()):
            summary_sheet.write(i + 1, 0, app_id)
            summary_sheet.write(i + 1, 1, count_val)
            
        summary_sheet.write(len(st.session_state.summary_data) + 1, 0, "GRAND TOTAL", header_fmt)
        summary_sheet.write(len(st.session_state.summary_data) + 1, 1, sum(st.session_state.summary_data.values()), header_fmt)

    file_date = target_date.strftime('%Y-%m-%d')
    final_filename = f"Bulk_Report_{file_date}.xlsx" if st.session_state.bulk_mode else f"{extract_id(app_url)}_{file_date}.xlsx"
    st.download_button(label="📥 Download Excel Report", data=output.getvalue(), file_name=final_filename)
