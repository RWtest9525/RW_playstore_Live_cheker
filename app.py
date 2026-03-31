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
    .block-container { padding-top: 1.5rem !important; }
    .stDataFrame td { white-space: normal !important; word-wrap: break-word !important; }
    .stButton > button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    .counter-box {
        background-color: #1E1E1E;
        border: 2px solid #2ecc71;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
    }
    .counter-box h2 { color: #2ecc71; margin: 0; font-size: 30px; }
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

# --- SIDEBAR CONFIG ---
st.sidebar.header("⚙️ Configuration")
if st.sidebar.button("🔄 Switch to " + ("Single Mode" if st.session_state.bulk_mode else "Bulk Check")):
    st.session_state.bulk_mode = not st.session_state.bulk_mode
    st.session_state.all_matches = []

if st.session_state.bulk_mode:
    bulk_links = st.sidebar.text_area("Enter Bulk Links (One per line):", height=200)
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
                "Stars": "⭐" * r['score'],
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
        for url in urls:
            app_id = extract_id(url)
            if app_id:
                res, _ = reviews(app_id, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
                st.session_state.all_matches.extend(process_reviews(res, app_id))
    else:
        app_id = extract_id(app_url)
        if app_id:
            res, _ = reviews(app_id, lang='en', country='in', sort=Sort.NEWEST, count=count, filter_score_with=score_filter)
            st.session_state.all_matches = process_reviews(res, app_id)

# --- RESULTS DISPLAY ---
if st.session_state.all_matches:
    total_count = len(st.session_state.all_matches)
    st.markdown(f'<div class="counter-box"><h2>Total Live Matches: {total_count}</h2></div>', unsafe_allow_html=True)
    
    df = pd.DataFrame(st.session_state.all_matches)
    st.dataframe(df, use_container_width=True)
    
    # EXCEL EXPORT WITH SUMMARY & FORMULAS
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reviews')
        workbook = writer.book
        worksheet = writer.sheets['Reviews']
        
        # Summary Section
        summary_start_row = len(df) + 3
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1})
        worksheet.write(summary_start_row, 0, "APP SUMMARY", header_fmt)
        worksheet.write(summary_start_row, 1, "LIVE COUNT (Formula)", header_fmt)
        
        unique_apps = df['App ID'].unique()
        for idx, app in enumerate(unique_apps):
            current_row = summary_start_row + 1 + idx
            worksheet.write(current_row, 0, app)
            # EXCEL FORMULA: Counts reviews for this specific App ID
            # Column A (0) is where App ID is stored
            formula = f'=COUNTIF(A2:A{len(df)+1}, "{app}")'
            worksheet.write_formula(current_row, 1, formula)

        # Final Total
        total_row = summary_start_row + len(unique_apps) + 1
        worksheet.write(total_row, 0, "GRAND TOTAL", header_fmt)
        worksheet.write_formula(total_row, 1, f'=SUM(B{summary_start_row + 2}:B{total_row})', header_fmt)

    file_date = target_date.strftime('%Y-%m-%d')
    btn_label = "📥 Download Bulk Excel" if st.session_state.bulk_mode else "📥 Download Excel"
    st.download_button(label=btn_label, data=output.getvalue(), file_name=f"Report_{file_date}.xlsx", mime="application/vnd.ms-excel")
