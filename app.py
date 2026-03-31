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
    
    .summary-box {
        background-color: #0E1117;
        border: 1px solid #333;
        padding: 10px;
        border-radius: 5px;
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER SECTION ---
logo_path = "logo.png"
if os.path.exists(logo_path):
    st.markdown(f"""
        <div class="header-container">
            <img src="https://raw.githubusercontent.com/RWtest9525/RW_playstore_Live_cheker/main/logo.png">
            <h2>RW play store live cheker</h2>
        </div>
    """, unsafe_allow_html=True)
else:
    st.title("📊 RW play store live cheker")

# 3. Initialize session state
if 'all_matches' not in st.session_state: st.session_state.all_matches = []
if 'bulk_mode' not in st.session_state: st.session_state.bulk_mode = False

def extract_id(url):
    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None

# --- SIDEBAR CONFIG ---
st.sidebar.header("⚙️ Configuration")
if st.sidebar.button("🔄 Switch Mode"):
    st.session_state.bulk_mode = not st.session_state.bulk_mode
    st.session_state.all_matches = []

if st.session_state.bulk_mode:
    bulk_links = st.sidebar.text_area("Enter Bulk Links (One per line):", height=150)
else:
    app_url = st.sidebar.text_input("Play Store URL:", value="https://play.google.com/store/apps/details?id=com.sanatan.dharma")

count = st.sidebar.slider("Batch Size", 10, 1000, 500)
score_filter = st.sidebar.selectbox("Filter Stars", [None, 5, 4, 3, 2, 1])

use_date = st.sidebar.checkbox("Filter by Date", value=True)
ist = pytz.timezone('Asia/Kolkata')
target_date = st.sidebar.date_input("Select Date", datetime.now(ist))

hint_type = st.sidebar.radio("Hint", ["Show All", "No Hint (Normal .)", "Custom Symbol"], index=2)
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
    if st.session_state.bulk_mode:
        urls = [u.strip() for u in bulk_links.split('\n') if u.strip()]
        for url in urls:
            aid = extract_id(url)
            if aid:
                res, _ = reviews(aid, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
                st.session_state.all_matches.extend(process_reviews(res, aid))
    else:
        aid = extract_id(app_url)
        if aid:
            res, _ = reviews(aid, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
            st.session_state.all_matches = process_reviews(res, aid)

# --- DISPLAY ---
if st.session_state.all_matches:
    # 1. Small Total Counter
    st.markdown(f'<div class="small-counter">Total Live: <b>{len(st.session_state.all_matches)}</b></div>', unsafe_allow_html=True)
    
    df = pd.DataFrame(st.session_state.all_matches)
    
    # EXACT COLUMN ORDER: User and Review first, Metadata last
    desired_order = ["User", "Review", "App ID", "Rating", "Date", "Posting Time"]
    df = df[desired_order]
    
    # 2. Main Data Table
    st.dataframe(df, use_container_width=True)
    
    # 3. Summary Table on Page
    st.markdown("### 📊 App Wise Summary")
    summary_df = df['App ID'].value_counts().reset_index()
    summary_df.columns = ['App ID', 'Live Count']
    st.table(summary_df)
    
    # 4. EXCEL EXPORT WITH SUMMARY FORMULAS
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
        workbook = writer.book
        worksheet = writer.sheets['Data']
        row_count = len(df)
        
        # Format for Summary Header
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1})
        
        # Write Summary Table at the bottom of Excel
        summary_row = row_count + 3
        worksheet.write(summary_row, 0, "APP NAME / ID", header_fmt)
        worksheet.write(summary_row, 1, "LIVE COUNT", header_fmt)
        
        unique_apps = df['App ID'].unique()
        for i, app in enumerate(unique_apps):
            current_row = summary_row + 1 + i
            worksheet.write(current_row, 0, app)
            # FIXED FORMULA: App ID is in Column C (index 2)
            formula = f'=COUNTIF(C2:C{row_count+1}, "{app}")'
            worksheet.write_formula(current_row, 1, formula)

    st.download_button(
        label="📥 Download Excel Report", 
        data=output.getvalue(), 
        file_name=f"Report_{target_date}.xlsx", 
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
